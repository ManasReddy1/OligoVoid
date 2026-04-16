"""Killer experiment: simulated discovery efficiency for VPA.

THE CORE QUESTION: "How many iterations does each strategy need to discover
a top-X% candidate?"

This is the most compelling evidence for VPA's value. We simulate a realistic
active learning loop on real OligoFormer data where an oracle holds back
ground-truth efficacy values and each strategy must choose which candidate
to query next.

Six strategies are compared:
  1. Random         - uniform random baseline
  2. Greedy         - pure exploitation (highest predicted mean)
  3. EI             - Expected Improvement (standard BO acquisition)
  4. UCB            - Upper Confidence Bound (mu + 2*sigma)
  5. Diversity      - max-min Euclidean distance in feature space
  6. VPA            - Void-Prioritized Acquisition (EI x novelty bonus)

VPA uniquely combines exploitation (EI) with exploration of under-sampled
regions (void preference), enabling faster discovery of high-efficacy
candidates while maintaining broad coverage of the modification space.

Functions:
  - run_simulated_discovery_experiment()  - THE killer experiment
  - run_coverage_experiment()             - feature-space coverage tracking
  - run_vpa_lambda_sensitivity()          - lambda trade-off analysis
  - format_killer_experiment_table()      - markdown table for README
"""

from __future__ import annotations

import logging
import time
import warnings
from typing import Any

import numpy as np
from scipy.stats import mannwhitneyu, norm
from sklearn.cluster import KMeans
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel

logger = logging.getLogger(__name__)

# Suppress GP convergence warnings during fast experiments
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*lbfgs.*")
warnings.filterwarnings("ignore", message=".*ConvergenceWarning.*")

try:
    from sklearn.exceptions import ConvergenceWarning
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
except ImportError:
    pass


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _load_full_dataset() -> tuple[np.ndarray, np.ndarray, dict]:
    """Load the full OligoFormer dataset (train+test combined).

    Returns:
        (X_all, y_all, metadata) where X_all has shape (N, n_features).
    """
    from backend.real_data_pipeline import build_ml_dataset

    X_train, X_test, y_train, y_test, meta = build_ml_dataset()
    X_all = np.vstack([X_train, X_test])
    y_all = np.concatenate([y_train, y_test])

    # Clip efficacy to [0, 100] for consistency
    y_all = np.clip(y_all, 0.0, 100.0)

    return X_all, y_all, meta


