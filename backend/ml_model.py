"""Gaussian Process Regression model for siRNA knockdown prediction.

Replaces the heuristic feasibility scorer with a real ML model that:
  - Learns from 60 published siRNA modification patterns
  - Provides calibrated uncertainty estimates for active learning
  - Uses 27 biophysically meaningful features (not 336 one-hot)
  - Supports incremental updates and LOOCV diagnostics

Feature groups (27 total):
  Regional ΔTm aggregates (8): mean ΔTm for seed, cleavage, supplementary,
    overhang, passenger-seed, passenger-mid, passenger-3prime, full-guide
  RISC tolerance (4): mean for seed, cleavage, supplementary, overhang
  Nuclease resistance (4): mean for guide-terminal, guide-internal,
    passenger-terminal, passenger-internal
  Composition fractions (5): fraction of 2OMe, 2F, MOE, LNA, unmodified
  Backbone encoding (3): guide-terminal, guide-internal, passenger-terminal
  Conjugate one-hot (3): GalNAc, Cholesterol, LNP
"""

from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

from backend.modification_grammar import SUGAR_MODIFICATIONS

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FEATURE ENCODING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Biophysical property lookups from the modification grammar
_DELTA_TM: dict[str, float] = {
    k: v["binding_affinity_delta_tm"] for k, v in SUGAR_MODIFICATIONS.items()
}
_RISC_TOL: dict[str, float] = {
    k: v["risc_tolerance"] for k, v in SUGAR_MODIFICATIONS.items()
}
_NUC_RES: dict[str, float] = {
    k: v["nuclease_resistance"] for k, v in SUGAR_MODIFICATIONS.items()
}

# Canonical mod names for composition fractions
_COMP_MODS = ["2'-OMe", "2'-F", "MOE", "LNA", "RNA"]

# Backbone encoding: PS=1.0, MsPA=0.5, PO=0.0
_BB_ENCODE = {"PS": 1.0, "MsPA": 0.5, "PO": 0.0}

# Conjugate one-hot order
_CONJUGATES = ["GalNAc", "Cholesterol", "LNP"]


def _mean_prop(mods: list[str], prop_map: dict[str, float], indices: range | list[int]) -> float:
    """Mean of a biophysical property across given 0-indexed positions."""
    vals = [prop_map.get(mods[i], 0.0) for i in indices if i < len(mods)]
    return float(np.mean(vals)) if vals else 0.0


def _mean_bb(backbone: list[str], indices: list[int]) -> float:
    """Mean backbone encoding across given linkage indices."""
    vals = [_BB_ENCODE.get(backbone[i], 0.0) for i in indices if i < len(backbone)]
    return float(np.mean(vals)) if vals else 0.0


def encode_pattern(pattern: dict) -> np.ndarray:
    """Convert a siRNA pattern dict to a 27-feature vector.

    Args:
        pattern: Dict with keys guide_mods (list[str] len 21),
                 passenger_mods (list[str] len 21),
                 backbone_guide (list[str] len 20),
                 backbone_passenger (list[str] len 20),
                 conjugate (str).

    Returns:
        np.ndarray of shape (27,).
    """
    guide = pattern.get("guide_mods", ["RNA"] * 21)
    passenger = pattern.get("passenger_mods", ["RNA"] * 21)
    bb_g = pattern.get("backbone_guide", ["PO"] * 20)
    bb_p = pattern.get("backbone_passenger", ["PO"] * 20)
    conjugate = pattern.get("conjugate", "None")

    features = []

    # ── Group 1: Regional ΔTm aggregates (8 features) ────────────────
    # Guide regions (0-indexed)
    features.append(_mean_prop(guide, _DELTA_TM, range(1, 8)))      # seed g2-g8
    features.append(_mean_prop(guide, _DELTA_TM, range(9, 11)))     # cleavage g10-g11
    features.append(_mean_prop(guide, _DELTA_TM, range(12, 16)))    # supplementary g13-g16
    features.append(_mean_prop(guide, _DELTA_TM, range(18, 21)))    # overhang g19-g21
    # Passenger regions
    features.append(_mean_prop(passenger, _DELTA_TM, range(1, 8)))  # passenger-seed p2-p8
    features.append(_mean_prop(passenger, _DELTA_TM, range(8, 15))) # passenger-mid p9-p15
    features.append(_mean_prop(passenger, _DELTA_TM, range(15, 21)))# passenger-3prime p16-p21
    # Full guide mean
    features.append(_mean_prop(guide, _DELTA_TM, range(0, 21)))     # full-guide-mean

    # ── Group 2: RISC tolerance (4 features) ─────────────────────────
    features.append(_mean_prop(guide, _RISC_TOL, range(1, 8)))      # seed
    features.append(_mean_prop(guide, _RISC_TOL, range(9, 11)))     # cleavage
    features.append(_mean_prop(guide, _RISC_TOL, range(12, 16)))    # supplementary
    features.append(_mean_prop(guide, _RISC_TOL, range(18, 21)))    # overhang

    # ── Group 3: Nuclease resistance (4 features) ────────────────────
    # Guide terminal = g1-g2, g20-g21 (0-indexed: 0,1,19,20)
    features.append(_mean_prop(guide, _NUC_RES, [0, 1, 19, 20]))   # guide-terminal
    features.append(_mean_prop(guide, _NUC_RES, range(2, 19)))      # guide-internal
    # Passenger terminal = p1-p2, p20-p21
    features.append(_mean_prop(passenger, _NUC_RES, [0, 1, 19, 20]))# passenger-terminal
    features.append(_mean_prop(passenger, _NUC_RES, range(2, 19)))  # passenger-internal

    # ── Group 4: Composition fractions (5 features) ──────────────────
    all_mods = list(guide) + list(passenger)
    total = max(len(all_mods), 1)
    for mod_name in _COMP_MODS:
        count = sum(1 for m in all_mods if m == mod_name)
        features.append(count / total)

    # ── Group 5: Backbone encoding (3 features) ─────────────────────
    # Guide terminal linkages (0,1,18,19)
    features.append(_mean_bb(bb_g, [0, 1, 18, 19]))
    # Guide internal linkages (2-17)
    features.append(_mean_bb(bb_g, list(range(2, 18))))
    # Passenger terminal linkages
    features.append(_mean_bb(bb_p, [0, 1, 18, 19]))

    # ── Group 6: Conjugate one-hot (3 features) ─────────────────────
    for conj_name in _CONJUGATES:
        features.append(1.0 if conjugate == conj_name else 0.0)

    return np.array(features, dtype=np.float64)


