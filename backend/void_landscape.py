"""
Void Landscape Mapper for OligoVoid.

Maps the topology of the siRNA modification design space into 7 territories,
from well-explored regions near FDA drugs to deep uncharted wilderness.

Author: Manas Reddy
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from backend.fda_validation import FDA_APPROVED_SIRNAS

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TERRITORY DEFINITIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TERRITORY_DEFINITIONS: dict[int, dict] = {
    1: {
        "name": "Established Ground",
        "description": (
            "Patterns within Hamming distance 0-3 of an FDA-approved siRNA drug. "
            "These are the safest starting points — minor variants of clinically "
            "validated chemistries. Low novelty but high confidence in feasibility."
        ),
        "recommendation": (
            "Use as positive controls or safe baselines. These patterns are likely "
            "to work but offer limited novelty for publication. Ideal for de-risking "
            "a new target gene with proven chemistry."
        ),
    },
    2: {
        "name": "Adjacent Frontier",
        "description": (
            "Patterns at Hamming distance 4-7 from the nearest FDA drug. "
            "Close enough to benefit from clinical intuition but different enough "
            "to explore genuinely new chemical territory. This is the most "
            "productive zone for rational design."
        ),
        "recommendation": (
            "Prioritize for experimental testing. These patterns balance novelty "
            "with biological plausibility. Many breakthrough siRNA designs will "
            "come from this zone."
        ),
    },
    3: {
        "name": "Deep Wilderness",
        "description": (
            "Patterns at Hamming distance 8+ from all FDA drugs. Uncharted "
            "territory with no clinical precedent. High risk of unexpected "
            "toxicity or loss of activity, but also the highest potential "
            "for discovering fundamentally new chemistry."
        ),
        "recommendation": (
            "Approach with caution. Validate with in-vitro assays before "
            "committing to animal studies. Consider pairing with a Territory 1 "
            "positive control in the same experiment."
        ),
    },
    4: {
        "name": "Forbidden Zone",
        "description": (
            "Patterns that violate established biological rules: LNA at the "
            "Ago2 cleavage site (positions 10-11) or more than 4 consecutive "
            "LNA residues anywhere on the guide strand. These modifications "
            "are expected to ablate silencing activity."
        ),
        "recommendation": (
            "Avoid unless specifically studying structure-activity relationships "
            "at the cleavage site. These patterns are scientifically informative "
            "as negative controls but should not be pursued as drug candidates."
        ),
    },
    5: {
        "name": "Chemical Desert",
        "description": (
            "Patterns with extremely low modification diversity — only a single "
            "unique sugar modification type used across all positions. Monotonic "
            "chemistry limits the ability to tune regional properties like seed "
            "flexibility or 3-prime stability independently."
        ),
        "recommendation": (
            "Consider adding targeted diversity. Even one or two positions with "
            "a different modification can dramatically improve the pharmacological "
            "profile. Use these as starting points for rational diversification."
        ),
    },
    6: {
        "name": "The Sweet Spot",
        "description": (
            "The most promising intersection: patterns in the Adjacent Frontier "
            "(Hamming 4-7 from FDA drugs) that also score above 70 on either "
            "fingerprint quality or biophysics. These combine novelty with "
            "predicted efficacy — the best candidates for experimental validation."
        ),
        "recommendation": (
            "These are the highest-priority targets for wet-lab validation. "
            "Order synthesis immediately. Consider running a small panel of "
            "3-5 Sweet Spot patterns alongside a Territory 1 positive control."
        ),
    },
    7: {
        "name": "Warming Zones",
        "description": (
            "Patterns where the void is closing — the research community is "
            "actively converging on these combinations. Velocity class is "
            "'warming' or 'hot', meaning recent publications are filling the gap. "
            "Act fast or someone else will publish first."
        ),
        "recommendation": (
            "Urgent: test these within 3-6 months or the void will close. "
            "If you have synthesis capacity, prioritize these over stable voids "
            "that will remain open indefinitely."
        ),
    },
}

# Modifications considered rigid/bulky — restricted at the cleavage site
_RIGID_MODS = {"LNA", "cEt"}
_CLEAVAGE_POSITIONS = {9, 10}  # 0-indexed positions 9-10 correspond to guide positions 10-11


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER: HAMMING DISTANCE TO NEAREST FDA DRUG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _hamming_to_nearest_fda(guide_mods: list[str]) -> int:
    """Compute the Hamming distance from a guide modification pattern to the
    nearest FDA-approved siRNA drug (guide strand only).

    Compares position-by-position against each FDA drug's guide_mods and
    returns the minimum distance found. Handles length mismatches by counting
    each unmatched trailing position as a difference.

    Args:
        guide_mods: List of modification strings for the guide strand
                    (e.g., ["2'-OMe", "2'-F", ...]).

    Returns:
        Minimum Hamming distance (int) to the nearest FDA drug. Returns 999
        if guide_mods is empty or no FDA drugs are available.
    """
    if not guide_mods or not FDA_APPROVED_SIRNAS:
        return 999

    best_dist = 999

    for drug in FDA_APPROVED_SIRNAS:
        fda_guide = drug.get("guide_mods", [])
        if not fda_guide:
            continue

        # Position-wise comparison over the shared length
        shared_len = min(len(guide_mods), len(fda_guide))
        dist = sum(
            1 for i in range(shared_len)
            if guide_mods[i] != fda_guide[i]
        )
        # Penalise length mismatches — each extra/missing position counts as 1
        dist += abs(len(guide_mods) - len(fda_guide))

        if dist < best_dist:
            best_dist = dist

    return best_dist


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INTERNAL HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _has_biological_violations(guide_mods: list[str]) -> bool:
    """Check whether a guide pattern has Forbidden Zone violations.

    Violations:
      - LNA (or cEt) at cleavage site positions 10-11 (0-indexed 9-10).
      - More than 4 consecutive LNA (or cEt) anywhere on the guide.

    Returns True if any violation is detected.
    """
    if not guide_mods:
        return False

    # Check cleavage site
    for idx in _CLEAVAGE_POSITIONS:
        if idx < len(guide_mods) and guide_mods[idx] in _RIGID_MODS:
            return True

    # Check >4 consecutive LNA/cEt
    consecutive = 0
    for mod in guide_mods:
        if mod in _RIGID_MODS:
            consecutive += 1
            if consecutive > 4:
                return True
        else:
            consecutive = 0

    return False


def _has_low_diversity(guide_mods: list[str]) -> bool:
    """Return True if the pattern uses only 1 unique modification type."""
    if not guide_mods:
        return False
    return len(set(guide_mods)) <= 1


def _is_sweet_spot(
    pattern: dict,
    hamming_dist: int,
) -> bool:
    """Return True if the pattern qualifies for Territory 6 (The Sweet Spot).

    Requirements:
      - Must be in Adjacent Frontier range (Hamming 4-7).
      - Must have fingerprint_quality_score > 70 OR a biophysics-derived
        overall_oligovoid_score > 70.
    """
    if not (4 <= hamming_dist <= 7):
        return False

    fqs = pattern.get("fingerprint_quality_score")
    if fqs is not None and fqs > 70:
        return True

    bio_score = pattern.get("overall_oligovoid_score")
    if bio_score is not None and bio_score > 70:
        return True

    return False


def _is_warming_zone(pattern: dict) -> bool:
    """Return True if the pattern has velocity_class 'warming' or 'hot'."""
    vc = pattern.get("velocity_class", "")
    if isinstance(vc, str):
        return vc.lower() in ("warming", "hot")
    return False


def _classify_territory(
    pattern: dict,
    hamming_dist: int,
) -> int:
    """Assign a single territory number (1-7) to a pattern.

    Priority rules (a pattern can match multiple criteria — highest-priority
    territory wins):
      7 — Warming Zones (velocity-based, always overrides if applicable)
      4 — Forbidden Zone (biological violations, always overrides distance)
      5 — Chemical Desert (low diversity)
      6 — The Sweet Spot (Adjacent Frontier + high score)
      1 — Established Ground (Hamming 0-3)
      2 — Adjacent Frontier (Hamming 4-7)
      3 — Deep Wilderness (Hamming 8+)
    """
    guide_mods = pattern.get("guide_mods", [])

    # Territory 7: Warming Zones (highest urgency)
    if _is_warming_zone(pattern):
        return 7

    # Territory 4: Forbidden Zone (biological violations)
    if _has_biological_violations(guide_mods):
        return 4

    # Territory 5: Chemical Desert (low diversity)
    if _has_low_diversity(guide_mods):
        return 5

    # Territory 6: The Sweet Spot (Adjacent Frontier + high quality)
    if _is_sweet_spot(pattern, hamming_dist):
        return 6

    # Distance-based territories
    if hamming_dist <= 3:
        return 1
    elif hamming_dist <= 7:
        return 2
    else:
        return 3


def _safe_get_score(pattern: dict) -> Optional[float]:
    """Extract the OligoVoid score from a pattern dict, returning None
    if not available."""
    score = pattern.get("overall_oligovoid_score")
    if score is not None:
        try:
            return float(score)
        except (TypeError, ValueError):
            return None
    return None


def _safe_get_void_id(pattern: dict) -> Optional[str]:
    """Extract a void ID from a pattern dict."""
    vid = pattern.get("void_id")
    if vid is not None:
        return str(vid)
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN FUNCTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_void_landscape(
    known_patterns: list[dict],
    void_candidates: list[dict],
    scored_voids: list[dict],
) -> dict:
    """Map the topology of the siRNA modification space into 7 territories.

    Takes three populations of patterns — known (published), unscored void
    candidates, and scored voids — and classifies each into one of 7
    territories based on Hamming distance to FDA drugs, biological rule
    violations, modification diversity, quality scores, and closure velocity.

    Args:
        known_patterns: Published/known siRNA modification patterns. Each dict
            should contain at minimum ``guide_mods`` (list[str]).
        void_candidates: Unscored void candidates from the void detector.
            Each dict should contain at minimum ``guide_mods``.
        scored_voids: Voids that have been scored by the feasibility engine.
            Each dict may additionally contain ``overall_oligovoid_score``,
            ``fingerprint_quality_score``, ``velocity_class``, and ``void_id``.

    Returns:
        Dictionary with keys:

        - ``territories`` (dict[int, dict]): Per-territory statistics including
          description, n_known, n_scored_voids, n_unscored_voids,
          best_void_score, and recommendation.
        - ``landscape_summary`` (str): Plain-English summary paragraph.
        - ``sweet_spot_voids`` (list[str]): Top 5 void IDs in Territory 6.
        - ``urgent_voids`` (list[str]): Top 5 void IDs in Territory 7.
    """
    # Normalise inputs — guard against None
    known_patterns = known_patterns or []
    void_candidates = void_candidates or []
    scored_voids = scored_voids or []

    # ── Pre-compute Hamming distances for every pattern ──────────────
    # Each entry: (pattern_dict, hamming_dist, population_tag)
    #   population_tag: "known", "unscored_void", "scored_void"

    classified: dict[int, list[tuple[dict, str]]] = {t: [] for t in range(1, 8)}

    for pat in known_patterns:
        guide = pat.get("guide_mods", [])
        h = _hamming_to_nearest_fda(guide)
        t = _classify_territory(pat, h)
        classified[t].append((pat, "known"))

    for pat in void_candidates:
        guide = pat.get("guide_mods", [])
        h = _hamming_to_nearest_fda(guide)
        t = _classify_territory(pat, h)
        classified[t].append((pat, "unscored_void"))

    for pat in scored_voids:
        guide = pat.get("guide_mods", [])
        h = _hamming_to_nearest_fda(guide)
        t = _classify_territory(pat, h)
        classified[t].append((pat, "scored_void"))

    # ── Build per-territory statistics ───────────────────────────────

    territories: dict[int, dict] = {}

    for t_num in range(1, 8):
        defn = TERRITORY_DEFINITIONS[t_num]
        entries = classified[t_num]

        n_known = sum(1 for _, tag in entries if tag == "known")
        n_scored = sum(1 for _, tag in entries if tag == "scored_void")
        n_unscored = sum(1 for _, tag in entries if tag == "unscored_void")

        # Best void score among scored voids in this territory
        scored_entries = [
            _safe_get_score(pat)
            for pat, tag in entries
            if tag == "scored_void"
        ]
        valid_scores = [s for s in scored_entries if s is not None]
        best_score = round(max(valid_scores), 1) if valid_scores else None

        territories[t_num] = {
            "name": defn["name"],
            "description": defn["description"],
            "n_known": n_known,
            "n_scored_voids": n_scored,
            "n_unscored_voids": n_unscored,
            "best_void_score": best_score,
            "recommendation": defn["recommendation"],
        }

    # ── Sweet Spot voids (Territory 6) — top 5 by score ──────────────

    sweet_spot_entries = [
        (pat, _safe_get_score(pat))
        for pat, tag in classified[6]
        if tag in ("scored_void", "unscored_void")
    ]
    # Sort by score descending; patterns without scores sort last
    sweet_spot_entries.sort(
        key=lambda x: x[1] if x[1] is not None else -1.0,
        reverse=True,
    )
    sweet_spot_voids: list[str] = []
    for pat, _ in sweet_spot_entries[:5]:
        vid = _safe_get_void_id(pat)
        if vid is not None:
            sweet_spot_voids.append(vid)

    # ── Urgent voids (Territory 7) — top 5 by score ──────────────────

    urgent_entries = [
        (pat, _safe_get_score(pat))
        for pat, tag in classified[7]
        if tag in ("scored_void", "unscored_void")
    ]
    urgent_entries.sort(
        key=lambda x: x[1] if x[1] is not None else -1.0,
        reverse=True,
    )
    urgent_voids: list[str] = []
    for pat, _ in urgent_entries[:5]:
        vid = _safe_get_void_id(pat)
        if vid is not None:
            urgent_voids.append(vid)

    # ── Landscape summary paragraph ──────────────────────────────────

    total_known = len(known_patterns)
    total_voids = len(void_candidates) + len(scored_voids)
    total_scored = len(scored_voids)

    t6_total = territories[6]["n_scored_voids"] + territories[6]["n_unscored_voids"]
    t7_total = territories[7]["n_scored_voids"] + territories[7]["n_unscored_voids"]
    t4_total = territories[4]["n_scored_voids"] + territories[4]["n_unscored_voids"]
    t1_known = territories[1]["n_known"]
    t3_voids = territories[3]["n_scored_voids"] + territories[3]["n_unscored_voids"]

    summary_parts = [
        f"The siRNA modification landscape contains {total_known} known patterns "
        f"and {total_voids} void candidates ({total_scored} scored).",
    ]

    if t1_known > 0:
        summary_parts.append(
            f"{t1_known} known patterns cluster within Hamming distance 3 of FDA "
            f"drugs (Established Ground), confirming the field's bias toward "
            f"validated chemistries."
        )

    if t6_total > 0:
        summary_parts.append(
            f"{t6_total} void candidate(s) fall in The Sweet Spot — novel enough "
            f"to be publishable but scoring high enough to be worth synthesizing."
        )

    if t7_total > 0:
        summary_parts.append(
            f"{t7_total} void(s) are in Warming Zones where the research community "
            f"is actively converging. These require urgent experimental attention."
        )

    if t4_total > 0:
        summary_parts.append(
            f"{t4_total} candidate(s) landed in the Forbidden Zone due to "
            f"biological rule violations and should be deprioritized."
        )

    if t3_voids > 0:
        summary_parts.append(
            f"{t3_voids} void(s) sit in the Deep Wilderness (Hamming 8+), "
            f"representing high-risk, high-reward exploration targets."
        )

    landscape_summary = " ".join(summary_parts)

    # ── Assemble and return ──────────────────────────────────────────

    logger.info(
        "Void landscape computed: %d territories, %d total patterns classified",
        7,
        sum(len(v) for v in classified.values()),
    )

    return {
        "territories": territories,
        "landscape_summary": landscape_summary,
        "sweet_spot_voids": sweet_spot_voids,
        "urgent_voids": urgent_voids,
    }