def _subsample_universe(
    X_all: np.ndarray,
    y_all: np.ndarray,
    n_universe: int = 500,
    rng: np.random.RandomState | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Stratified subsample of the full dataset for tractable experiments.

    Preserves the efficacy distribution (quartile-stratified).
    """
    if rng is None:
        rng = np.random.RandomState(42)

    N = len(y_all)
    if N <= n_universe:
        return X_all.copy(), y_all.copy()

    # Quartile-stratified sampling
    quartiles = np.digitize(y_all, np.percentile(y_all, [25, 50, 75]))
    indices = []
    for q in np.unique(quartiles):
        q_idx = np.where(quartiles == q)[0]
        n_take = max(1, int(n_universe * len(q_idx) / N))
        chosen = rng.choice(q_idx, size=min(n_take, len(q_idx)), replace=False)
        indices.extend(chosen.tolist())

    indices = indices[:n_universe]
    rng.shuffle(indices)
    return X_all[indices], y_all[indices]


def _fit_lightweight_gp(
    X_obs: np.ndarray,
    y_obs: np.ndarray,
    X_pool: np.ndarray,
    max_train: int = 150,
    rng: np.random.RandomState | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit a lightweight GP and predict mean+std on pool candidates.

    Optimized for speed: minimal restarts, subsampled training data.

    Args:
        X_obs: Observed feature matrix, shape (n_obs, d).
        y_obs: Observed efficacy values, shape (n_obs,).
        X_pool: Pool candidates, shape (n_pool, d).
        max_train: Max training points for GP.
        rng: Random state for subsampling.

    Returns:
        (mu, sigma) arrays of shape (n_pool,).
    """
    if rng is None:
        rng = np.random.RandomState(42)

    # Subsample if needed
    if len(y_obs) > max_train:
        idx = rng.choice(len(y_obs), size=max_train, replace=False)
        X_train = X_obs[idx]
        y_train = y_obs[idx]
    else:
        X_train = X_obs
        y_train = y_obs

    # Normalize
    X_mean = X_train.mean(axis=0)
    X_std = X_train.std(axis=0)
    X_std[X_std < 1e-8] = 1.0
    X_train_norm = (X_train - X_mean) / X_std
    X_pool_norm = (X_pool - X_mean) / X_std

    d = X_train.shape[1]
    kernel = (
        ConstantKernel(1.0, constant_value_bounds=(1e-2, 1e3))
        * Matern(nu=2.5, length_scale=np.ones(d), length_scale_bounds=(1e-1, 1e4))
        + WhiteKernel(noise_level=1.0, noise_level_bounds=(1e-2, 1e3))
    )
    gpr = GaussianProcessRegressor(
        kernel=kernel,
        n_restarts_optimizer=0,  # speed: single optimization
        normalize_y=True,
        alpha=1e-3,
    )
    gpr.fit(X_train_norm, y_train)
    mu, sigma = gpr.predict(X_pool_norm, return_std=True)

    # Ensure sigma is positive
    sigma = np.maximum(sigma, 1e-6)

    return mu.astype(np.float64), sigma.astype(np.float64)


def _compute_ei(mu: np.ndarray, sigma: np.ndarray, best_so_far: float) -> np.ndarray:
    """Expected Improvement acquisition function.

    EI(x) = (mu(x) - f*) * Phi(z) + sigma(x) * phi(z)
    where z = (mu(x) - f*) / sigma(x), f* = best observed value.
    """
    z = (mu - best_so_far) / sigma
    ei = (mu - best_so_far) * norm.cdf(z) + sigma * norm.pdf(z)
    return np.maximum(ei, 0.0)


def _compute_ucb(mu: np.ndarray, sigma: np.ndarray, kappa: float = 2.0) -> np.ndarray:
    """Upper Confidence Bound acquisition: mu + kappa * sigma."""
    return mu + kappa * sigma


def _compute_diversity_scores(
    X_pool: np.ndarray, X_obs: np.ndarray
) -> np.ndarray:
    """Max-min Euclidean distance from pool to observed points.

    For each pool candidate, compute the minimum Euclidean distance to
    any observed point. Select the candidate with the maximum such distance.
    """
    if len(X_obs) == 0:
        return np.ones(len(X_pool))

    # Normalize for fair distance computation
    X_all = np.vstack([X_obs, X_pool])
    X_mean = X_all.mean(axis=0)
    X_std = X_all.std(axis=0)
    X_std[X_std < 1e-8] = 1.0

    X_obs_norm = (X_obs - X_mean) / X_std
    X_pool_norm = (X_pool - X_mean) / X_std

    # Efficient pairwise min-distance via cdist
    from scipy.spatial.distance import cdist
    dist_matrix = cdist(X_pool_norm, X_obs_norm, metric="euclidean")
    min_dists = dist_matrix.min(axis=1)

    return min_dists


def _compute_vpa(
    mu: np.ndarray,
    sigma: np.ndarray,
    best_so_far: float,
    X_pool: np.ndarray,
    X_obs: np.ndarray,
    lam: float = 0.5,
) -> np.ndarray:
    """Void-Prioritized Acquisition: EI * (1 + lambda * d_min / max_d).

    Combines Expected Improvement with a novelty bonus that scales with
    distance to the nearest observed point. This biases selection toward
    under-explored regions (voids) while still prioritizing high EI.

    Args:
        mu: Predicted means for pool candidates.
        sigma: Predicted stds for pool candidates.
        best_so_far: Best observed value so far.
        X_pool: Pool features, shape (n_pool, d).
        X_obs: Observed features, shape (n_obs, d).
        lam: Lambda parameter controlling void preference strength.

    Returns:
        VPA scores, shape (n_pool,).
    """
    ei = _compute_ei(mu, sigma, best_so_far)
    d_min = _compute_diversity_scores(X_pool, X_obs)
    max_d = d_min.max() if d_min.max() > 1e-8 else 1.0
    novelty_bonus = 1.0 + lam * (d_min / max_d)
    return ei * novelty_bonus


def _cluster_features(X: np.ndarray, n_clusters: int = 20) -> np.ndarray:
    """Assign feature vectors to clusters for coverage tracking.

    Returns cluster labels, shape (N,).
    """
    # Normalize before clustering
    X_mean = X.mean(axis=0)
    X_std = X.std(axis=0)
    X_std[X_std < 1e-8] = 1.0
    X_norm = (X - X_mean) / X_std

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=5, max_iter=100)
    return kmeans.fit_predict(X_norm)


