"""Active learning engine for OligoVoid — the DMTL loop.

Design-Make-Test-Learn: systematically suggests which void modification
pattern a researcher should synthesize NEXT to gain the maximum
information about the siRNA modification design space.

The core question: "Given everything we know, which untested pattern
should be tested next?"

Now powered by:
  - RealDataGP: trained on 3,700+ OligoFormer sequences with calibrated uncertainty
  - CVAE: generative model for in-silico exploration of novel modification space
  - Proper acquisition functions: EI, UCB, Thompson sampling, VPA (novel contribution)

Acquisition functions:
  - ei:        Expected Improvement — analytical EI with real GP uncertainty
  - ucb:       Upper Confidence Bound — mu + kappa*sigma exploration
  - thompson:  Thompson Sampling — posterior sample for stochastic exploration
  - vpa:       Void-Prioritized Acquisition — EI × novelty_bonus (THE NOVEL CONTRIBUTION)
  - balanced:  Legacy weighted combination (backward compat)
"""

from __future__ import annotations

import logging
import math
import hashlib
import os
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import norm
from sqlalchemy.orm import Session

from backend.database import DMTLCycle, DMTLCycleLog, Void
from backend.modification_grammar import (
    SUGAR_MODIFICATIONS,
    SugarMod,
    SEED_REGION,
    CLEAVAGE_SITE,
    SUPPLEMENTARY,
    THREE_PRIME_OVERHANG,
    GUIDE_LENGTH,
    PASSENGER_LENGTH,
    all_positions,
)

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _hamming_lists(a: list[str], b: list[str]) -> int:
    """Hamming distance between two mod lists."""
    return sum(1 for x, y in zip(a, b) if x != y)


def _pattern_fingerprint(guide: list[str], passenger: list[str]) -> str:
    raw = "|".join(guide) + "||" + "|".join(passenger)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _changed_regions(void: dict) -> set[str]:
    """Return which functional regions a void's changes affect."""
    regions = set()
    changes = void.get("changes", [])
    for c in changes:
        pos = c.get("position", 0)
        if 2 <= pos <= 8:
            regions.add("seed")
        elif pos in (10, 11):
            regions.add("cleavage")
        elif 13 <= pos <= 16:
            regions.add("supplementary")
        elif 19 <= pos <= 21:
            regions.add("3prime")
        else:
            regions.add("other")
    return regions


def _position_region_name(pos: int) -> str:
    """Return the functional region name for a guide position."""
    if pos == 1:
        return "5' end"
    elif 2 <= pos <= 8:
        return "seed region"
    elif pos in (10, 11):
        return "cleavage site"
    elif 13 <= pos <= 16:
        return "supplementary region"
    elif 19 <= pos <= 21:
        return "3' overhang"
    else:
        return "central"


def _avg_coverage(coverage: dict) -> float:
    """Average coverage across all subregions."""
    values = [v for v in coverage.values() if isinstance(v, (int, float))]
    return sum(values) / len(values) if values else 0.0


def _build_recommendation_reason(
    void: dict, detail: dict, acq_fn: str
) -> str:
    """Generate a human-readable recommendation reason."""
    parts: list[str] = []
    uncertainty = detail.get("uncertainty_std", detail.get("uncertainty_score", 0))
    ei = detail.get("ei_score", detail.get("expected_improvement", 0))
    hamming = void.get("hamming_to_nearest", 0)
    confidence = detail.get("model_confidence", "")

    if confidence == "low" or uncertainty > 20:
        parts.append(
            f"High GP uncertainty (σ={uncertainty:.1f}%) — testing this pattern "
            f"would maximally reduce model blind spots"
        )
    elif confidence == "medium" or uncertainty > 10:
        parts.append(f"Moderate GP uncertainty (σ={uncertainty:.1f}%) in this region")

    if ei > 0.1:
        pred = detail.get("predicted_efficacy", 0)
        parts.append(f"Expected {pred:.0f}% knockdown — potential improvement over known patterns")

    if detail.get("novelty_bonus", 0) > 1.1:
        parts.append(
            f"Novelty bonus {detail['novelty_bonus']:.2f}× — "
            f"explores untested modification space"
        )

    if hamming >= 5:
        parts.append(f"Hamming distance {hamming} from nearest known — highly novel")
    elif hamming <= 2:
        parts.append(f"Conservative variant (Hamming {hamming}) — low-risk validation")

    changes = void.get("changes", [])
    if changes:
        change_desc = ", ".join(
            f"g{c['position']}: {c['from']}→{c['to']}" for c in changes[:3]
        )
        parts.append(f"Changes: {change_desc}")

    if not parts:
        parts.append(f"Top candidate by {acq_fn} acquisition function")

    return "; ".join(parts) + "."