# Feature names for interpretability
FEATURE_NAMES: list[str] = [
    # ΔTm (8)
    "dtm_seed", "dtm_cleavage", "dtm_supplementary", "dtm_overhang",
    "dtm_pass_seed", "dtm_pass_mid", "dtm_pass_3prime", "dtm_guide_mean",
    # RISC (4)
    "risc_seed", "risc_cleavage", "risc_supplementary", "risc_overhang",
    # Nuclease (4)
    "nuc_guide_term", "nuc_guide_int", "nuc_pass_term", "nuc_pass_int",
    # Composition (5)
    "frac_2ome", "frac_2f", "frac_moe", "frac_lna", "frac_rna",
    # Backbone (3)
    "bb_guide_term", "bb_guide_int", "bb_pass_term",
    # Conjugate (3)
    "conj_galnac", "conj_cholesterol", "conj_lnp",
]

assert len(FEATURE_NAMES) == 27


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GPR MODEL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class OligoVoidGPR:
    """Gaussian Process Regression model for siRNA knockdown prediction.

    Uses a Matern-5/2 kernel with automatic relevance determination (ARD)
    and a WhiteKernel for noise estimation. Trained on 27 biophysically
    meaningful features extracted from siRNA modification patterns.

    Designed for small datasets (n~60): uses LOOCV for validation,
    provides calibrated uncertainty estimates for active learning.
    """

    def __init__(self):
        kernel = Matern(nu=2.5, length_scale=np.ones(27)) + WhiteKernel(noise_level=0.1)
        self.gpr = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=5,
            normalize_y=True,
            alpha=1e-6,
        )
        self._X_train: np.ndarray | None = None
        self._y_train: np.ndarray | None = None
        self._is_fitted: bool = False
        self._diagnostics: dict = {}

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    def fit(self, patterns: list[dict], targets: list[float]) -> dict:
        """Train the GPR on a set of siRNA patterns and knockdown targets.

        Args:
            patterns: List of pattern dicts with guide_mods, passenger_mods, etc.
            targets: List of knockdown efficacy values (0-100).

        Returns:
            Diagnostics dict with LOOCV R², MAE, calibration, kernel params.
        """
        X = np.array([encode_pattern(p) for p in patterns])
        y = np.array(targets, dtype=np.float64)

        self._X_train = X
        self._y_train = y

        # Fit the model
        self.gpr.fit(X, y)
        self._is_fitted = True

        # Compute LOOCV diagnostics
        self._diagnostics = self._compute_loocv(X, y)
        self._diagnostics["n_training"] = len(y)
        self._diagnostics["kernel_params"] = str(self.gpr.kernel_)

        logger.info(
            "GPR fitted on %d samples: LOOCV R²=%.3f, MAE=%.2f",
            len(y), self._diagnostics["r2_loocv"], self._diagnostics["mae_loocv"],
        )

        return self._diagnostics

    def _compute_loocv(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Run Leave-One-Out Cross-Validation and return diagnostics."""
        loo = LeaveOneOut()
        y_pred_loo = np.zeros_like(y)
        y_std_loo = np.zeros_like(y)

        for train_idx, test_idx in loo.split(X):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train = y[train_idx]

            # Create a fresh GPR with same kernel config for each fold
            kernel = Matern(nu=2.5, length_scale=np.ones(27)) + WhiteKernel(noise_level=0.1)
            gpr_fold = GaussianProcessRegressor(
                kernel=kernel,
                n_restarts_optimizer=3,
                normalize_y=True,
                alpha=1e-6,
            )
            gpr_fold.fit(X_train, y_train)
            mu, std = gpr_fold.predict(X_test, return_std=True)
            y_pred_loo[test_idx] = mu
            y_std_loo[test_idx] = std

        r2 = r2_score(y, y_pred_loo)
        mae = mean_absolute_error(y, y_pred_loo)

        # Calibration: % of true values within ±1σ prediction interval
        within_1sigma = np.mean(np.abs(y - y_pred_loo) <= y_std_loo)

        return {
            "r2_loocv": round(float(r2), 4),
            "mae_loocv": round(float(mae), 4),
            "calibration_1sigma": round(float(within_1sigma), 4),
            "mean_std": round(float(np.mean(y_std_loo)), 4),
        }

    def predict(self, pattern: dict) -> tuple[float, float]:
        """Predict knockdown efficacy and uncertainty for a single pattern.

        Args:
            pattern: Dict with guide_mods, passenger_mods, etc.

        Returns:
            (predicted_knockdown, uncertainty_std) tuple.
        """
        if not self._is_fitted:
            raise RuntimeError("GPR model is not fitted. Call fit() first.")

        X = encode_pattern(pattern).reshape(1, -1)
        mu, std = self.gpr.predict(X, return_std=True)
        return float(mu[0]), float(std[0])

    def predict_batch(self, patterns: list[dict]) -> tuple[np.ndarray, np.ndarray]:
        """Predict knockdown efficacy and uncertainty for multiple patterns.

        Args:
            patterns: List of pattern dicts.

        Returns:
            (means, stds) tuple of arrays with shape (n_patterns,).
        """
        if not self._is_fitted:
            raise RuntimeError("GPR model is not fitted. Call fit() first.")

        X = np.array([encode_pattern(p) for p in patterns])
        mu, std = self.gpr.predict(X, return_std=True)
        return mu, std

    def update(self, new_pattern: dict, new_target: float) -> dict:
        """Incrementally add a new observation and refit.

        Args:
            new_pattern: Pattern dict for the new observation.
            new_target: Observed knockdown efficacy.

        Returns:
            Updated diagnostics dict.
        """
        x_new = encode_pattern(new_pattern).reshape(1, -1)

        if self._X_train is not None and self._y_train is not None:
            self._X_train = np.vstack([self._X_train, x_new])
            self._y_train = np.append(self._y_train, new_target)
        else:
            self._X_train = x_new
            self._y_train = np.array([new_target])

        self.gpr.fit(self._X_train, self._y_train)
        self._is_fitted = True

        # Recompute diagnostics only if we have enough data
        if len(self._y_train) >= 5:
            self._diagnostics = self._compute_loocv(self._X_train, self._y_train)
        self._diagnostics["n_training"] = len(self._y_train)
        self._diagnostics["kernel_params"] = str(self.gpr.kernel_)

        return self._diagnostics

    def save(self, path: str) -> None:
        """Save the fitted model to disk using joblib."""
        state = {
            "gpr": self.gpr,
            "X_train": self._X_train,
            "y_train": self._y_train,
            "is_fitted": self._is_fitted,
            "diagnostics": self._diagnostics,
        }
        joblib.dump(state, path)
        logger.info("GPR model saved to %s", path)

    def load(self, path: str) -> None:
        """Load a fitted model from disk."""
        state = joblib.load(path)
        self.gpr = state["gpr"]
        self._X_train = state["X_train"]
        self._y_train = state["y_train"]
        self._is_fitted = state["is_fitted"]
        self._diagnostics = state["diagnostics"]
        logger.info("GPR model loaded from %s", path)

    def get_model_diagnostics(self) -> dict:
        """Return current model diagnostics.

        Returns:
            Dict with LOOCV R², MAE, calibration, n_training,
            kernel params, and fitted status.
        """
        return {
            "is_fitted": self._is_fitted,
            **self._diagnostics,
        }

    def copy(self) -> "OligoVoidGPR":
        """Create a deep copy of this model for simulation."""
        new = OligoVoidGPR()
        new.gpr = deepcopy(self.gpr)
        new._X_train = self._X_train.copy() if self._X_train is not None else None
        new._y_train = self._y_train.copy() if self._y_train is not None else None
        new._is_fitted = self._is_fitted
        new._diagnostics = dict(self._diagnostics)
        return new


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SINGLETON ACCESS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_gpr_instance: OligoVoidGPR | None = None


def get_gpr_model() -> OligoVoidGPR:
    """Get or create the singleton GPR model."""
    global _gpr_instance
    if _gpr_instance is None:
        _gpr_instance = OligoVoidGPR()
    return _gpr_instance
