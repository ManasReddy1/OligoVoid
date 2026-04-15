"""Active learning engine for OligoVoid — the DMTL loop.

Design-Make-Test-Learn: systematically suggests which void modification
pattern a researcher should synthesize NEXT to gain the maximum
information about the siRNA modification design space.

The core question: "Given everything we know, which untested pattern
should be tested next?"

Acquisition functions:
  - uncertainty:   maximize reduction in model uncertainty
  - exploitation:  maximize predicted knockdown efficacy
  - exploration:   maximize coverage of uncharted design space
  - balanced:      weighted combination (default, recommended)
"""

from __future__ import annotations

import logging
import math
import hashlib
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

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
# ACTIVE LEARNER CLASS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ActiveLearner:
    """Design-Make-Test-Learn cycle engine for siRNA modification space.

    Maintains a set of known patterns and scored void candidates.
    Uses acquisition functions to recommend which void to test next
    for maximum information gain.

    Args:
        known_patterns: List of dicts with guide_mods, passenger_mods,
                       knockdown_efficacy, pattern_id, etc.
        scored_voids: List of void dicts with guide_mods, passenger_mods,
                     overall_oligovoid_score, hamming_to_nearest,
                     nearest_known_id, etc.
    """

    def __init__(
        self,
        known_patterns: list[dict],
        scored_voids: list[dict],
    ):
        self.known = list(known_patterns)
        self.candidates = list(scored_voids)
        self.cycle_history: list[dict] = []
        self._mod_position_counts: dict[tuple[str, int, str], int] | None = None

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
    # CORE: Uncertainty
    # ────────────────────────────────────────────────────────────────────

    def _compute_uncertainty(self, void: dict) -> float:
        """Compute epistemic uncertainty for a void candidate (0-1).

        High uncertainty when:
          - Hamming distance to nearest known pattern > 5
          - The modification at each changed position has been tested
            fewer than 3 times at that position across known patterns
          - The void sits in an unexplored region (far from ALL known
            patterns, not just the nearest)

        Components:
          1. Distance uncertainty (0-0.40): based on min Hamming distance
          2. Position rarity (0-0.35): based on how rarely each mod
             appears at each changed position
          3. Neighborhood sparsity (0-0.25): based on how many known
             patterns are within Hamming ≤ 5

        Returns 0-1 uncertainty score.
        """
        guide = void.get("guide_mods", [])
        passenger = void.get("passenger_mods", [])
        counts = self._get_mod_position_counts()

        # ── Component 1: Distance uncertainty ────────────────────────
        hamming = void.get("hamming_to_nearest", 0)
        # Sigmoid saturation: distance 0 → 0.0, distance 5 → ~0.3, 10+ → ~0.40
        dist_uncertainty = 0.40 * (1.0 - math.exp(-hamming / 5.0))

        # ── Component 2: Position-specific rarity ────────────────────
        changes = void.get("changes", [])
        if changes:
            rarities = []
            for c in changes:
                pos_idx = c["position"] - 1  # 0-indexed
                strand = c.get("strand", "guide")
                mod = c["to"]
                obs = counts.get((strand, pos_idx, mod), 0)
                # 0 observations → rarity 1.0, 3+ → rarity ~0.05
                rarity = 1.0 / (1.0 + obs)
                rarities.append(rarity)
            avg_rarity = sum(rarities) / len(rarities)
        else:
            # No explicit changes — estimate from guide mods
            rarities = []
            for i, mod in enumerate(guide):
                obs = counts.get(("guide", i, mod), 0)
                rarities.append(1.0 / (1.0 + obs))
            avg_rarity = sum(rarities) / max(len(rarities), 1)

        position_uncertainty = 0.35 * avg_rarity

        # ── Component 3: Neighborhood sparsity ───────────────────────
        nearby_count = 0
        for pat in self.known:
            d = _hamming_lists(guide, pat.get("guide_mods", [])) + \
                _hamming_lists(passenger, pat.get("passenger_mods", []))
            if d <= 5:
                nearby_count += 1

        # 0 neighbors → 0.25, 5+ neighbors → ~0.02
        sparsity_uncertainty = 0.25 / (1.0 + nearby_count)

        total = dist_uncertainty + position_uncertainty + sparsity_uncertainty
        return round(min(1.0, total), 4)

    # ────────────────────────────────────────────────────────────────────
    # CORE: Expected Improvement
    # ────────────────────────────────────────────────────────────────────

    def _compute_expected_improvement(
        self,
        void: dict,
        target_knockdown: float = 85.0,
    ) -> float:
        """Expected improvement over current best result (0-1).

        Based on:
          - predicted_knockdown from feasibility scoring
          - best known knockdown across existing patterns
          - uncertainty amplification (higher uncertainty → wider EI)

        Uses a simplified Expected Improvement formula:
          EI = max(0, predicted - target) * feasibility_factor * uncertainty_boost

        Returns 0-1 score.
        """
        predicted_kd = void.get("predicted_knockdown_pct",
                                void.get("overall_oligovoid_score", 50.0))
        overall_score = void.get("overall_oligovoid_score", 50.0)

        # Best known knockdown
        best_known = max(
            (p.get("knockdown_efficacy", 0) or 0 for p in self.known),
            default=70.0,
        )

        # Raw improvement: how much better than target?
        improvement = max(0.0, predicted_kd - target_knockdown)
        # Normalize: 15% improvement → ~1.0
        normalized_improvement = min(1.0, improvement / 15.0)

        # Feasibility factor: high-scoring patterns more likely to work
        feasibility_factor = min(1.0, overall_score / 100.0)

        # Uncertainty boost: uncertain patterns have wider confidence
        # intervals, so EI is amplified
        uncertainty = self._compute_uncertainty(void)
        uncertainty_boost = 1.0 + uncertainty * 0.5

        ei = normalized_improvement * feasibility_factor * uncertainty_boost
        return round(min(1.0, ei), 4)

    # ────────────────────────────────────────────────────────────────────
    # CORE: Diversity Bonus
    # ────────────────────────────────────────────────────────────────────

    def _compute_diversity_bonus(
        self,
        void: dict,
        already_recommended: list[dict],
    ) -> float:
        """Diversity bonus relative to already-recommended patterns (0-1).

        Prevents the algorithm from recommending 5 similar patterns in
        a row. Computes minimum Hamming distance to all patterns in
        already_recommended.

        High bonus when:
          - The candidate differs from all previously recommended patterns
          - The candidate uses a different modification type
          - The candidate targets a different functional region

        Returns 0-1 score.
        """
        if not already_recommended:
            return 1.0  # maximum diversity if nothing recommended yet

        guide = void.get("guide_mods", [])
        passenger = void.get("passenger_mods", [])

        min_dist = 42  # maximum possible
        for rec in already_recommended:
            d = _hamming_lists(guide, rec.get("guide_mods", [])) + \
                _hamming_lists(passenger, rec.get("passenger_mods", []))
            min_dist = min(min_dist, d)

        # Distance 0 → bonus 0.0, distance 5 → bonus ~0.6, distance 10+ → ~0.9
        distance_bonus = 1.0 - math.exp(-min_dist / 5.0)

        # Check if candidate targets a different region than recommended
        cand_regions = _changed_regions(void)
        rec_regions = set()
        for r in already_recommended:
            rec_regions.update(_changed_regions(r))

        if cand_regions and not cand_regions.intersection(rec_regions):
            region_bonus = 0.15
        else:
            region_bonus = 0.0

        total = min(1.0, distance_bonus + region_bonus)
        return round(total, 4)

    # ────────────────────────────────────────────────────────────────────
    # MAIN: Recommend Next Experiment
    # ────────────────────────────────────────────────────────────────────

    def recommend_next_experiment(
        self,
        acquisition_function: str = "balanced",
        n_recommendations: int = 3,
    ) -> list[dict]:
        """Return top N void patterns to test next.

        Acquisition function options:
          "uncertainty":   maximize uncertainty reduction
          "exploitation":  maximize expected knockdown
          "exploration":   maximize space coverage (diversity)
          "balanced":      weighted combination (default)

        Returns list of recommendation dicts with scores and rationale.
        """
        if not self.candidates:
            return []

        # Score all candidates
        scored: list[tuple[float, dict, dict]] = []
        already_rec: list[dict] = []

        for void in self.candidates:
            uncertainty = self._compute_uncertainty(void)
            ei = self._compute_expected_improvement(void)
            diversity = self._compute_diversity_bonus(void, already_rec)

            # Acquisition function weighting
            if acquisition_function == "uncertainty":
                acq_score = uncertainty * 0.70 + ei * 0.15 + diversity * 0.15
            elif acquisition_function == "exploitation":
                acq_score = uncertainty * 0.10 + ei * 0.75 + diversity * 0.15
            elif acquisition_function == "exploration":
                acq_score = uncertainty * 0.30 + ei * 0.10 + diversity * 0.60
            else:  # balanced
                acq_score = uncertainty * 0.35 + ei * 0.35 + diversity * 0.30

            detail = {
                "uncertainty_score": uncertainty,
                "expected_improvement": ei,
                "diversity_score": diversity,
                "acquisition_score": acq_score,
            }
            scored.append((acq_score, void, detail))

        # Sort by acquisition score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Greedily pick top N, recomputing diversity after each pick
        recommendations: list[dict] = []
        remaining = list(scored)

        for rank in range(1, n_recommendations + 1):
            if not remaining:
                break

            # Re-score diversity for remaining candidates
            if rank > 1:
                rescored = []
                for _, void, detail in remaining:
                    diversity = self._compute_diversity_bonus(void, already_rec)
                    detail = dict(detail)
                    detail["diversity_score"] = diversity

                    if acquisition_function == "uncertainty":
                        acq = detail["uncertainty_score"] * 0.70 + detail["expected_improvement"] * 0.15 + diversity * 0.15
                    elif acquisition_function == "exploitation":
                        acq = detail["uncertainty_score"] * 0.10 + detail["expected_improvement"] * 0.75 + diversity * 0.15
                    elif acquisition_function == "exploration":
                        acq = detail["uncertainty_score"] * 0.30 + detail["expected_improvement"] * 0.10 + diversity * 0.60
                    else:
                        acq = detail["uncertainty_score"] * 0.35 + detail["expected_improvement"] * 0.35 + diversity * 0.30

                    detail["acquisition_score"] = acq
                    rescored.append((acq, void, detail))

                rescored.sort(key=lambda x: x[0], reverse=True)
                remaining = rescored

            acq_score, best_void, best_detail = remaining.pop(0)

            predicted_kd = best_void.get(
                "predicted_knockdown_pct",
                best_void.get("overall_oligovoid_score", 50.0),
            )

            rec = {
                "void_id": best_void.get("void_id", best_void.get("fingerprint", "")),
                "rank": rank,
                "acquisition_score": round(acq_score, 4),
                "acquisition_function": acquisition_function,
                "recommendation_reason": _build_recommendation_reason(
                    best_void, best_detail, acquisition_function
                ),
                "expected_knockdown": round(predicted_kd, 1),
                "uncertainty_score": round(best_detail["uncertainty_score"], 4),
                "diversity_score": round(best_detail["diversity_score"], 4),
                "expected_improvement": round(best_detail["expected_improvement"], 4),
                "what_we_learn": _what_we_learn(best_void),
                "guide_mods": best_void.get("guide_mods", []),
                "passenger_mods": best_void.get("passenger_mods", []),
                "hamming_to_nearest": best_void.get("hamming_to_nearest", 0),
                "nearest_known_id": best_void.get("nearest_known_id", ""),
            }
            recommendations.append(rec)
            already_rec.append(best_void)

        return recommendations

    # ────────────────────────────────────────────────────────────────────
    # SIMULATE: Full DMTL Cycle
    # ────────────────────────────────────────────────────────────────────

    def simulate_dmtl_cycle(
        self,
        n_cycles: int = 5,
        start_with_n_known: int = 5,
    ) -> dict:
        """Simulate running N DMTL cycles.

        Algorithm:
          1. Start with only start_with_n_known patterns as "known"
          2. Each cycle:
             a. recommend_next_experiment()
             b. "Test" the top pick: use its predicted score as outcome
                (or look up actual data if the void matches a known pattern)
             c. Add the tested pattern to the known set
             d. Recompute uncertainties (invalidate cache)
             e. Log cycle data
          3. Track model improvement across cycles

        Returns:
          {
            "cycles": list of cycle dicts,
            "total_patterns_explored": int,
            "uncertainty_reduction": float (% reduced from cycle 1 to last),
            "coverage_improvement": float (% coverage gained),
            "final_recommendation": dict,
          }
        """
        # Reset state for simulation
        all_known_backup = list(self.known)
        all_candidates_backup = list(self.candidates)

        # Start with limited known patterns
        sim_known = list(self.known[:start_with_n_known])
        sim_candidates = list(self.candidates)

        self.known = sim_known
        self._invalidate_cache()

        cycles_log: list[dict] = []
        initial_uncertainty = None

        for cycle_num in range(1, n_cycles + 1):
            # Filter candidates: remove any that have been "tested"
            known_fps = set()
            for k in self.known:
                fp = _pattern_fingerprint(k.get("guide_mods", []),
                                          k.get("passenger_mods", []))
                known_fps.add(fp)

            self.candidates = [
                c for c in sim_candidates
                if _pattern_fingerprint(c.get("guide_mods", []),
                                        c.get("passenger_mods", []))
                not in known_fps
            ]

            if not self.candidates:
                break

            # Compute mean uncertainty before recommendation
            uncertainties_before = [
                self._compute_uncertainty(c) for c in self.candidates
            ]
            mean_uncertainty_before = (
                sum(uncertainties_before) / len(uncertainties_before)
                if uncertainties_before else 0.0
            )
            if initial_uncertainty is None:
                initial_uncertainty = mean_uncertainty_before

            # Get recommendation
            recs = self.recommend_next_experiment(
                acquisition_function="balanced",
                n_recommendations=1,
            )
            if not recs:
                break

            top_rec = recs[0]

            # "Test" the recommendation: simulate getting a result
            tested_pattern = {
                "pattern_id": f"DMTL_CYCLE_{cycle_num:03d}",
                "guide_mods": top_rec["guide_mods"],
                "passenger_mods": top_rec["passenger_mods"],
                "knockdown_efficacy": top_rec["expected_knockdown"],
                "source": "DMTL simulation",
                "year": 2026,
            }

            # Check if this matches any pattern from the full known set
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

            # Add to known set
            self.known.append(tested_pattern)
            self._invalidate_cache()

            # Compute uncertainty after
            uncertainties_after = [
                self._compute_uncertainty(c) for c in self.candidates
            ]
            mean_uncertainty_after = (
                sum(uncertainties_after) / len(uncertainties_after)
                if uncertainties_after else 0.0
            )

            info_gain = max(0.0, mean_uncertainty_before - mean_uncertainty_after)

            # Coverage snapshot
            coverage = self.get_exploration_coverage()
            total_explored = sum(
                v for v in coverage.values() if isinstance(v, (int, float))
            )

            cycle_data = {
                "cycle_number": cycle_num,
                "recommended_void_id": top_rec["void_id"],
                "acquisition_score": top_rec["acquisition_score"],
                "acquisition_function": "balanced",
                "expected_knockdown": top_rec["expected_knockdown"],
                "actual_knockdown": tested_pattern["knockdown_efficacy"],
                "uncertainty_before": round(mean_uncertainty_before, 4),
                "uncertainty_after": round(mean_uncertainty_after, 4),
                "information_gain": round(info_gain, 4),
                "patterns_known": len(self.known),
                "candidates_remaining": len(self.candidates),
                "recommendation_reason": top_rec["recommendation_reason"],
                "what_we_learn": top_rec["what_we_learn"],
                "coverage_snapshot": coverage,
            }
            cycles_log.append(cycle_data)
            self.cycle_history.append(cycle_data)

        # Compute overall metrics
        final_uncertainty = cycles_log[-1]["uncertainty_after"] if cycles_log else 0.0
        initial_uncertainty = initial_uncertainty or final_uncertainty

        uncertainty_reduction = (
            (initial_uncertainty - final_uncertainty) / initial_uncertainty * 100
            if initial_uncertainty > 0 else 0.0
        )

        initial_coverage = cycles_log[0]["coverage_snapshot"] if cycles_log else {}
        final_coverage = cycles_log[-1]["coverage_snapshot"] if cycles_log else {}
        initial_avg = _avg_coverage(initial_coverage)
        final_avg = _avg_coverage(final_coverage)
        coverage_improvement = final_avg - initial_avg

        # Final recommendation for next step
        final_rec = (
            self.recommend_next_experiment("balanced", 1)[0]
            if self.candidates else {}
        )

        # Restore state
        self.known = all_known_backup
        self.candidates = all_candidates_backup
        self._invalidate_cache()

        return {
            "cycles": cycles_log,
            "total_patterns_explored": len(cycles_log),
            "uncertainty_reduction": round(uncertainty_reduction, 1),
            "coverage_improvement": round(coverage_improvement, 1),
            "final_recommendation": final_rec,
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

        Returns dict with % explored (0-100) for each subregion.
        """
        all_mods = [m.value for m in SugarMod]
        n_mods = len(all_mods)

        # Collect all (strand, position, mod) from known
        seen: set[tuple[str, int, str]] = set()
        seen_backbone: set[tuple[str, str]] = set()    # (strand, mod)
        seen_conjugates: set[str] = set()
        seen_cross: set[tuple[str, str]] = set()       # (guide_mod_at_seed, pass_mod_at_seed)

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

            # Cross-strand: (guide seed combo, passenger seed combo)
            if len(guide) >= 8 and len(passenger) >= 8:
                g_seed = frozenset(guide[1:8])
                p_seed = frozenset(passenger[1:8])
                seen_cross.add((str(g_seed), str(p_seed)))

        # 1. Seed modifications (guide pos 2-8 = 0-idx 1..7)
        seed_total = 7 * n_mods
        seed_seen = sum(1 for s, p, m in seen if s == "guide" and 1 <= p <= 7)
        seed_pct = round(min(100.0, seed_seen / seed_total * 100), 1)

        # 2. Cleavage neighbors (guide pos 9-12 = 0-idx 8..11)
        cleave_total = 4 * n_mods
        cleave_seen = sum(1 for s, p, m in seen if s == "guide" and 8 <= p <= 11)
        cleave_pct = round(min(100.0, cleave_seen / cleave_total * 100), 1)

        # 3. Central region (guide pos 8-14 = 0-idx 7..13)
        central_total = 7 * n_mods
        central_seen = sum(1 for s, p, m in seen if s == "guide" and 7 <= p <= 13)
        central_pct = round(min(100.0, central_seen / central_total * 100), 1)

        # 4. 3' stabilization (guide pos 17-21 = 0-idx 16..20)
        three_total = 5 * n_mods
        three_seen = sum(1 for s, p, m in seen if s == "guide" and 16 <= p <= 20)
        three_pct = round(min(100.0, three_seen / three_total * 100), 1)

        # 5. Full passenger strand
        pass_total = 21 * n_mods
        pass_seen = sum(1 for s, p, m in seen if s == "passenger")
        pass_pct = round(min(100.0, pass_seen / pass_total * 100), 1)

        # 6. Backbone variations: 2 strands × 3 mods = 6 possible
        bb_total = 6
        bb_pct = round(min(100.0, len(seen_backbone) / bb_total * 100), 1)

        # 7. Conjugate combinations: 4 options (GalNAc, Cholesterol, LNP, None)
        conj_total = 4
        conj_pct = round(min(100.0, len(seen_conjugates) / conj_total * 100), 1)

        # 8. Cross-strand patterns: theoretical max is very large;
        # track as ratio of unique combos seen to theoretical maximum
        # Approximate: n_mods^2 seed combos × n_mods^2 pass combos is huge.
        # Use a practical ceiling of 50 unique combos.
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


def _build_recommendation_reason(
    void: dict, detail: dict, acq_fn: str
) -> str:
    """Generate a human-readable recommendation reason."""
    parts: list[str] = []
    uncertainty = detail.get("uncertainty_score", 0)
    ei = detail.get("expected_improvement", 0)
    diversity = detail.get("diversity_score", 0)
    hamming = void.get("hamming_to_nearest", 0)

    if uncertainty >= 0.5:
        parts.append(f"High uncertainty ({uncertainty:.0%}) — testing this reduces model blind spots")
    elif uncertainty >= 0.3:
        parts.append(f"Moderate uncertainty ({uncertainty:.0%}) in this region")

    if ei >= 0.3:
        kd = void.get("predicted_knockdown_pct",
                       void.get("overall_oligovoid_score", 0))
        parts.append(f"Expected {kd:.0f}% knockdown — potential improvement over known patterns")

    if diversity >= 0.7:
        parts.append("Explores a different region of modification space than recent recommendations")

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
        parts.append("Balanced acquisition score across all criteria")

    return "; ".join(parts) + "."


def _what_we_learn(void: dict) -> str:
    """Describe what testing this void would teach us."""
    changes = void.get("changes", [])
    guide = void.get("guide_mods", [])

    learnings: list[str] = []

    # Check for specific modification types
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STANDALONE: run_dmtl_demo
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_dmtl_demo(
    n_cycles: int = 8,
    db: Session | None = None,
) -> dict:
    """Run a full DMTL demo simulation and return dashboard-ready output.

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

    # Run active learner
    learner = ActiveLearner(known_patterns=known, scored_voids=scored_voids)
    result = learner.simulate_dmtl_cycle(
        n_cycles=n_cycles,
        start_with_n_known=5,
    )

    # Format for dashboard
    dashboard = {
        "title": f"DMTL Simulation: {n_cycles} Cycles",
        "summary": {
            "total_cycles": result["total_patterns_explored"],
            "uncertainty_reduction_pct": result["uncertainty_reduction"],
            "coverage_improvement_pct": result["coverage_improvement"],
            "patterns_available": len(known),
            "voids_scored": len(scored_voids),
        },
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
