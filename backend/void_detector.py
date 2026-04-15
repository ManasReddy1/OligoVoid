"""Void detection engine for OligoVoid.

Detects untested siRNA modification patterns ("voids") by:
  1. Enumerating variants of known patterns (1-3 position changes)
  2. Filtering by biophysical feasibility rules
  3. Computing Hamming distance and novelty scores
  4. Classifying voids by exploration type and synthesis risk

Also provides legacy co-occurrence-based void detection for the original
(position:mod, position:mod) pair scanning approach.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from itertools import combinations
from typing import Any

from sqlalchemy.orm import Session

from backend.database import CooccurrenceEntry, PublishedSiRNA, Void
from backend.modification_grammar import (
    ABBREVIATION_MAP,
    REVERSE_ABBREVIATION_MAP,
    SEED_REGION,
    CLEAVAGE_SITE,
    SUGAR_MODIFICATIONS,
    SugarMod,
    BackboneMod,
    SiRNAModificationPattern,
    SiRNAPattern,
    PositionModification,
    FeasibilityViolation,
    all_positions,
    check_feasibility,
    compute_feasibility_score,
)
from backend.literature_parser import PUBLISHED_MODIFICATIONS_DATASET

logger = logging.getLogger(__name__)

DEFAULT_VOID_THRESHOLD = 3  # fewer than this many observations = void

# Modifications that are rigid/bulky — restricted at certain positions
_RIGID_MODS = {"LNA", "cEt"}
_CLEAVAGE_UNSAFE = {"LNA", "cEt", "MOE", "UNA"}
_ALL_SUGAR_MODS = [m.value for m in SugarMod]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. ENUMERATE MODIFICATION VOIDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def enumerate_modification_voids(
    known_patterns: list[dict] | None = None,
    max_positions_changed: int = 3,
) -> list[dict]:
    """Generate candidate voids by mutating known patterns at 1-3 positions.

    Algorithm:
      1. Take each known pattern as a "seed"
      2. Generate all variants with 1, 2, or 3 position changes
      3. Check if the variant already exists in known_patterns (Hamming check)
      4. Apply biological filters to reject infeasible variants
      5. Return filtered list of void candidates

    Biological filters:
      - Reject if rigid mod (LNA/cEt/MOE/UNA) at cleavage site (g10-g11)
      - Reject if >2 LNA/cEt in seed region (g2-g8)
      - Reject if >3 consecutive LNA anywhere on guide
      - Reject if nuclease_resistance < 0.30 (too unstable)

    Args:
        known_patterns: List of pattern dicts with guide_mods/passenger_mods.
                       If None, uses PUBLISHED_MODIFICATIONS_DATASET.
        max_positions_changed: Maximum positions to mutate (1, 2, or 3).

    Returns:
        List of void candidate dicts with guide_mods, passenger_mods,
        source_pattern_id, positions_changed, hamming_to_nearest, etc.
    """
    if known_patterns is None:
        known_patterns = PUBLISHED_MODIFICATIONS_DATASET

    # Build a set of known pattern fingerprints for dedup
    known_fps: set[str] = set()
    for pat in known_patterns:
        fp = _pattern_fingerprint(pat["guide_mods"], pat["passenger_mods"])
        known_fps.add(fp)

    candidates: list[dict] = []
    seen_fps: set[str] = set()

    # Use a representative subset of known patterns as seeds to avoid
    # combinatorial explosion (pick unique fingerprints only)
    seed_patterns: list[dict] = []
    seed_fps: set[str] = set()
    for pat in known_patterns:
        fp = _pattern_fingerprint(pat["guide_mods"], pat["passenger_mods"])
        if fp not in seed_fps:
            seed_fps.add(fp)
            seed_patterns.append(pat)

    for seed in seed_patterns:
        guide = seed["guide_mods"]
        passenger = seed["passenger_mods"]
        source_id = seed.get("pattern_id", "unknown")

        # Generate mutations at 1..max_positions_changed positions
        for n_changes in range(1, max_positions_changed + 1):
            new_candidates = _generate_mutations(
                guide, passenger, n_changes, source_id,
                known_fps, seen_fps, known_patterns,
            )
            candidates.extend(new_candidates)

            # Cap total candidates to prevent runaway
            if len(candidates) >= 2000:
                break

        if len(candidates) >= 2000:
            break

    logger.info(
        "Enumerated %d void candidates from %d seed patterns (max %d changes)",
        len(candidates), len(seed_patterns), max_positions_changed,
    )
    return candidates


def _generate_mutations(
    guide: list[str],
    passenger: list[str],
    n_changes: int,
    source_id: str,
    known_fps: set[str],
    seen_fps: set[str],
    known_patterns: list[dict],
) -> list[dict]:
    """Generate all n-position mutations of a seed pattern.

    For efficiency, only mutates the guide strand (the biologically
    more critical strand). Passenger mutations are a secondary concern.
    """
    results: list[dict] = []

    # Choose which positions to mutate
    guide_positions = list(range(21))

    # For n_changes=1, try all positions. For n>1, limit to interesting regions.
    if n_changes == 1:
        position_combos = [(p,) for p in guide_positions]
    elif n_changes == 2:
        # Focus on biologically interesting position pairs
        interesting = list(range(0, 8)) + list(range(9, 11)) + list(range(17, 21))
        position_combos = list(combinations(interesting, 2))
    else:
        # For n_changes=3, sample from regions
        seed_pos = list(range(1, 8))
        three_prime = list(range(17, 21))
        other = [0, 8, 9, 10, 11, 12]
        position_combos = []
        for a in seed_pos[:3]:
            for b in three_prime[:2]:
                for c in other[:2]:
                    position_combos.append((a, b, c))

    for positions in position_combos:
        # For each position combo, try each modification at each position
        mod_options_per_pos = []
        for pos in positions:
            current_mod = guide[pos]
            alternatives = [m for m in _ALL_SUGAR_MODS if m != current_mod]
            mod_options_per_pos.append(alternatives)

        # Generate all combinations of mods at the chosen positions
        # For n_changes=1: 7 options. For n=2: 49. For n=3: ~343 (capped).
        from itertools import product as itertools_product
        mod_combos = list(itertools_product(*mod_options_per_pos))

        # Cap for n_changes >= 2 to avoid explosion
        if len(mod_combos) > 20:
            # Sample: take first mod from each position's alternatives
            mod_combos = mod_combos[:20]

        for mods in mod_combos:
            new_guide = list(guide)
            changes_detail = []
            for pos, mod in zip(positions, mods):
                old = new_guide[pos]
                new_guide[pos] = mod
                changes_detail.append({
                    "position": pos + 1,
                    "strand": "guide",
                    "from": old,
                    "to": mod,
                })

            fp = _pattern_fingerprint(new_guide, passenger)

            # Skip if already known or already generated
            if fp in known_fps or fp in seen_fps:
                continue

            # Apply biological filters
            rejection = _apply_biological_filters(new_guide)
            if rejection is not None:
                continue

            seen_fps.add(fp)

            nearest_id, hamming = calculate_hamming_to_nearest(
                {"guide_mods": new_guide, "passenger_mods": passenger},
                known_patterns,
            )

            results.append({
                "guide_mods": new_guide,
                "passenger_mods": list(passenger),
                "source_pattern_id": source_id,
                "positions_changed": len(positions),
                "changes": changes_detail,
                "nearest_known_id": nearest_id,
                "hamming_to_nearest": hamming,
                "fingerprint": fp,
            })

            if len(results) >= 500:
                return results

    return results


def _apply_biological_filters(guide_mods: list[str]) -> str | None:
    """Apply biological feasibility filters to a candidate guide pattern.

    Returns None if the pattern passes all filters, or a rejection reason string.
    """
    # Filter 1: No rigid/bulky mods at cleavage site (g10-g11, 0-idx 9-10)
    for idx in [9, 10]:
        if guide_mods[idx] in _CLEAVAGE_UNSAFE:
            return f"Cleavage site (g{idx + 1}): {guide_mods[idx]} blocks Ago2 catalysis"

    # Filter 2: Max 2 LNA/cEt in seed region (g2-g8, 0-idx 1-7)
    rigid_in_seed = sum(1 for i in range(1, 8) if guide_mods[i] in _RIGID_MODS)
    if rigid_in_seed > 2:
        return f"Seed region: {rigid_in_seed} LNA/cEt (max 2 tolerated)"

    # Filter 3: No >3 consecutive LNA anywhere on guide
    consecutive_lna = 0
    for mod in guide_mods:
        if mod in _RIGID_MODS:
            consecutive_lna += 1
            if consecutive_lna > 3:
                return "More than 3 consecutive LNA/cEt — blocks helicase unwinding"
        else:
            consecutive_lna = 0

    # Filter 4: Minimum nuclease resistance (weighted average >= 0.30)
    total_resistance = sum(
        SUGAR_MODIFICATIONS.get(mod, {}).get("nuclease_resistance", 0.1)
        for mod in guide_mods
    )
    avg_resistance = total_resistance / len(guide_mods)
    if avg_resistance < 0.30:
        return f"Nuclease resistance too low ({avg_resistance:.2f} < 0.30)"

    return None


def _pattern_fingerprint(guide: list[str], passenger: list[str]) -> str:
    """Compute a 12-char hex fingerprint for a pattern."""
    raw = "|".join(guide) + "||" + "|".join(passenger)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. HAMMING DISTANCE TO NEAREST KNOWN PATTERN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calculate_hamming_to_nearest(
    candidate_pattern: dict,
    known_patterns: list[dict],
) -> tuple[str, int]:
    """Find the nearest known pattern by Hamming distance.

    Position-wise comparison of guide + passenger modification codes.

    Args:
        candidate_pattern: Dict with "guide_mods" and "passenger_mods" lists.
        known_patterns: List of known pattern dicts with same keys.

    Returns:
        (nearest_pattern_id, hamming_distance)
    """
    cand_g = candidate_pattern["guide_mods"]
    cand_p = candidate_pattern["passenger_mods"]

    best_id = ""
    best_dist = 999

    for pat in known_patterns:
        pat_g = pat.get("guide_mods", [])
        pat_p = pat.get("passenger_mods", [])

        dist = _hamming(cand_g, pat_g) + _hamming(cand_p, pat_p)

        if dist < best_dist:
            best_dist = dist
            best_id = pat.get("pattern_id", "")

    return best_id, best_dist


def _hamming(a: list[str], b: list[str]) -> int:
    """Position-wise Hamming distance between two modification lists."""
    return sum(1 for x, y in zip(a, b) if x != y)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. VOID NOVELTY SCORE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_void_novelty_score(
    candidate: dict,
    known_patterns: list[dict] | None = None,
) -> float:
    """Compute a 0-100 novelty score for a void candidate.

    Higher score = more different from all known patterns.

    Components:
      - Min Hamming distance (0-42 positions, normalized to 0-50 points)
      - Coverage density penalty: how many known patterns are "nearby" (0-25 points)
      - Modification rarity bonus: using rare mods scores higher (0-25 points)

    Args:
        candidate: Dict with guide_mods and passenger_mods.
        known_patterns: Reference patterns. Defaults to PUBLISHED_MODIFICATIONS_DATASET.

    Returns:
        Float 0-100 (100 = maximally novel).
    """
    if known_patterns is None:
        known_patterns = PUBLISHED_MODIFICATIONS_DATASET

    cand_g = candidate["guide_mods"]
    cand_p = candidate["passenger_mods"]

    # ── Component 1: Minimum Hamming distance (0-50 points) ──────────
    distances = []
    for pat in known_patterns:
        d = _hamming(cand_g, pat["guide_mods"]) + _hamming(cand_p, pat["passenger_mods"])
        distances.append(d)

    min_dist = min(distances) if distances else 42
    # Normalize: 0 distance → 0 pts, 42 distance → 50 pts
    hamming_score = min(min_dist / 42.0 * 50.0, 50.0)

    # ── Component 2: Coverage density penalty (0-25 points) ──────────
    # Count how many known patterns are within Hamming distance ≤ 5
    nearby = sum(1 for d in distances if d <= 5)
    # More nearby = less novel. 0 nearby → 25 pts, 10+ nearby → 0 pts
    density_score = max(0.0, 25.0 - nearby * 2.5)

    # ── Component 3: Modification rarity bonus (0-25 points) ─────────
    # Count usage frequency of each mod across all known patterns
    mod_freq: dict[str, int] = defaultdict(int)
    total_positions = 0
    for pat in known_patterns:
        for mod in pat["guide_mods"] + pat["passenger_mods"]:
            mod_freq[mod] += 1
            total_positions += 1

    # Calculate rarity of modifications used in candidate
    candidate_mods = cand_g + cand_p
    rarity_scores = []
    for mod in candidate_mods:
        freq = mod_freq.get(mod, 0)
        # Lower frequency → higher rarity score
        if total_positions > 0:
            rarity = 1.0 - (freq / total_positions)
        else:
            rarity = 1.0
        rarity_scores.append(rarity)

    avg_rarity = sum(rarity_scores) / len(rarity_scores) if rarity_scores else 0
    rarity_score = avg_rarity * 25.0

    total = round(hamming_score + density_score + rarity_score, 1)
    return min(100.0, max(0.0, total))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. VOID TYPE CLASSIFICATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def classify_void_type(candidate: dict) -> dict[str, str]:
    """Classify a void candidate into a research exploration category.

    Returns:
        {
            "void_type": one of [
                "conservative_variant",   — 1-2 positions changed
                "regional_explorer",      — changes in a specific functional region
                "modification_pioneer",   — uses a rare modification (UNA/cEt/MOE/DNA)
                "chemistry_hybrid",       — combines two distinct known chemistries
            ],
            "exploration_risk": "low" | "medium" | "high",
            "estimated_synthesis_complexity": "easy" | "moderate" | "hard",
        }
    """
    guide = candidate["guide_mods"]
    passenger = candidate.get("passenger_mods", [])
    hamming = candidate.get("hamming_to_nearest", 0)
    changes = candidate.get("changes", [])
    n_changed = candidate.get("positions_changed", len(changes))

    # ── Determine void_type ──────────────────────────────────────────
    rare_mods = {"UNA", "cEt", "MOE", "LNA", "DNA"}
    rare_in_guide = sum(1 for m in guide if m in rare_mods)
    rare_in_passenger = sum(1 for m in passenger if m in rare_mods)

    # Check if changes are concentrated in a functional region
    change_positions = [c["position"] for c in changes] if changes else []
    in_seed = sum(1 for p in change_positions if 2 <= p <= 8)
    in_cleavage = sum(1 for p in change_positions if p in (10, 11))
    in_3prime = sum(1 for p in change_positions if 19 <= p <= 21)

    # Check for chemistry hybridization: multiple distinct mod types
    unique_mods_guide = set(guide)
    unique_mods_passenger = set(passenger)
    distinct_chemistries = len((unique_mods_guide | unique_mods_passenger) - {"2'-OMe", "2'-F"})

    if distinct_chemistries >= 3:
        void_type = "chemistry_hybrid"
    elif distinct_chemistries >= 2 and rare_in_guide + rare_in_passenger >= 4:
        void_type = "chemistry_hybrid"
    elif rare_in_guide + rare_in_passenger >= 3:
        void_type = "modification_pioneer"
    elif n_changed <= 2 and hamming <= 3:
        void_type = "conservative_variant"
    elif in_seed >= 2 or in_cleavage >= 1 or in_3prime >= 2:
        void_type = "regional_explorer"
    elif n_changed == 1:
        void_type = "conservative_variant"
    else:
        void_type = "regional_explorer"

    # ── Determine exploration risk ───────────────────────────────────
    if void_type == "conservative_variant":
        risk = "low"
    elif void_type == "regional_explorer":
        risk = "medium" if in_cleavage == 0 else "high"
    elif void_type == "modification_pioneer":
        risk = "high" if rare_in_guide >= 5 else "medium"
    else:  # chemistry_hybrid
        risk = "high"

    # Override: very high hamming always = high risk
    if hamming >= 8:
        risk = "high"

    # ── Determine synthesis complexity ───────────────────────────────
    # Based on how many non-standard monomers are needed
    non_standard = {"UNA", "cEt", "MOE", "LNA", "MsPA"}
    all_mods = set(guide) | set(passenger)
    non_std_count = len(all_mods & non_standard)

    if non_std_count == 0:
        complexity = "easy"
    elif non_std_count <= 2:
        complexity = "moderate"
    else:
        complexity = "hard"

    return {
        "void_type": void_type,
        "exploration_risk": risk,
        "estimated_synthesis_complexity": complexity,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEGACY: CO-OCCURRENCE PAIR VOID DETECTION (database-backed)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_voids(
    db: Session,
    threshold: int = DEFAULT_VOID_THRESHOLD,
    position_filter: list[str] | None = None,
    mod_filter: list[str] | None = None,
) -> int:
    """Detect voids by comparing observed co-occurrence matrix against the
    full theoretical space.

    A void is a (posA:modA, posB:modB) pair observed fewer than `threshold`
    times across all published siRNAs.

    Returns:
        Number of new void records created.
    """
    cooc_entries = db.query(CooccurrenceEntry).all()
    observed: dict[str, int] = {e.pair_key: e.count for e in cooc_entries}

    positions = position_filter or all_positions()
    mods = mod_filter or [m.value for m in SugarMod]
    assignments = [(pos, mod) for pos in positions for mod in mods]

    new_voids = 0
    batch: list[Void] = []

    for (pos_a, mod_a), (pos_b, mod_b) in combinations(assignments, 2):
        pair_key = _canonical_key(pos_a, mod_a, pos_b, mod_b)
        count = observed.get(pair_key, 0)

        if count < threshold:
            existing = db.query(Void).filter(Void.pair_key == pair_key).first()
            if existing:
                existing.observation_count = count
                existing.is_void = True
                continue

            feas_score, rationale = _quick_feasibility(pos_a, mod_a, pos_b, mod_b)

            batch.append(Void(
                pos_a=pos_a, mod_a=mod_a,
                pos_b=pos_b, mod_b=mod_b,
                pair_key=pair_key,
                observation_count=count,
                is_void=True,
                feasibility_score=feas_score,
                feasibility_rationale=rationale,
            ))
            new_voids += 1

            if len(batch) >= 500:
                db.add_all(batch)
                db.commit()
                batch.clear()

    if batch:
        db.add_all(batch)
        db.commit()

    logger.info("Detected %d new voids (threshold=%d)", new_voids, threshold)
    return new_voids


def _canonical_key(pos_a: str, mod_a: str, pos_b: str, mod_b: str) -> str:
    a = f"{pos_a}:{mod_a}"
    b = f"{pos_b}:{mod_b}"
    if a > b:
        a, b = b, a
    return f"{a}|{b}"


def _quick_feasibility(
    pos_a: str, mod_a: str, pos_b: str, mod_b: str,
) -> tuple[float, str]:
    """Run a minimal feasibility check for a single co-occurrence pair."""
    pattern = SiRNAPattern(name="void_check")

    for pos_label, mod_name in [(pos_a, mod_a), (pos_b, mod_b)]:
        strand = "guide" if pos_label.startswith("g") else "passenger"
        position = int(pos_label[1:])
        try:
            sugar = SugarMod(mod_name)
        except ValueError:
            continue

        pm = PositionModification(strand=strand, position=position, sugar=sugar)
        if strand == "guide":
            pattern.guide.append(pm)
        else:
            pattern.passenger.append(pm)

    violations = check_feasibility(pattern)
    score = compute_feasibility_score(violations)
    rationale = (
        "; ".join(v.message for v in violations)
        if violations
        else "No rule violations detected."
    )
    return score, rationale


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEGACY: QUERY HELPERS (for main.py API endpoints)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_void_summary(db: Session) -> dict:
    """Return aggregate void statistics."""
    total_voids = db.query(Void).filter(Void.is_void == True).count()  # noqa: E712
    scored = db.query(Void).filter(Void.feasibility_score.isnot(None)).count()
    high_feasibility = db.query(Void).filter(
        Void.is_void == True,  # noqa: E712
        Void.feasibility_score >= 0.7,
    ).count()

    return {
        "total_voids": total_voids,
        "scored_voids": scored,
        "high_feasibility_voids": high_feasibility,
    }


def get_voids_by_position(db: Session, position: str) -> list[dict]:
    """Return all voids involving a specific position."""
    voids = db.query(Void).filter(
        Void.is_void == True,  # noqa: E712
        (Void.pos_a == position) | (Void.pos_b == position),
    ).order_by(Void.feasibility_score.desc().nullslast()).all()

    return [_void_to_dict(v) for v in voids]


def get_top_voids(
    db: Session,
    limit: int = 50,
    min_feasibility: float | None = None,
) -> list[dict]:
    """Return the most promising voids, ranked by feasibility score."""
    q = db.query(Void).filter(Void.is_void == True)  # noqa: E712
    if min_feasibility is not None:
        q = q.filter(Void.feasibility_score >= min_feasibility)
    voids = q.order_by(Void.feasibility_score.desc().nullslast()).limit(limit).all()
    return [_void_to_dict(v) for v in voids]


def _void_to_dict(v: Void) -> dict:
    return {
        "id": v.id,
        "pos_a": v.pos_a,
        "mod_a": v.mod_a,
        "pos_b": v.pos_b,
        "mod_b": v.mod_b,
        "pair_key": v.pair_key,
        "observation_count": v.observation_count,
        "is_void": v.is_void,
        "feasibility_score": v.feasibility_score,
        "feasibility_rationale": v.feasibility_rationale,
        "claude_score": v.claude_score,
        "information_gain": v.information_gain,
        "closure_velocity": v.closure_velocity,
    }