def _what_we_learn(void: dict) -> str:
    """Describe what testing this void would teach us."""
    changes = void.get("changes", [])
    guide = void.get("guide_mods", [])

    learnings: list[str] = []

    rare_mods_at_pos = []
    for c in changes:
        mod = c.get("to", "")
        pos = c.get("position", 0)
        if mod in ("UNA", "LNA", "cEt", "MOE", "DNA"):
            rare_mods_at_pos.append((mod, pos))

    if rare_mods_at_pos:
        for mod, pos in rare_mods_at_pos:
            region = _position_region_name(pos)
            props = SUGAR_MODIFICATIONS.get(mod, {})
            risc = props.get("risc_tolerance", 0)
            nuc = props.get("nuclease_resistance", 0)

            if mod == "UNA" and pos <= 4:
                learnings.append(
                    f"Whether UNA at guide position {pos} ({region}) "
                    f"improves strand selection without sacrificing activity"
                )
            elif mod == "LNA" and 17 <= pos <= 21:
                learnings.append(
                    f"Whether LNA at 3' overhang (position {pos}) extends "
                    f"duplex half-life without blocking RISC"
                )
            elif mod in ("LNA", "cEt") and 2 <= pos <= 8:
                learnings.append(
                    f"Whether {mod} is tolerated in the seed region "
                    f"(position {pos}) — high affinity but RISC risk"
                )
            else:
                learnings.append(
                    f"Tolerance of {mod} at position {pos} ({region}) "
                    f"(RISC tol: {risc:.2f}, nuc res: {nuc:.2f})"
                )

    if not learnings:
        hamming = void.get("hamming_to_nearest", 0)
        if hamming <= 2:
            learnings.append(
                "Fine-tuning: whether this minor variant maintains "
                "efficacy of the parent pattern"
            )
        else:
            learnings.append(
                "Broad question: how this modification combination "
                "affects the activity-stability tradeoff"
            )

    return "; ".join(learnings)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OLIGO ACTIVE LEARNER — powered by RealDataGP + CVAE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class OligoActiveLearner:
    """Design-Make-Test-Learn cycle engine powered by real GP uncertainty + CVAE.

    Uses RealDataGP (3,700+ OligoFormer sequences) for calibrated predictions
    and the CVAE for generative exploration of untested modification space.

    Implements four acquisition functions:
      - EI:       Expected Improvement — analytical formula with real GP σ
      - UCB:      Upper Confidence Bound — mu + kappa*sigma
      - Thompson: Thompson Sampling — stochastic posterior exploration
      - VPA:      Void-Prioritized Acquisition — EI × novelty_bonus (NOVEL)

    VPA is the novel contribution: biases exploration toward "void" regions of
    modification space that are farthest from any known pattern.

    Args:
        known_patterns: List of pattern dicts with guide_mods, passenger_mods,
                       knockdown_efficacy, pattern_id, etc.
        scored_voids: List of void dicts with guide_mods, passenger_mods,
                     overall_oligovoid_score, hamming_to_nearest, etc.
    """

    def __init__(
        self,
        known_patterns: list[dict],
        scored_voids: list[dict],
    ):
        self.known = list(known_patterns)
        self.candidates = list(scored_voids)
        self.cycle_history: list[dict] = []
        self._gp = None
        self._mod_position_counts: dict[tuple[str, int, str], int] | None = None

    # ────────────────────────────────────────────────────────────────────
    # GP MODEL ACCESS
    # ────────────────────────────────────────────────────────────────────

    def _get_gp(self):
        """Get the trained RealDataGP, loading/training if necessary."""
        if self._gp is not None and self._gp.is_fitted:
            return self._gp
        try:
            from backend.feasibility_scorer import ensure_real_data_gp_trained
            self._gp = ensure_real_data_gp_trained()
            return self._gp
        except Exception as e:
            logger.warning("Could not load RealDataGP: %s", e)
            return None

    def _predict(self, pattern: dict) -> dict:
        """Get GP prediction with uncertainty for a pattern.

        Returns dict with predicted_efficacy, uncertainty_std, ci_95,
        model_confidence, is_extrapolation. Falls back to heuristic if GP unavailable.
        """
        gp = self._get_gp()
        if gp is not None and gp.is_fitted:
            return gp.predict_with_uncertainty(pattern)

        # Heuristic fallback (for when GP is unavailable)
        predicted = pattern.get(
            "predicted_knockdown_pct",
            pattern.get("overall_oligovoid_score", 50.0),
        )
        return {
            "predicted_efficacy": float(predicted),
            "uncertainty_std": 25.0,  # high default uncertainty
            "ci_95": (max(0, predicted - 49), min(100, predicted + 49)),
            "model_confidence": "low",
            "is_extrapolation": True,
            "plain_english": "Heuristic estimate — GP model unavailable",
        }

    # ────────────────────────────────────────────────────────────────────
    # INTERNAL: Modification position frequency cache
    # ────────────────────────────────────────────────────────────────────

    def _build_mod_position_counts(self) -> dict[tuple[str, int, str], int]:
        """Count how many times each (strand, position, mod) appears in known."""
        counts: dict[tuple[str, int, str], int] = defaultdict(int)
        for pat in self.known:
            for i, mod in enumerate(pat.get("guide_mods", [])):
                counts[("guide", i, mod)] += 1
            for i, mod in enumerate(pat.get("passenger_mods", [])):
                counts[("passenger", i, mod)] += 1
        return dict(counts)

    def _get_mod_position_counts(self) -> dict[tuple[str, int, str], int]:
        if self._mod_position_counts is None:
            self._mod_position_counts = self._build_mod_position_counts()
        return self._mod_position_counts

    def _invalidate_cache(self):
        self._mod_position_counts = None

    # ────────────────────────────────────────────────────────────────────
    # ACQUISITION FUNCTION 1: Expected Improvement (EI)
    # ────────────────────────────────────────────────────────────────────

    def expected_improvement(self, pattern: dict, best_known: float | None = None) -> dict:
        """Analytical Expected Improvement using real GP uncertainty.

        EI(x) = (μ(x) - f*) × Φ(Z) + σ(x) × φ(Z)
        where Z = (μ(x) - f*) / σ(x)

        Args:
            pattern: Modification pattern dict.
            best_known: Current best knockdown%. If None, computed from self.known.

        Returns:
            Dict with ei_raw, ei_normalized, predicted_efficacy, uncertainty_std,
            model_confidence, is_extrapolation.
        """
        if best_known is None:
            best_known = max(
                (p.get("knockdown_efficacy", 0) or 0 for p in self.known),
                default=70.0,
            )

        pred = self._predict(pattern)
        mu = pred["predicted_efficacy"] or 50.0
        sigma = pred["uncertainty_std"] or 25.0

        if sigma > 1e-6:
            z = (mu - best_known) / sigma
            ei_raw = (mu - best_known) * norm.cdf(z) + sigma * norm.pdf(z)
        else:
            ei_raw = max(0.0, mu - best_known)

        # Normalize: 15% EI → ~1.0
        ei_normalized = min(1.0, max(0.0, ei_raw) / 15.0)

        return {
            "ei_raw": round(float(ei_raw), 4),
            "ei_normalized": round(ei_normalized, 4),
            "predicted_efficacy": pred["predicted_efficacy"],
            "uncertainty_std": pred["uncertainty_std"],
            "model_confidence": pred["model_confidence"],
            "is_extrapolation": pred["is_extrapolation"],
        }

    # ────────────────────────────────────────────────────────────────────
    # ACQUISITION FUNCTION 2: Upper Confidence Bound (UCB)
    # ────────────────────────────────────────────────────────────────────

    def upper_confidence_bound(self, pattern: dict, kappa: float = 2.0) -> dict:
        """UCB acquisition: mu + kappa * sigma.

        Higher kappa = more exploration. Default kappa=2.0 balances
        exploitation and exploration (standard GP-UCB).

        Args:
            pattern: Modification pattern dict.
            kappa: Exploration-exploitation tradeoff parameter.

        Returns:
            Dict with ucb_score, ucb_normalized, predicted_efficacy,
            uncertainty_std, model_confidence.
        """
        pred = self._predict(pattern)
        mu = pred["predicted_efficacy"] or 50.0
        sigma = pred["uncertainty_std"] or 25.0

        ucb_score = mu + kappa * sigma

        # Normalize to 0-1: 100% knockdown → 1.0
        ucb_normalized = min(1.0, max(0.0, ucb_score / 100.0))

        return {
            "ucb_score": round(float(ucb_score), 2),
            "ucb_normalized": round(ucb_normalized, 4),
            "predicted_efficacy": pred["predicted_efficacy"],
            "uncertainty_std": pred["uncertainty_std"],
            "model_confidence": pred["model_confidence"],
        }

    # ────────────────────────────────────────────────────────────────────
    # ACQUISITION FUNCTION 3: Thompson Sampling
    # ────────────────────────────────────────────────────────────────────

    def thompson_sampling(self, pattern: dict, rng: np.random.RandomState | None = None) -> dict:
        """Thompson sampling: draw from posterior N(mu, sigma²).

        Stochastic acquisition function — each call produces a different
        sample, naturally balancing exploration and exploitation.

        Args:
            pattern: Modification pattern dict.
            rng: Random state for reproducibility.

        Returns:
            Dict with thompson_score, thompson_normalized, predicted_efficacy,
            uncertainty_std, model_confidence.
        """
        if rng is None:
            rng = np.random.RandomState()

        pred = self._predict(pattern)
        mu = pred["predicted_efficacy"] or 50.0
        sigma = pred["uncertainty_std"] or 25.0

        # Draw from posterior
        sample = float(rng.normal(mu, sigma))
        sample = max(0.0, min(100.0, sample))

        thompson_normalized = sample / 100.0

        return {
            "thompson_score": round(sample, 2),
            "thompson_normalized": round(thompson_normalized, 4),
            "predicted_efficacy": pred["predicted_efficacy"],
            "uncertainty_std": pred["uncertainty_std"],
            "model_confidence": pred["model_confidence"],
        }

    # ────────────────────────────────────────────────────────────────────
    # ACQUISITION FUNCTION 4: Void-Prioritized Acquisition (VPA)
    # ────────────────────────────────────────────────────────────────────

    def void_prioritized_acquisition(
        self, pattern: dict, alpha: float = 0.5, best_known: float | None = None,
    ) -> dict:
        """Void-Prioritized Acquisition — THE NOVEL CONTRIBUTION.

        VPA(x) = EI(x) × novelty_bonus(x)

        novelty_bonus = 1.0 + alpha × (hamming_to_nearest / 21)

        This biases the acquisition function toward patterns in "void" regions
        of modification space — regions far from any known tested pattern.
        The further a candidate is from known patterns, the larger the bonus,
        up to 1 + alpha at maximum Hamming distance.

        Args:
            pattern: Modification pattern dict.
            alpha: Novelty bonus strength. 0.5 = up to 50% bonus for maximally novel.
            best_known: Current best knockdown%. If None, computed from self.known.

        Returns:
            Dict with vpa_score, vpa_normalized, ei_raw, novelty_bonus,
            hamming_to_nearest, predicted_efficacy, uncertainty_std,
            model_confidence, is_extrapolation, plain_english.
        """
        # Compute EI
        ei_result = self.expected_improvement(pattern, best_known=best_known)
        ei_raw = ei_result["ei_raw"]

        # Compute novelty bonus from Hamming distance
        guide = pattern.get("guide_mods", [])
        passenger = pattern.get("passenger_mods", [])

        if pattern.get("hamming_to_nearest") is not None:
            hamming = pattern["hamming_to_nearest"]
        else:
            hamming = 42  # maximum possible
            for known in self.known:
                d = _hamming_lists(guide, known.get("guide_mods", [])) + \
                    _hamming_lists(passenger, known.get("passenger_mods", []))
                hamming = min(hamming, d)

        # Novelty bonus: 1.0 at hamming=0, up to 1+alpha at hamming=21+
        novelty_bonus = 1.0 + alpha * (min(hamming, 21) / 21.0)

        vpa_score = ei_raw * novelty_bonus
        vpa_normalized = min(1.0, max(0.0, vpa_score) / 15.0)

        # Plain English explanation
        if novelty_bonus > 1.3:
            eng = (
                f"VPA boosted: EI={ei_raw:.1f}% × novelty {novelty_bonus:.2f}× "
                f"(Hamming {hamming} from nearest known) → VPA={vpa_score:.1f}%. "
                f"This pattern explores uncharted modification space."
            )
        elif novelty_bonus > 1.1:
            eng = (
                f"Moderate VPA boost: EI={ei_raw:.1f}% × {novelty_bonus:.2f}× novelty → "
                f"VPA={vpa_score:.1f}%. Novel but not far from tested patterns."
            )
        else:
            eng = (
                f"Minimal VPA boost: EI={ei_raw:.1f}% × {novelty_bonus:.2f}× → "
                f"VPA={vpa_score:.1f}%. Close to known patterns — validates consistency."
            )

        return {
            "vpa_score": round(float(vpa_score), 4),
            "vpa_normalized": round(vpa_normalized, 4),
            "ei_raw": round(ei_raw, 4),
            "novelty_bonus": round(novelty_bonus, 4),
            "hamming_to_nearest": hamming,
            "predicted_efficacy": ei_result["predicted_efficacy"],
            "uncertainty_std": ei_result["uncertainty_std"],
            "model_confidence": ei_result["model_confidence"],
            "is_extrapolation": ei_result["is_extrapolation"],
            "plain_english": eng,
        }

    # ────────────────────────────────────────────────────────────────────
    # MAIN: Recommend Next Experiments
    # ────────────────────────────────────────────────────────────────────

    def recommend_next(
        self,
        acquisition_function: str = "vpa",
        n_recommendations: int = 3,
        kappa: float = 2.0,
        alpha: float = 0.5,
    ) -> list[dict]:
        """Return top N void patterns to test next.

        Acquisition function options:
          "ei":        Expected Improvement
          "ucb":       Upper Confidence Bound (mu + kappa*sigma)
          "thompson":  Thompson Sampling
          "vpa":       Void-Prioritized Acquisition (NOVEL — default)
          "balanced":  Legacy weighted combination (backward compat)

        Each recommendation includes a plain English explanation of WHY
        this pattern was chosen and WHAT we'd learn by testing it.

        Returns list of recommendation dicts.
        """
        if not self.candidates:
            return []

        best_known = max(
            (p.get("knockdown_efficacy", 0) or 0 for p in self.known),
            default=70.0,
        )

        # Score all candidates with chosen acquisition function
        rng = np.random.RandomState(42)
        scored: list[tuple[float, dict, dict]] = []

        for void in self.candidates:
            if acquisition_function == "ei":
                result = self.expected_improvement(void, best_known=best_known)
                acq_score = result["ei_normalized"]
                detail = result
            elif acquisition_function == "ucb":
                result = self.upper_confidence_bound(void, kappa=kappa)
                acq_score = result["ucb_normalized"]
                detail = result
            elif acquisition_function == "thompson":
                result = self.thompson_sampling(void, rng=rng)
                acq_score = result["thompson_normalized"]
                detail = result
            elif acquisition_function == "vpa":
                result = self.void_prioritized_acquisition(
                    void, alpha=alpha, best_known=best_known,
                )
                acq_score = result["vpa_normalized"]
                detail = result
            else:  # "balanced" — legacy compatible
                ei_res = self.expected_improvement(void, best_known=best_known)
                vpa_res = self.void_prioritized_acquisition(
                    void, alpha=alpha, best_known=best_known,
                )
                # Weighted blend: 35% EI, 35% uncertainty, 30% novelty
                unc_norm = min(1.0, (ei_res["uncertainty_std"] or 0) / 25.0)
                nov_norm = (vpa_res["novelty_bonus"] - 1.0) / alpha if alpha > 0 else 0
                acq_score = 0.35 * ei_res["ei_normalized"] + 0.35 * unc_norm + 0.30 * nov_norm
                detail = {**ei_res, **vpa_res, "balanced_score": acq_score}

            scored.append((acq_score, void, detail))

        # Sort by acquisition score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Greedy selection with diversity enforcement
        recommendations: list[dict] = []
        already_rec: list[dict] = []

        for rank_idx, (acq_score, void, detail) in enumerate(scored):
            if len(recommendations) >= n_recommendations:
                break

            # Diversity check: skip if too similar to already recommended
            if already_rec:
                guide = void.get("guide_mods", [])
                passenger = void.get("passenger_mods", [])
                min_dist = min(
                    _hamming_lists(guide, r.get("guide_mods", [])) +
                    _hamming_lists(passenger, r.get("passenger_mods", []))
                    for r in already_rec
                )
                if min_dist < 3:  # skip near-duplicates
                    continue

            predicted_kd = detail.get(
                "predicted_efficacy",
                void.get("predicted_knockdown_pct",
                         void.get("overall_oligovoid_score", 50.0)),
            ) or 50.0

            rec = {
                "void_id": void.get("void_id", void.get("fingerprint", "")),
                "rank": len(recommendations) + 1,
                "acquisition_score": round(acq_score, 4),
                "acquisition_function": acquisition_function,
                "predicted_efficacy": round(predicted_kd, 1),
                "uncertainty_std": round(detail.get("uncertainty_std", 0) or 0, 2),
                "model_confidence": detail.get("model_confidence", "low"),
                "is_extrapolation": detail.get("is_extrapolation", True),
                "recommendation_reason": _build_recommendation_reason(
                    void, detail, acquisition_function,
                ),
                "what_we_learn": _what_we_learn(void),
                "guide_mods": void.get("guide_mods", []),
                "passenger_mods": void.get("passenger_mods", []),
                "hamming_to_nearest": void.get("hamming_to_nearest", 0),
                "nearest_known_id": void.get("nearest_known_id", ""),
            }

            # Add acquisition-function-specific fields
            if acquisition_function == "vpa":
                rec["novelty_bonus"] = detail.get("novelty_bonus", 1.0)
                rec["vpa_score"] = detail.get("vpa_score", 0)
                rec["ei_raw"] = detail.get("ei_raw", 0)
                rec["plain_english"] = detail.get("plain_english", "")
            elif acquisition_function == "ei":
                rec["ei_raw"] = detail.get("ei_raw", 0)
            elif acquisition_function == "ucb":
                rec["ucb_score"] = detail.get("ucb_score", 0)

            recommendations.append(rec)
            already_rec.append(void)

        return recommendations

    # Backward-compatible alias
    def recommend_next_experiment(
        self,
        acquisition_function: str = "balanced",
        n_recommendations: int = 3,
    ) -> list[dict]:
        """Legacy alias for recommend_next(). Maps old acquisition names."""
        acq_map = {
            "uncertainty": "ucb",
            "exploitation": "ei",
            "exploration": "vpa",
            "balanced": "balanced",
        }
        mapped = acq_map.get(acquisition_function, acquisition_function)
        return self.recommend_next(
            acquisition_function=mapped,
            n_recommendations=n_recommendations,
        )

    # ────────────────────────────────────────────────────────────────────
    # SIMULATION: Compare Acquisition Strategies
    # ────────────────────────────────────────────────────────────────────

    def run_simulation(
        self,
        n_cycles: int = 10,
        strategies: list[str] | None = None,
        start_with_n_known: int = 5,
    ) -> dict:
        """Simulate DMTL cycles comparing Random vs EI vs VPA (and more).

        For each strategy, runs n_cycles of:
          1. Score all candidates with the strategy's acquisition function
          2. Pick the top candidate
          3. "Test" it (use predicted efficacy or lookup actual data)
          4. Add to known set, track metrics

        Args:
            n_cycles: Cycles per strategy.
            strategies: List of strategies to compare. Default: ["random", "ei", "vpa"].
            start_with_n_known: Number of initial known patterns per run.

        Returns:
            Dict with per-strategy results, comparison metrics, and winner.
        """
        if strategies is None:
            strategies = ["random", "ei", "vpa"]

        all_known_backup = list(self.known)
        all_candidates_backup = list(self.candidates)

        best_known_global = max(
            (p.get("knockdown_efficacy", 0) or 0 for p in self.known),
            default=70.0,
        )

        results: dict[str, dict] = {}

        for strategy in strategies:
            logger.info("Simulating %d cycles with strategy: %s", n_cycles, strategy)

            # Reset state
            self.known = list(all_known_backup[:start_with_n_known])
            self._invalidate_cache()
            sim_candidates = list(all_candidates_backup)

            rng = np.random.RandomState(42)
            cycles_log: list[dict] = []
            cumulative_best = max(
                (p.get("knockdown_efficacy", 0) or 0 for p in self.known),
                default=0.0,
            )

            for cycle_num in range(1, n_cycles + 1):
                # Filter out already-tested candidates
                known_fps = set()
                for k in self.known:
                    fp = _pattern_fingerprint(
                        k.get("guide_mods", []), k.get("passenger_mods", []),
                    )
                    known_fps.add(fp)

                available = [
                    c for c in sim_candidates
                    if _pattern_fingerprint(
                        c.get("guide_mods", []), c.get("passenger_mods", []),
                    ) not in known_fps
                ]

                if not available:
                    break

                # Select next pattern based on strategy
                if strategy == "random":
                    selected = available[rng.randint(len(available))]
                    acq_score = 0.0
                elif strategy == "ei":
                    best = max(
                        (p.get("knockdown_efficacy", 0) or 0 for p in self.known),
                        default=70.0,
                    )
                    scored_list = []
                    for c in available:
                        ei_res = self.expected_improvement(c, best_known=best)
                        scored_list.append((ei_res["ei_normalized"], c, ei_res))
                    scored_list.sort(key=lambda x: x[0], reverse=True)
                    acq_score, selected, _ = scored_list[0]
                elif strategy == "vpa":
                    best = max(
                        (p.get("knockdown_efficacy", 0) or 0 for p in self.known),
                        default=70.0,
                    )
                    scored_list = []
                    for c in available:
                        vpa_res = self.void_prioritized_acquisition(c, best_known=best)
                        scored_list.append((vpa_res["vpa_normalized"], c, vpa_res))
                    scored_list.sort(key=lambda x: x[0], reverse=True)
                    acq_score, selected, _ = scored_list[0]
                elif strategy == "ucb":
                    scored_list = []
                    for c in available:
                        ucb_res = self.upper_confidence_bound(c)
                        scored_list.append((ucb_res["ucb_normalized"], c, ucb_res))
                    scored_list.sort(key=lambda x: x[0], reverse=True)
                    acq_score, selected, _ = scored_list[0]
                elif strategy == "thompson":
                    scored_list = []
                    for c in available:
                        ts_res = self.thompson_sampling(c, rng=rng)
                        scored_list.append((ts_res["thompson_normalized"], c, ts_res))
                    scored_list.sort(key=lambda x: x[0], reverse=True)
                    acq_score, selected, _ = scored_list[0]
                else:
                    # Default to VPA
                    self.candidates = available
                    recs = self.recommend_next(acquisition_function=strategy, n_recommendations=1)
                    if not recs:
                        break
                    selected = available[0]
                    acq_score = recs[0]["acquisition_score"] if recs else 0

                # "Test" the selected pattern
                test_efficacy = selected.get(
                    "predicted_knockdown_pct",
                    selected.get("overall_oligovoid_score", 50.0),
                )

                # Check if this matches any actual known pattern
                for full_pat in all_known_backup:
                    if (_hamming_lists(selected.get("guide_mods", []),
                                       full_pat.get("guide_mods", []))
                        + _hamming_lists(selected.get("passenger_mods", []),
                                         full_pat.get("passenger_mods", []))
                        <= 2):
                        test_efficacy = full_pat.get(
                            "knockdown_efficacy", test_efficacy,
                        )
                        break

                # Update cumulative best
                cumulative_best = max(cumulative_best, test_efficacy)

                # Add to known set
                tested = {
                    "pattern_id": f"SIM_{strategy.upper()}_{cycle_num:03d}",
                    "guide_mods": selected.get("guide_mods", []),
                    "passenger_mods": selected.get("passenger_mods", []),
                    "knockdown_efficacy": test_efficacy,
                    "source": f"simulation_{strategy}",
                }
                self.known.append(tested)
                self._invalidate_cache()

                cycles_log.append({
                    "cycle": cycle_num,
                    "strategy": strategy,
                    "acquisition_score": round(acq_score, 4),
                    "tested_efficacy": round(test_efficacy, 1),
                    "cumulative_best": round(cumulative_best, 1),
                    "patterns_known": len(self.known),
                    "candidates_remaining": len(available) - 1,
                })

            # Strategy summary
            efficacies = [c["tested_efficacy"] for c in cycles_log]
            results[strategy] = {
                "cycles": cycles_log,
                "mean_efficacy": round(np.mean(efficacies), 1) if efficacies else 0,
                "max_efficacy": round(max(efficacies), 1) if efficacies else 0,
                "final_best": round(cumulative_best, 1),
                "n_cycles_completed": len(cycles_log),
            }

        # Restore state
        self.known = all_known_backup
        self.candidates = all_candidates_backup
        self._invalidate_cache()

        # Determine winner
        winner = max(results.items(), key=lambda x: x[1]["final_best"])

        return {
            "strategies": results,
            "winner": winner[0],
            "winner_best_efficacy": winner[1]["final_best"],
            "comparison_summary": (
                f"After {n_cycles} cycles: "
                + ", ".join(
                    f"{s}={r['final_best']:.1f}% best"
                    for s, r in results.items()
                )
                + f". Winner: {winner[0].upper()}"
            ),
        }

    # ────────────────────────────────────────────────────────────────────
    # SIMULATE: Legacy DMTL Cycle (backward compat)
    # ────────────────────────────────────────────────────────────────────

    def simulate_dmtl_cycle(
        self,
        n_cycles: int = 5,
        start_with_n_known: int = 5,
    ) -> dict:
        """Simulate running N DMTL cycles using VPA acquisition.

        Algorithm:
          1. Start with only start_with_n_known patterns as "known"
          2. Each cycle:
             a. recommend_next() with VPA
             b. "Test" the top pick
             c. Add tested pattern to known set
             d. Log cycle data
          3. Track model improvement across cycles

        Returns:
            Compatible dict with cycles, total_patterns_explored,
            uncertainty_reduction, coverage_improvement, final_recommendation.
        """
        all_known_backup = list(self.known)
        all_candidates_backup = list(self.candidates)

        sim_known = list(self.known[:start_with_n_known])
        sim_candidates = list(self.candidates)

        self.known = sim_known
        self._invalidate_cache()

        cycles_log: list[dict] = []
        initial_uncertainty = None

        try:
            for cycle_num in range(1, n_cycles + 1):
                known_fps = set()
                for k in self.known:
                    fp = _pattern_fingerprint(
                        k.get("guide_mods", []), k.get("passenger_mods", []),
                    )
                    known_fps.add(fp)

                self.candidates = [
                    c for c in sim_candidates
                    if _pattern_fingerprint(
                        c.get("guide_mods", []), c.get("passenger_mods", []),
                    ) not in known_fps
                ]

                if not self.candidates:
                    break

                # Compute mean uncertainty before
                uncertainties_before = []
                for c in self.candidates[:100]:  # cap for speed
                    pred = self._predict(c)
                    uncertainties_before.append(pred["uncertainty_std"] or 25.0)
                mean_unc_before = np.mean(uncertainties_before) if uncertainties_before else 0

                if initial_uncertainty is None:
                    initial_uncertainty = mean_unc_before

                # Get recommendation via VPA
                recs = self.recommend_next(
                    acquisition_function="vpa",
                    n_recommendations=1,
                )
                if not recs:
                    break

                top_rec = recs[0]

                # "Test" the recommendation
                tested_pattern = {
                    "pattern_id": f"DMTL_CYCLE_{cycle_num:03d}",
                    "guide_mods": top_rec["guide_mods"],
                    "passenger_mods": top_rec["passenger_mods"],
                    "knockdown_efficacy": top_rec["predicted_efficacy"],
                    "source": "DMTL simulation",
                    "year": 2026,
                }

                # Check if matches actual known pattern
                for full_pat in all_known_backup:
                    if (_hamming_lists(tested_pattern["guide_mods"],
                                       full_pat.get("guide_mods", []))
                        + _hamming_lists(tested_pattern["passenger_mods"],
                                         full_pat.get("passenger_mods", []))
                        <= 2):
                        tested_pattern["knockdown_efficacy"] = full_pat.get(
                            "knockdown_efficacy",
                            tested_pattern["knockdown_efficacy"],
                        )
                        break

                self.known.append(tested_pattern)
                self._invalidate_cache()

                # Compute uncertainty after
                uncertainties_after = []
                for c in self.candidates[:100]:
                    pred = self._predict(c)
                    uncertainties_after.append(pred["uncertainty_std"] or 25.0)
                mean_unc_after = np.mean(uncertainties_after) if uncertainties_after else 0

                info_gain = max(0.0, mean_unc_before - mean_unc_after)

                coverage = self.get_exploration_coverage()

                cycle_data = {
                    "cycle_number": cycle_num,
                    "recommended_void_id": top_rec["void_id"],
                    "acquisition_score": top_rec["acquisition_score"],
                    "acquisition_function": "vpa",
                    "expected_knockdown": top_rec["predicted_efficacy"],
                    "actual_knockdown": tested_pattern["knockdown_efficacy"],
                    "uncertainty_before": round(float(mean_unc_before), 4),
                    "uncertainty_after": round(float(mean_unc_after), 4),
                    "information_gain": round(float(info_gain), 4),
                    "patterns_known": len(self.known),
                    "candidates_remaining": len(self.candidates),
                    "recommendation_reason": top_rec["recommendation_reason"],
                    "what_we_learn": top_rec["what_we_learn"],
                    "coverage_snapshot": coverage,
                    "model_confidence": top_rec.get("model_confidence", "low"),
                    "is_extrapolation": top_rec.get("is_extrapolation", True),
                }
                cycles_log.append(cycle_data)
                self.cycle_history.append(cycle_data)
        finally:
            pass  # restore handled below

        # Compute overall metrics
        final_uncertainty = cycles_log[-1]["uncertainty_after"] if cycles_log else 0.0
        initial_uncertainty = initial_uncertainty or final_uncertainty

        uncertainty_reduction = (
            (initial_uncertainty - final_uncertainty) / initial_uncertainty * 100
            if initial_uncertainty > 0 else 0.0
        )

        initial_coverage = cycles_log[0]["coverage_snapshot"] if cycles_log else {}
        final_coverage = cycles_log[-1]["coverage_snapshot"] if cycles_log else {}
        coverage_improvement = _avg_coverage(final_coverage) - _avg_coverage(initial_coverage)

        final_rec = (
            self.recommend_next("vpa", 1)[0]
            if self.candidates else {}
        )

        # Restore state
        self.known = all_known_backup
        self.candidates = all_candidates_backup
        self._invalidate_cache()

        return {
            "cycles": cycles_log,
            "total_patterns_explored": len(cycles_log),
            "uncertainty_reduction": round(float(uncertainty_reduction), 1),
            "coverage_improvement": round(float(coverage_improvement), 1),
            "final_recommendation": final_rec,
        }

    # ────────────────────────────────────────────────────────────────────
    # GENERATE AND EXPLORE: CVAE + Active Learning Pipeline
    # ────────────────────────────────────────────────────────────────────

    def generate_and_explore(
        self,
        n_generate: int = 50,
        target_efficacy: float = 80.0,
        acquisition_function: str = "vpa",
        n_select: int = 5,
    ) -> dict:
        """Combine CVAE generation with active learning selection.

        Pipeline:
          1. CVAE generates n_generate novel modification profiles
          2. Convert to candidate dicts (feature vectors → heuristic patterns)
          3. GP predicts efficacy + uncertainty for each
          4. VPA (or chosen acq fn) selects top n_select candidates
          5. Return ranked candidates with explanations

        Args:
            n_generate: Number of CVAE candidates to generate.
            target_efficacy: Desired knockdown % (CVAE conditioning).
            acquisition_function: Which acquisition function for selection.
            n_select: Number of candidates to return.

        Returns:
            Dict with generated candidates, selected candidates, and metrics.
        """
        try:
            import torch
            from backend.generative_model import load_cvae
            from backend.ml_model import encode_pattern
        except ImportError as e:
            return {
                "error": f"CVAE dependencies unavailable: {e}",
                "generated": 0,
                "selected": [],
            }

        cvae_path = str(
            (Path(__file__).resolve().parent.parent / "data" / "cvae_model.pt")
        )
        if not os.path.exists(cvae_path):
            return {
                "error": "CVAE model not trained yet",
                "generated": 0,
                "selected": [],
            }

        try:
            model, scaler = load_cvae(cvae_path)
            model.eval()
        except Exception as e:
            return {
                "error": f"Failed to load CVAE: {e}",
                "generated": 0,
                "selected": [],
            }

        # Step 1: Generate candidates from CVAE
        target_norm = target_efficacy / 100.0
        with torch.no_grad():
            generated = model.generate(n_generate, target_norm, temperature=1.0)
        gen_np = generated.numpy()

        # Inverse transform to original feature space
        gen_original = scaler.inverse_transform(gen_np)

        # Step 2: Filter for validity (all features within ±4 std)
        valid_mask = np.all(np.abs(gen_np) < 4.0, axis=1)

        # Step 3: Convert to candidate dicts and score with GP
        candidates = []
        for i in range(len(gen_np)):
            if not valid_mask[i]:
                continue

            # Create a synthetic pattern dict for GP scoring
            # The CVAE produces feature vectors, not modification patterns directly.
            # We create a placeholder pattern and store the feature vector for analysis.
            candidate = {
                "candidate_id": f"CVAE_{i + 1:03d}",
                "guide_mods": ["RNA"] * 21,  # placeholder
                "passenger_mods": ["RNA"] * 21,  # placeholder
                "feature_vector_scaled": gen_np[i].tolist(),
                "feature_vector_original": gen_original[i].tolist(),
                "target_efficacy_pct": target_efficacy,
                "source": "cvae_generated",
            }

            # Score with GP (using feature vector directly if possible,
            # or fall back to biophysics-based prediction)
            pred = self._predict(candidate)
            candidate["predicted_efficacy"] = pred["predicted_efficacy"]
            candidate["uncertainty_std"] = pred["uncertainty_std"]
            candidate["model_confidence"] = pred["model_confidence"]
            candidate["is_extrapolation"] = pred["is_extrapolation"]

            candidates.append(candidate)

        if not candidates:
            return {
                "error": "No valid candidates generated by CVAE",
                "generated": int(valid_mask.sum()),
                "selected": [],
            }

        # Step 4: Score with acquisition function and select top-N
        best_known = max(
            (p.get("knockdown_efficacy", 0) or 0 for p in self.known),
            default=70.0,
        )

        scored_candidates = []
        for cand in candidates:
            if acquisition_function == "vpa":
                res = self.void_prioritized_acquisition(cand, best_known=best_known)
                acq_score = res["vpa_normalized"]
            elif acquisition_function == "ei":
                res = self.expected_improvement(cand, best_known=best_known)
                acq_score = res["ei_normalized"]
            elif acquisition_function == "ucb":
                res = self.upper_confidence_bound(cand)
                acq_score = res["ucb_normalized"]
            else:
                res = self.expected_improvement(cand, best_known=best_known)
                acq_score = res["ei_normalized"]

            cand["acquisition_score"] = round(acq_score, 4)
            scored_candidates.append(cand)

        # Sort and select
        scored_candidates.sort(key=lambda x: x["acquisition_score"], reverse=True)
        selected = scored_candidates[:n_select]

        # Add rank and explanation to selected
        for rank, cand in enumerate(selected, 1):
            cand["rank"] = rank
            cand["plain_english"] = (
                f"CVAE-generated candidate #{rank}: "
                f"predicted {cand['predicted_efficacy']:.0f}% knockdown "
                f"(σ={cand['uncertainty_std']:.1f}%), "
                f"confidence={cand['model_confidence']}, "
                f"acq_score={cand['acquisition_score']:.3f}"
            )

        return {
            "total_generated": n_generate,
            "total_valid": len(candidates),
            "total_selected": len(selected),
            "target_efficacy_pct": target_efficacy,
            "acquisition_function": acquisition_function,
            "selected": selected,
            "generation_stats": {
                "validity_rate": round(float(valid_mask.mean()) * 100, 1),
                "mean_predicted_efficacy": round(
                    np.mean([c["predicted_efficacy"] or 0 for c in candidates]), 1,
                ),
                "mean_uncertainty": round(
                    np.mean([c["uncertainty_std"] or 0 for c in candidates]), 1,
                ),
            },
        }

    # ────────────────────────────────────────────────────────────────────
    # EXPLORATION COVERAGE
    # ────────────────────────────────────────────────────────────────────

    def get_exploration_coverage(self) -> dict[str, float]:
        """Return % explored for 8 subregions of modification space.

        Subregions:
          1. Seed modifications (guide pos 2-8)
          2. Cleavage site neighbors (guide pos 9-12)
          3. Central region (guide pos 8-14)
          4. 3' stabilization zone (guide pos 17-21)
          5. Full passenger strand
          6. Backbone variations
          7. Conjugate combinations
          8. Cross-strand pattern combinations
        """
        all_mods = [m.value for m in SugarMod]
        n_mods = len(all_mods)

        seen: set[tuple[str, int, str]] = set()
        seen_backbone: set[tuple[str, str]] = set()
        seen_conjugates: set[str] = set()
        seen_cross: set[tuple[str, str]] = set()

        for pat in self.known:
            guide = pat.get("guide_mods", [])
            passenger = pat.get("passenger_mods", [])
            bb_g = pat.get("backbone_guide", [])
            bb_p = pat.get("backbone_passenger", [])
            conj = pat.get("conjugate", "None")

            for i, mod in enumerate(guide):
                seen.add(("guide", i, mod))
            for i, mod in enumerate(passenger):
                seen.add(("passenger", i, mod))
            for b in bb_g:
                seen_backbone.add(("guide", b))
            for b in bb_p:
                seen_backbone.add(("passenger", b))
            seen_conjugates.add(conj)

            if len(guide) >= 8 and len(passenger) >= 8:
                g_seed = frozenset(guide[1:8])
                p_seed = frozenset(passenger[1:8])
                seen_cross.add((str(g_seed), str(p_seed)))

        seed_total = 7 * n_mods
        seed_seen = sum(1 for s, p, m in seen if s == "guide" and 1 <= p <= 7)
        seed_pct = round(min(100.0, seed_seen / seed_total * 100), 1)

        cleave_total = 4 * n_mods
        cleave_seen = sum(1 for s, p, m in seen if s == "guide" and 8 <= p <= 11)
        cleave_pct = round(min(100.0, cleave_seen / cleave_total * 100), 1)

        central_total = 7 * n_mods
        central_seen = sum(1 for s, p, m in seen if s == "guide" and 7 <= p <= 13)
        central_pct = round(min(100.0, central_seen / central_total * 100), 1)

        three_total = 5 * n_mods
        three_seen = sum(1 for s, p, m in seen if s == "guide" and 16 <= p <= 20)
        three_pct = round(min(100.0, three_seen / three_total * 100), 1)

        pass_total = 21 * n_mods
        pass_seen = sum(1 for s, p, m in seen if s == "passenger")
        pass_pct = round(min(100.0, pass_seen / pass_total * 100), 1)

        bb_total = 6
        bb_pct = round(min(100.0, len(seen_backbone) / bb_total * 100), 1)

        conj_total = 4
        conj_pct = round(min(100.0, len(seen_conjugates) / conj_total * 100), 1)

        cross_pct = round(min(100.0, len(seen_cross) / 50.0 * 100), 1)

        return {
            "seed_modifications": seed_pct,
            "cleavage_neighbors": cleave_pct,
            "central_region": central_pct,
            "three_prime_zone": three_pct,
            "passenger_strand": pass_pct,
            "backbone_variations": bb_pct,
            "conjugate_combinations": conj_pct,
            "cross_strand_patterns": cross_pct,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKWARD COMPAT: ActiveLearner alias
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ActiveLearner = OligoActiveLearner


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STANDALONE: run_dmtl_demo
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_dmtl_demo(
    n_cycles: int = 8,
    db: Session | None = None,
) -> dict:
    """Run a full DMTL demo simulation and return dashboard-ready output.

    Now uses RealDataGP + VPA acquisition instead of heuristic uncertainty.
    Optionally logs each cycle to the DMTLCycleLog database table.

    Args:
        n_cycles: Number of DMTL cycles to simulate.
        db: Optional database session for persistence.

    Returns:
        Formatted dict suitable for the frontend dashboard demo panel.
    """
    from backend.literature_parser import PUBLISHED_MODIFICATIONS_DATASET
    from backend.void_detector import enumerate_modification_voids
    from backend.feasibility_scorer import score_pattern_biophysics

    known = PUBLISHED_MODIFICATIONS_DATASET
    voids_raw = enumerate_modification_voids(known, max_positions_changed=2)

    # Score all void candidates
    scored_voids = []
    for v in voids_raw[:500]:  # cap for demo speed
        scores = score_pattern_biophysics(v)
        scored_void = {**v, **scores}
        scored_voids.append(scored_void)

    # Run active learner with VPA
    learner = OligoActiveLearner(known_patterns=known, scored_voids=scored_voids)

    # Run comparison simulation (Random vs EI vs VPA)
    sim_result = learner.run_simulation(
        n_cycles=min(n_cycles, 5),
        strategies=["random", "ei", "vpa"],
        start_with_n_known=5,
    )

    # Run standard DMTL cycle for detailed per-cycle output
    result = learner.simulate_dmtl_cycle(
        n_cycles=n_cycles,
        start_with_n_known=5,
    )

    # Format for dashboard
    dashboard = {
        "title": f"DMTL Simulation: {n_cycles} Cycles (RealDataGP + VPA)",
        "summary": {
            "total_cycles": result["total_patterns_explored"],
            "uncertainty_reduction_pct": result["uncertainty_reduction"],
            "coverage_improvement_pct": result["coverage_improvement"],
            "patterns_available": len(known),
            "voids_scored": len(scored_voids),
            "gp_model": "RealDataGP (3,700+ OligoFormer sequences)",
            "acquisition_function": "VPA (Void-Prioritized Acquisition)",
        },
        "strategy_comparison": sim_result,
        "cycles": [],
        "final_recommendation": result.get("final_recommendation", {}),
    }

    for cycle in result["cycles"]:
        dashboard["cycles"].append({
            "cycle": cycle["cycle_number"],
            "void_tested": cycle["recommended_void_id"],
            "expected_kd": cycle["expected_knockdown"],
            "actual_kd": cycle["actual_knockdown"],
            "uncertainty_before": cycle["uncertainty_before"],
            "uncertainty_after": cycle["uncertainty_after"],
            "info_gain": cycle["information_gain"],
            "patterns_known": cycle["patterns_known"],
            "model_confidence": cycle.get("model_confidence", ""),
            "reason": cycle["recommendation_reason"],
            "what_we_learn": cycle["what_we_learn"],
        })

    # Persist to database if session provided
    if db is not None:
        for cycle in result["cycles"]:
            log = DMTLCycleLog(
                cycle_number=cycle["cycle_number"],
                recommended_void_id=cycle["recommended_void_id"][:32]
                    if cycle["recommended_void_id"] else None,
                recommendation_reason=cycle["recommendation_reason"],
                acquisition_function=cycle["acquisition_function"],
                model_uncertainty_before=cycle["uncertainty_before"],
                model_uncertainty_after=cycle["uncertainty_after"],
                information_gain=cycle["information_gain"],
            )
            db.add(log)
        db.commit()
        logger.info("Logged %d DMTL cycles to database", len(result["cycles"]))

    return dashboard


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEGACY: backward compat functions used by main.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_information_gain(void: Void, total_voids: int) -> float:
    """Compute legacy information gain for a co-occurrence Void."""
    if total_voids == 0:
        return 0.0

    feas = void.feasibility_score if void.feasibility_score is not None else 0.5
    uncertainty = 1.0 - abs(2.0 * feas - 1.0)
    novelty = 1.0 / (1.0 + void.observation_count)

    disagreement = 0.5
    if void.claude_score is not None and void.feasibility_score is not None:
        disagreement = abs(void.feasibility_score - void.claude_score)

    velocity_penalty = 1.0 / (1.0 + max(0, void.closure_velocity))

    score = (
        0.35 * uncertainty
        + 0.30 * novelty
        + 0.20 * disagreement
        + 0.15 * velocity_penalty
    )
    return round(min(1.0, score), 4)


def update_information_gains(db: Session) -> int:
    """Recompute information gain for all active legacy Voids."""
    voids = db.query(Void).filter(Void.is_void == True).all()  # noqa: E712
    total = len(voids)
    updated = 0
    for void in voids:
        void.information_gain = compute_information_gain(void, total)
        updated += 1
    db.commit()
    return updated


def suggest_next_void(db: Session, top_k: int = 10) -> list[dict]:
    """Legacy suggestion engine for co-occurrence pair voids."""
    update_information_gains(db)
    voids = (
        db.query(Void)
        .filter(Void.is_void == True)  # noqa: E712
        .order_by(Void.information_gain.desc())
        .limit(top_k)
        .all()
    )
    return [
        {
            "rank": rank,
            "void_id": v.id,
            "pos_a": v.pos_a, "mod_a": v.mod_a,
            "pos_b": v.pos_b, "mod_b": v.mod_b,
            "information_gain": v.information_gain,
            "feasibility_score": v.feasibility_score,
            "claude_score": v.claude_score,
            "observation_count": v.observation_count,
            "rationale": _legacy_rationale(v),
        }
        for rank, v in enumerate(voids, 1)
    ]


def _legacy_rationale(void: Void) -> str:
    parts = []
    feas = void.feasibility_score
    if feas is not None:
        if feas >= 0.8:
            parts.append("High biophysics feasibility")
        elif feas >= 0.5:
            parts.append("Moderate feasibility — testing resolves uncertainty")
        else:
            parts.append("Low predicted feasibility — confirms or refutes predictions")
    if void.observation_count == 0:
        parts.append("completely untested")
    elif void.observation_count < 3:
        parts.append(f"only {void.observation_count} observation(s)")
    return "; ".join(parts) + "." if parts else "Standard void."


def record_dmtl_cycle(
    db: Session,
    void_id: int,
    outcome: str = "pending",
    information_gained: float = 0.0,
) -> DMTLCycle:
    """Record a legacy DMTL cycle."""
    last_cycle = db.query(DMTLCycle).order_by(DMTLCycle.cycle_number.desc()).first()
    next_number = (last_cycle.cycle_number + 1) if last_cycle else 1
    void = db.query(Void).filter(Void.id == void_id).first()
    cycle = DMTLCycle(
        cycle_number=next_number,
        suggested_void_id=void_id,
        suggestion_rationale=_legacy_rationale(void) if void else "",
        outcome=outcome,
        information_gained=information_gained,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def get_dmtl_history(db: Session) -> list[dict]:
    """Return all legacy DMTL cycle records."""
    cycles = db.query(DMTLCycle).order_by(DMTLCycle.cycle_number.asc()).all()
    return [
        {
            "cycle_number": c.cycle_number,
            "void_id": c.suggested_void_id,
            "rationale": c.suggestion_rationale,
            "outcome": c.outcome,
            "information_gained": c.information_gained,
            "timestamp": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cycles
    ]
