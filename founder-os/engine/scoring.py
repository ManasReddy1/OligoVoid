"""Harmonic composites. The score gates, it does not average.

The harmonic mean is chosen because it punishes either term being low
(finding F11). A weighted sum lets a fatal weakness hide behind strong
unrelated dimensions, which is exactly the failure this system must avoid.

The two heads are reported separately and never collapsed, because the
ideation-execution gap lives in that collapse (finding F25).
"""

from __future__ import annotations

from typing import Any

WEIGHTS_VERSION = "uncalibrated-v1"

# Floor so a single zero does not silently annihilate a score that a human
# should still see and argue with. A true zero on a hard gate kills the idea
# outright before scoring, so this only smooths the soft dimensions.
EPS = 0.02


def harmonic(*values: float) -> float:
    vals = [max(EPS, min(1.0, float(v))) for v in values if v is not None]
    if not vals:
        return 0.0
    return len(vals) / sum(1.0 / v for v in vals)


def novelty(originality: float, quality: float) -> float:
    """Head 1. Original but low quality must not rank; nor the reverse."""
    return harmonic(originality, quality)


def viability(buildability: float, unit_economics: float,
              distribution: float, timing: float) -> float:
    """Head 2. Every term is a veto."""
    return harmonic(buildability, unit_economics, distribution, timing)


def founder_score(nov: float, via: float, survival: float) -> float:
    """Shortlisting composite only. Ranking is done pairwise, per head."""
    return round(100.0 * harmonic(nov, via) * max(0.0, min(1.0, survival)), 1)


def unit_economics_score(price: float, conversion: float,
                         inference_cost_user: float) -> tuple[float, dict[str, Any]]:
    """Gross margin against the seeded 2026 consumer benchmarks.

    At roughly 3% paid conversion each payer's margin carries ~33 users'
    inference bills, so blended cost per active user is what actually decides
    this. Negative margin is a kill, not a low score.
    """
    conversion = max(1e-6, conversion)
    revenue_per_active = price * conversion
    margin = revenue_per_active - inference_cost_user
    if revenue_per_active <= 0:
        return 0.0, {"margin_ratio": -1.0, "verdict": "no revenue"}
    ratio = margin / revenue_per_active
    if ratio <= 0:
        return 0.0, {"margin_ratio": round(ratio, 3), "verdict": "negative margin"}
    # 0.70 gross margin maps to 1.0; below 0.30 is severe trouble.
    score = max(0.0, min(1.0, (ratio - 0.10) / 0.60))
    return round(score, 3), {"revenue_per_active": round(revenue_per_active, 4),
                             "margin_ratio": round(ratio, 3),
                             "verdict": "ok" if ratio > 0.3 else "thin"}


def buildability_score(build_cost_usd: float, weeks_to_v1: float,
                       ceiling: float = 50_000, week_ceiling: float = 12) -> float:
    if build_cost_usd > ceiling or weeks_to_v1 > week_ceiling:
        return 0.0
    cost_term = 1.0 - (build_cost_usd / ceiling)
    time_term = 1.0 - (weeks_to_v1 / week_ceiling)
    return round(max(0.0, min(1.0, 0.5 * cost_term + 0.5 * time_term)), 3)


def timing_score(months_since_unlock: float | None) -> float:
    """Recency of the enabling capability.

    An unlock that crossed years ago is occupied territory; one that crossed
    last month may not be stable yet. The peak sits at roughly 6-12 months.
    """
    if months_since_unlock is None:
        return 0.4
    m = float(months_since_unlock)
    if m < 0:
        return 0.3
    if m <= 3:
        return 0.75
    if m <= 12:
        return 1.0
    if m <= 24:
        return 0.65
    if m <= 36:
        return 0.35
    return 0.15


def assemble(originality: float, quality: float, buildability: float,
             unit_econ: float, distribution: float, timing: float,
             survival: float) -> dict[str, Any]:
    nov = novelty(originality, quality)
    via = viability(buildability, unit_econ, distribution, timing)
    return {"originality": round(originality, 3),
            "quality": round(quality, 3),
            "novelty": round(nov, 3),
            "buildability": round(buildability, 3),
            "unit_economics": round(unit_econ, 3),
            "distribution": round(distribution, 3),
            "timing": round(timing, 3),
            "viability": round(via, 3),
            "survival": round(survival, 3),
            "founder_score": founder_score(nov, via, survival),
            "weights_version": WEIGHTS_VERSION}