def _run_single_strategy(
    strategy: str,
    X_universe: np.ndarray,
    y_universe: np.ndarray,
    cluster_labels: np.ndarray,
    n_clusters: int,
    seed_indices: np.ndarray,
    pool_indices: np.ndarray,
    top_threshold: float,
    n_cycles: int,
    max_pool: int,
    vpa_lambda: float,
    rng: np.random.RandomState,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Run a single strategy for one repeat.

    Returns:
        (best_curve, coverage_curve, iteration_to_top)
        best_curve: shape (n_cycles,), cumulative best found
        coverage_curve: shape (n_cycles,), fraction of clusters covered
        iteration_to_top: 1-indexed cycle when top was first reached
    """
    X_obs = X_universe[seed_indices].copy()
    y_obs = y_universe[seed_indices].copy()
    obs_cluster_set = set(cluster_labels[seed_indices].tolist())
    pool_idx = pool_indices.copy()
    best_found = float(y_obs.max())
    found_top = False
    found_iter = n_cycles + 1

    best_curve = np.zeros(n_cycles)
    coverage_curve = np.zeros(n_cycles)

    for cycle in range(n_cycles):
        if len(pool_idx) == 0:
            best_curve[cycle] = best_found
            coverage_curve[cycle] = len(obs_cluster_set) / n_clusters
            continue

        # Subsample pool for GP speed
        if len(pool_idx) > max_pool:
            sub = rng.choice(len(pool_idx), size=max_pool, replace=False)
            pool_sub = pool_idx[sub]
        else:
            pool_sub = pool_idx

        X_pool = X_universe[pool_sub]

        # --- Strategy selection ---
        if strategy == "random":
            pick_local = rng.randint(len(pool_sub))

        elif strategy == "diversity":
            div_scores = _compute_diversity_scores(X_pool, X_obs)
            pick_local = int(np.argmax(div_scores))

        else:
            # GP-based strategies: greedy, ei, ucb, vpa
            mu, sigma = _fit_lightweight_gp(X_obs, y_obs, X_pool, rng=rng)

            if strategy == "greedy":
                pick_local = int(np.argmax(mu))
            elif strategy == "ei":
                scores = _compute_ei(mu, sigma, best_found)
                pick_local = int(np.argmax(scores))
            elif strategy == "ucb":
                scores = _compute_ucb(mu, sigma, kappa=2.0)
                pick_local = int(np.argmax(scores))
            elif strategy == "vpa":
                scores = _compute_vpa(
                    mu, sigma, best_found, X_pool, X_obs, lam=vpa_lambda
                )
                pick_local = int(np.argmax(scores))
            else:
                pick_local = 0

        # Reveal oracle efficacy
        picked_global = pool_sub[pick_local]
        x_new = X_universe[picked_global].reshape(1, -1)
        y_new = float(y_universe[picked_global])

        # Update observations
        X_obs = np.vstack([X_obs, x_new])
        y_obs = np.append(y_obs, y_new)
        obs_cluster_set.add(int(cluster_labels[picked_global]))

        # Remove from pool
        pool_idx = pool_idx[pool_idx != picked_global]

        # Track metrics
        best_found = max(best_found, y_new)
        best_curve[cycle] = best_found
        coverage_curve[cycle] = len(obs_cluster_set) / n_clusters

        # Check if top-X% reached
        if not found_top and best_found >= top_threshold:
            found_top = True
            found_iter = cycle + 1  # 1-indexed

    return best_curve, coverage_curve, found_iter


# ---------------------------------------------------------------------------
# EXPERIMENT 1: SIMULATED DISCOVERY (THE KILLER EXPERIMENT)
# ---------------------------------------------------------------------------

def run_simulated_discovery_experiment(
    n_repeats: int = 20,
    n_cycles: int = 50,
    top_pct: int = 5,
    max_pool: int = 200,
    n_universe: int = 500,
    vpa_lambda: float = 0.5,
) -> dict:
    """THE KILLER EXPERIMENT: iterations to discover a top-X% candidate.

    Setup:
      - Subsample n_universe sequences from full OligoFormer dataset
      - For each repeat: randomly split into seed (10) + pool (rest)
      - Each cycle: strategy selects 1 candidate from pool, oracle reveals efficacy
      - Track: cumulative best, coverage, iterations to reach top-5%

    Using a smaller universe (500 sequences) makes the experiment:
      - Harder: fewer top candidates to find by chance
      - Faster: GP fits on <150 points with 0 optimizer restarts
      - More realistic: simulates real-world scenario of limited candidates

    Strategies compared: random, greedy, ei, ucb, diversity, vpa

    Args:
        n_repeats: Number of independent repeats for statistics.
        n_cycles: Maximum number of AL cycles per run.
        top_pct: Percentile threshold for "discovery" (default 5 = top 5%).
        max_pool: Max pool size per cycle for GP speed.
        n_universe: Size of the working universe (subsampled from full data).
        vpa_lambda: Lambda for VPA's novelty bonus.

    Returns:
        Dict with iterations_to_top5, best_found_over_iterations,
        space_coverage_over_iterations, pairwise_significance, table.
    """
    np.random.seed(42)
    t0 = time.time()

    logger.info(
        "Starting killer experiment: %d repeats x %d cycles, top-%d%%",
        n_repeats, n_cycles, top_pct,
    )

    # Load full dataset and subsample
    X_full, y_full, meta = _load_full_dataset()
    X_universe, y_universe = _subsample_universe(X_full, y_full, n_universe)
    N = len(y_universe)
    n_features = X_universe.shape[1]

    logger.info("Universe: %d sequences (from %d total), %d features",
                N, len(y_full), n_features)

    # Pre-compute cluster labels for coverage tracking
    n_clusters = 20
    cluster_labels = _cluster_features(X_universe, n_clusters=n_clusters)

    # Top-X% threshold on the universe
    top_threshold = float(np.percentile(y_universe, 100 - top_pct))
    logger.info("Top-%d%% threshold: %.1f%%", top_pct, top_threshold)

    strategies = ["random", "greedy", "ei", "ucb", "diversity", "vpa"]
    n_seed = 10  # initial random seed observations

    # Storage
    iterations_to_top = {s: [] for s in strategies}
    best_curves = {s: np.zeros((n_repeats, n_cycles)) for s in strategies}
    coverage_curves = {s: np.zeros((n_repeats, n_cycles)) for s in strategies}

    for rep in range(n_repeats):
        rng = np.random.RandomState(rep * 17 + 42)

        # Random seed/pool split
        perm = rng.permutation(N)
        seed_indices = perm[:n_seed]
        pool_indices = perm[n_seed:]

        for strategy in strategies:
            best_curve, cov_curve, found_iter = _run_single_strategy(
                strategy=strategy,
                X_universe=X_universe,
                y_universe=y_universe,
                cluster_labels=cluster_labels,
                n_clusters=n_clusters,
                seed_indices=seed_indices,
                pool_indices=pool_indices,
                top_threshold=top_threshold,
                n_cycles=n_cycles,
                max_pool=max_pool,
                vpa_lambda=vpa_lambda,
                rng=np.random.RandomState(rng.randint(0, 2**31)),
            )
            best_curves[strategy][rep] = best_curve
            coverage_curves[strategy][rep] = cov_curve
            iterations_to_top[strategy].append(found_iter)

        if (rep + 1) % max(1, n_repeats // 4) == 0 or rep == 0:
            elapsed = time.time() - t0
            logger.info(
                "  Repeat %d/%d done (%.1fs elapsed)", rep + 1, n_repeats, elapsed
            )

    # ---- Aggregate results ----

    # 1. Iterations to top-X%
    iter_stats = {}
    for s in strategies:
        arr = np.array(iterations_to_top[s], dtype=float)
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr))
        se = std_val / max(np.sqrt(len(arr)), 1)
        ci_lo = mean_val - 1.96 * se
        ci_hi = mean_val + 1.96 * se
        iter_stats[s] = {
            "mean": round(mean_val, 1),
            "std": round(std_val, 1),
            "ci_95": (round(ci_lo, 1), round(ci_hi, 1)),
            "raw": arr.tolist(),
        }

    # 2. Best found over iterations (averaged across repeats)
    best_over_iters = {}
    for s in strategies:
        best_over_iters[s] = [
            round(float(v), 2) for v in best_curves[s].mean(axis=0)
        ]

    # 3. Space coverage over iterations
    coverage_over_iters = {}
    for s in strategies:
        coverage_over_iters[s] = [
            round(float(v), 4) for v in coverage_curves[s].mean(axis=0)
        ]

    # 4. Pairwise significance (VPA vs each other strategy)
    pairwise = {}
    vpa_arr = np.array(iterations_to_top["vpa"], dtype=float)
    for s in strategies:
        if s == "vpa":
            continue
        other_arr = np.array(iterations_to_top[s], dtype=float)
        mean_diff = float(np.mean(other_arr) - np.mean(vpa_arr))
        try:
            stat, p_val = mannwhitneyu(vpa_arr, other_arr, alternative="less")
            p_val = float(p_val)
        except Exception:
            p_val = 1.0

        # Cohen's d effect size
        pooled_std = np.sqrt((np.var(vpa_arr) + np.var(other_arr)) / 2)
        effect_size = mean_diff / pooled_std if pooled_std > 1e-8 else 0.0

        pairwise[f"vpa_vs_{s}"] = {
            "mean_diff": round(mean_diff, 1),
            "p_value": round(p_val, 4),
            "effect_size": round(effect_size, 2),
        }

    # 5. Build markdown table
    table = _build_main_table(
        iter_stats, best_over_iters, coverage_over_iters, pairwise, n_cycles
    )

    elapsed_total = round(time.time() - t0, 1)
    logger.info("Killer experiment done in %.1fs", elapsed_total)

    return {
        "iterations_to_top5": iter_stats,
        "best_found_over_iterations": best_over_iters,
        "space_coverage_over_iterations": coverage_over_iters,
        "pairwise_significance": pairwise,
        "table": table,
        "config": {
            "n_repeats": n_repeats,
            "n_cycles": n_cycles,
            "top_pct": top_pct,
            "max_pool": max_pool,
            "n_universe": N,
            "vpa_lambda": vpa_lambda,
            "n_sequences_full": int(len(y_full)),
            "n_features": n_features,
            "top_threshold": round(top_threshold, 1),
        },
        "elapsed_seconds": elapsed_total,
    }


def _build_main_table(
    iter_stats: dict,
    best_over_iters: dict,
    coverage_over_iters: dict,
    pairwise: dict,
    n_cycles: int,
) -> str:
    """Build the killer experiment markdown table."""
    # Use iteration 30 (or last available) for snapshot metrics
    snap_iter = min(29, n_cycles - 1)  # 0-indexed

    lines = [
        "| Strategy   | Iterations to Top-5% | Best @ Iter 30 | Coverage @ Iter 30 | p vs VPA |",
        "|------------|---------------------:|---------------:|-------------------:|----------|",
    ]

    strategy_display = {
        "random": "Random",
        "greedy": "Greedy",
        "ei": "EI",
        "ucb": "UCB",
        "diversity": "Diversity",
        "vpa": "**VPA**",
    }

    for s in ["random", "greedy", "ei", "ucb", "diversity", "vpa"]:
        stats = iter_stats[s]
        iter_str = f"{stats['mean']:.0f} +/- {stats['std']:.0f}"

        best_at_snap = (
            best_over_iters[s][snap_iter]
            if len(best_over_iters[s]) > snap_iter
            else best_over_iters[s][-1]
        )
        cov_at_snap = (
            coverage_over_iters[s][snap_iter]
            if len(coverage_over_iters[s]) > snap_iter
            else coverage_over_iters[s][-1]
        )
        cov_pct = cov_at_snap * 100

        name = strategy_display[s]

        if s == "vpa":
            p_str = "---"
            iter_str = f"**{iter_str}**"
            best_str = f"**{best_at_snap:.1f}**"
            cov_str = f"**{cov_pct:.0f}%**"
        else:
            pw = pairwise.get(f"vpa_vs_{s}", {})
            p_val = pw.get("p_value", 1.0)
            if p_val < 0.001:
                p_str = "p<0.001"
            elif p_val < 0.01:
                p_str = f"p={p_val:.3f}"
            elif p_val < 0.05:
                p_str = f"p={p_val:.2f}"
            else:
                p_str = f"p={p_val:.2f}"
            best_str = f"{best_at_snap:.1f}"
            cov_str = f"{cov_pct:.0f}%"

        lines.append(
            f"| {name:<10s} | {iter_str:>20s} | {best_str:>14s} | {cov_str:>18s} | {p_str:<8s} |"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# EXPERIMENT 2: COVERAGE EXPERIMENT
# ---------------------------------------------------------------------------

def run_coverage_experiment(
    n_repeats: int = 20,
    n_cycles: int = 30,
    n_clusters: int = 20,
    max_pool: int = 200,
    n_universe: int = 500,
) -> dict:
    """Track how many unique feature-space regions each strategy covers.

    Clusters the feature space into n_clusters regions using KMeans.
    Coverage = fraction of clusters with at least one observed point.

    Args:
        n_repeats: Number of independent repeats.
        n_cycles: Number of AL cycles per run.
        n_clusters: Number of KMeans clusters.
        max_pool: Max pool subsample per cycle.
        n_universe: Working universe size.

    Returns:
        Dict with per-strategy coverage curves and summary.
    """
    np.random.seed(42)
    t0 = time.time()

    X_full, y_full, _ = _load_full_dataset()
    X_universe, y_universe = _subsample_universe(X_full, y_full, n_universe)
    N = len(y_universe)

    # Pre-compute cluster labels
    cluster_labels = _cluster_features(X_universe, n_clusters=n_clusters)

    # Top threshold for GP strategies (they need best_found)
    top_threshold = float(np.percentile(y_universe, 95))

    strategies = ["random", "greedy", "ei", "ucb", "diversity", "vpa"]
    n_seed = 10
    coverage_curves = {s: np.zeros((n_repeats, n_cycles)) for s in strategies}

    for rep in range(n_repeats):
        rng = np.random.RandomState(rep * 23 + 7)
        perm = rng.permutation(N)
        seed_indices = perm[:n_seed]
        pool_indices = perm[n_seed:]

        for strategy in strategies:
            _, cov_curve, _ = _run_single_strategy(
                strategy=strategy,
                X_universe=X_universe,
                y_universe=y_universe,
                cluster_labels=cluster_labels,
                n_clusters=n_clusters,
                seed_indices=seed_indices,
                pool_indices=pool_indices,
                top_threshold=top_threshold,
                n_cycles=n_cycles,
                max_pool=max_pool,
                vpa_lambda=0.5,
                rng=np.random.RandomState(rng.randint(0, 2**31)),
            )
            coverage_curves[strategy][rep] = cov_curve

    # Aggregate
    result = {}
    for s in strategies:
        mean_curve = coverage_curves[s].mean(axis=0)
        std_curve = coverage_curves[s].std(axis=0)
        result[s] = {
            "mean": [round(float(v), 4) for v in mean_curve],
            "std": [round(float(v), 4) for v in std_curve],
            "final_coverage": round(float(mean_curve[-1]), 4),
        }

    elapsed = round(time.time() - t0, 1)
    return {
        "strategies": result,
        "config": {
            "n_repeats": n_repeats,
            "n_cycles": n_cycles,
            "n_clusters": n_clusters,
            "n_universe": len(y_universe),
        },
        "elapsed_seconds": elapsed,
    }


# ---------------------------------------------------------------------------
# EXPERIMENT 3: VPA LAMBDA SENSITIVITY
# ---------------------------------------------------------------------------

def run_vpa_lambda_sensitivity(
    lambdas: list[float] | None = None,
    n_repeats: int = 10,
    n_cycles: int = 30,
    top_pct: int = 5,
    max_pool: int = 200,
    n_universe: int = 500,
) -> dict:
    """Show how VPA performance changes with the lambda parameter.

    lambda=0   -> pure EI (no void preference)
    lambda=0.5 -> default VPA
    lambda=2.0 -> heavy void preference

    Args:
        lambdas: List of lambda values to test.
        n_repeats: Number of repeats per lambda.
        n_cycles: Number of AL cycles.
        top_pct: Top percentile threshold.
        max_pool: Max pool subsample per cycle.
        n_universe: Working universe size.

    Returns:
        Dict with per-lambda iterations_to_top, coverage, best_found.
    """
    if lambdas is None:
        lambdas = [0.0, 0.1, 0.25, 0.5, 0.75, 1.0, 2.0]

    np.random.seed(42)
    t0 = time.time()

    X_full, y_full, _ = _load_full_dataset()
    X_universe, y_universe = _subsample_universe(X_full, y_full, n_universe)
    N = len(y_universe)

    n_clusters = 20
    cluster_labels = _cluster_features(X_universe, n_clusters=n_clusters)
    top_threshold = float(np.percentile(y_universe, 100 - top_pct))
    n_seed = 10

    results_per_lambda = {}

    for lam in lambdas:
        iters_to_top = []
        final_coverage = []
        final_best = []

        for rep in range(n_repeats):
            rng = np.random.RandomState(rep * 31 + 11)
            perm = rng.permutation(N)
            seed_indices = perm[:n_seed]
            pool_indices = perm[n_seed:]

            best_curve, cov_curve, found_iter = _run_single_strategy(
                strategy="vpa",
                X_universe=X_universe,
                y_universe=y_universe,
                cluster_labels=cluster_labels,
                n_clusters=n_clusters,
                seed_indices=seed_indices,
                pool_indices=pool_indices,
                top_threshold=top_threshold,
                n_cycles=n_cycles,
                max_pool=max_pool,
                vpa_lambda=lam,
                rng=np.random.RandomState(rng.randint(0, 2**31)),
            )

            iters_to_top.append(found_iter)
            final_coverage.append(float(cov_curve[-1]))
            final_best.append(float(best_curve[-1]))

        arr_iters = np.array(iters_to_top, dtype=float)
        arr_cov = np.array(final_coverage, dtype=float)
        arr_best = np.array(final_best, dtype=float)

        results_per_lambda[lam] = {
            "iterations_to_top": {
                "mean": round(float(arr_iters.mean()), 1),
                "std": round(float(arr_iters.std()), 1),
            },
            "coverage_at_final": {
                "mean": round(float(arr_cov.mean()), 4),
                "std": round(float(arr_cov.std()), 4),
            },
            "best_at_final": {
                "mean": round(float(arr_best.mean()), 1),
                "std": round(float(arr_best.std()), 1),
            },
        }

    elapsed = round(time.time() - t0, 1)

    # Build table
    table_lines = [
        "| Lambda | Iterations to Top-5% | Coverage @ Final | Best @ Final |",
        "|-------:|---------------------:|-----------------:|-------------:|",
    ]
    for lam in lambdas:
        r = results_per_lambda[lam]
        it = r["iterations_to_top"]
        cv = r["coverage_at_final"]
        bf = r["best_at_final"]
        table_lines.append(
            f"| {lam:.2f}   | {it['mean']:.0f} +/- {it['std']:.0f}"
            f" | {cv['mean']*100:.0f}% +/- {cv['std']*100:.0f}%"
            f" | {bf['mean']:.1f} +/- {bf['std']:.1f} |"
        )

    return {
        "lambdas": results_per_lambda,
        "table": "\n".join(table_lines),
        "config": {
            "lambdas_tested": lambdas,
            "n_repeats": n_repeats,
            "n_cycles": n_cycles,
            "top_pct": top_pct,
            "n_universe": len(y_universe),
        },
        "elapsed_seconds": elapsed,
    }


# ---------------------------------------------------------------------------
# EXPERIMENT 4: FORMAT TABLE
# ---------------------------------------------------------------------------

def format_killer_experiment_table() -> str:
    """Run the killer experiment and return a clean markdown table.

    Uses reduced parameters for speed (n_repeats=5, n_cycles=25).

    Returns:
        Markdown-formatted table string.
    """
    result = run_simulated_discovery_experiment(
        n_repeats=5,
        n_cycles=25,
        top_pct=5,
        max_pool=150,
        n_universe=400,
    )
    return result["table"]


# ---------------------------------------------------------------------------
# CLI ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("=" * 70)
    print("OligoVoid Killer Experiment: VPA Discovery Efficiency")
    print("=" * 70)
    print()

    # Quick run
    result = run_simulated_discovery_experiment(
        n_repeats=3,
        n_cycles=20,
        top_pct=5,
    )

    print(result["table"])
    print()
    print(f"Elapsed: {result['elapsed_seconds']}s")
    print()

    # Print pairwise significance
    print("Pairwise significance (VPA vs others):")
    for key, val in result["pairwise_significance"].items():
        print(
            f"  {key}: diff={val['mean_diff']:.1f}, "
            f"p={val['p_value']:.4f}, d={val['effect_size']:.2f}"
        )
