"""
Chemistry Fingerprint Module for OligoVoid.

Computes an 8-dimensional fingerprint that captures the chemical character of
an siRNA modification pattern.  Each dimension is biologically motivated:

1. alternation_score       – How alternating is the 2'-OMe / 2'-F pattern?
2. seed_region_2F_density  – Fraction of guide positions 2-8 that are 2'-F.
3. three_prime_protection_score – Stabilizing mods at guide positions 17-21.
4. strand_asymmetry        – RISC-loading bias between guide and passenger.
5. consecutive_LNA_max     – Longest run of consecutive LNA residues.
6. modification_diversity  – Normalised Shannon entropy of mod-type distribution.
7. galnac_compatible       – Binary flag for GalNAc conjugation compatibility.
8. similarity_to_givosiran – Hamming similarity to Givosiran (best FDA drug, 83%).

A composite fingerprint_quality_score (0-100) and a plain-English
fingerprint_interpretation are also returned.

Author: Manas Reddy
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

import numpy as np

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Givosiran guide modifications – the best-performing FDA-approved siRNA (83%).
GIVOSIRAN_GUIDE_MODS: list[str] = [
    "2'-OMe", "2'-F", "2'-OMe", "2'-OMe", "2'-OMe", "2'-F", "2'-OMe",
    "2'-F", "2'-OMe", "2'-OMe", "2'-OMe", "2'-OMe", "2'-OMe", "2'-F",
    "2'-OMe", "2'-F", "2'-OMe", "2'-OMe", "2'-OMe", "2'-OMe", "2'-OMe",
]

# RISC-loading compatibility scores per modification type.
# Higher values indicate a modification that is more tolerated by RISC.
RISC_SCORES: dict[str, float] = {
    "2'-F":   0.90,
    "2'-OMe": 0.95,
    "LNA":    0.45,
    "cEt":    0.50,
    "DNA":    0.70,
    "RNA":    1.00,
    "UNA":    0.85,
    "MOE":    0.40,
}

# Modifications that are considered stabilising at the 3' end.
STABILISING_MODS: frozenset[str] = frozenset({"2'-OMe", "LNA", "cEt"})

# All recognised modification types (used for diversity calculation).
ALL_MOD_TYPES: list[str] = list(RISC_SCORES.keys())

# Quality-score weights.
_W_ALTERNATION: float = 20.0
_W_SEED_2F: float = 25.0
_W_END_STABLE: float = 15.0
_W_STRAND_ASYM: float = 20.0
_W_DIVERSITY: float = 10.0
_W_GALNAC: float = 5.0
_W_SIMILARITY: float = 5.0
_LNA_PENALTY_PER_EXCESS: float = 10.0
_LNA_PENALTY_THRESHOLD: int = 3


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _alternation_score(mods: list[str]) -> float:
    """Compute how alternating a 2'-OMe / 2'-F pattern is.

    Looks at consecutive pairs and counts how many alternate between
    the two ribose modifications.  A perfect ESC pattern (OMe-F-OMe-F-...)
    scores 1.0.

    Parameters
    ----------
    mods : list[str]
        Modification list for one strand.

    Returns
    -------
    float
        Score in [0.0, 1.0].
    """
    if len(mods) < 2:
        return 0.0

    target_pair = {"2'-OMe", "2'-F"}
    alternations = 0
    total_pairs = len(mods) - 1

    for i in range(total_pairs):
        if {mods[i], mods[i + 1]} == target_pair:
            alternations += 1

    return float(alternations) / float(total_pairs)


def _seed_region_2f_density(guide_mods: list[str]) -> float:
    """Fraction of guide positions 2-8 (1-indexed) that are 2'-F.

    The seed region (positions 2-8) is critical for target recognition.
    2'-F at these positions maintains A-form geometry for stable base-pairing
    while retaining nuclease resistance.

    Parameters
    ----------
    guide_mods : list[str]
        Guide strand modifications (1-indexed position i maps to index i-1).

    Returns
    -------
    float
        Density in [0.0, 1.0].
    """
    # Positions 2-8 correspond to indices 1-7.
    start_idx = 1
    end_idx = 8  # exclusive (positions 2 through 8 inclusive = indices 1..7)

    if len(guide_mods) < end_idx:
        # Use whatever positions are available in the seed region.
        region = guide_mods[start_idx:] if len(guide_mods) > start_idx else []
    else:
        region = guide_mods[start_idx:end_idx]

    if not region:
        return 0.0

    f_count = sum(1 for m in region if m == "2'-F")
    return float(f_count) / float(len(region))


def _three_prime_protection_score(guide_mods: list[str]) -> float:
    """Fraction of guide positions 17-21 (1-indexed) with stabilising mods.

    The 3' overhang of the guide strand is vulnerable to exonucleases.
    Modifications such as 2'-OMe, LNA, and cEt confer metabolic stability.

    Parameters
    ----------
    guide_mods : list[str]
        Guide strand modifications.

    Returns
    -------
    float
        Protection score in [0.0, 1.0].
    """
    # Positions 17-21 correspond to indices 16-20.
    start_idx = 16
    end_idx = 21  # exclusive

    if len(guide_mods) <= start_idx:
        return 0.0

    region = guide_mods[start_idx:end_idx]
    if not region:
        return 0.0

    protected = sum(1 for m in region if m in STABILISING_MODS)
    return float(protected) / float(len(region))


def _strand_asymmetry(
    guide_mods: list[str],
    passenger_mods: list[str],
) -> float:
    """RISC-loading asymmetry between guide and passenger strands.

    A well-designed siRNA has an asymmetry that favours guide strand loading
    into Ago2.  We compute the mean RISC score for each strand and return
    the absolute difference, normalised to [0, 1].

    Parameters
    ----------
    guide_mods : list[str]
        Guide strand modifications.
    passenger_mods : list[str]
        Passenger (sense) strand modifications.

    Returns
    -------
    float
        Asymmetry score in [0.0, 1.0].
    """
    def _mean_risc(mods: list[str]) -> float:
        if not mods:
            return 0.0
        scores = [RISC_SCORES.get(m, 0.5) for m in mods]
        return float(np.mean(scores))

    guide_risc = _mean_risc(guide_mods)
    passenger_risc = _mean_risc(passenger_mods)

    return abs(guide_risc - passenger_risc)


def _consecutive_lna_max(mods: list[str]) -> int:
    """Maximum number of consecutive LNA residues in a modification list.

    Excessive consecutive LNA can cause hepatotoxicity and reduce
    RISC loading.

    Parameters
    ----------
    mods : list[str]
        Modification list (typically the concatenation of guide + passenger).

    Returns
    -------
    int
        Length of the longest consecutive LNA run.  0 if no LNA present.
    """
    if not mods:
        return 0

    max_run = 0
    current_run = 0
    for m in mods:
        if m == "LNA":
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 0

    return max_run


def _modification_diversity(
    guide_mods: list[str],
    passenger_mods: list[str],
) -> float:
    """Normalised Shannon entropy of the modification-type distribution.

    Higher diversity (more distinct mod types used in balanced proportions)
    may indicate a more nuanced design that leverages each modification's
    unique biophysical properties.

    Parameters
    ----------
    guide_mods : list[str]
        Guide strand modifications.
    passenger_mods : list[str]
        Passenger strand modifications.

    Returns
    -------
    float
        Normalised entropy in [0.0, 1.0].  Returns 0.0 when all
        positions share the same modification or inputs are empty.
    """
    all_mods = list(guide_mods) + list(passenger_mods)
    if not all_mods:
        return 0.0

    counts = Counter(all_mods)
    n = len(all_mods)

    # Number of distinct types actually present.
    k = len(counts)
    if k <= 1:
        return 0.0

    # Shannon entropy H = -sum(p * log2(p)).
    entropy = 0.0
    for count in counts.values():
        p = count / n
        if p > 0:
            entropy -= p * math.log2(p)

    # Normalise by log2(k) so the result lies in [0, 1].
    max_entropy = math.log2(k)
    if max_entropy == 0:
        return 0.0

    return entropy / max_entropy


def _galnac_compatible(
    guide_mods: list[str],
    passenger_mods: list[str],
) -> int:
    """Determine whether the pattern is compatible with GalNAc conjugation.

    GalNAc delivery requires a predominantly 2'-OMe / 2'-F chemistry
    without excessive locked nucleic acids or unnatural nucleotides that
    interfere with ASGPR-mediated uptake.

    Heuristic rules:
    - At least 80% of positions must be 2'-OMe or 2'-F.
    - No more than 4 total LNA or cEt positions (combined strands).

    Parameters
    ----------
    guide_mods : list[str]
        Guide strand modifications.
    passenger_mods : list[str]
        Passenger strand modifications.

    Returns
    -------
    int
        1 if compatible, 0 otherwise.
    """
    all_mods = list(guide_mods) + list(passenger_mods)
    if not all_mods:
        return 0

    ome_or_f = sum(1 for m in all_mods if m in {"2'-OMe", "2'-F"})
    locked = sum(1 for m in all_mods if m in {"LNA", "cEt"})

    if ome_or_f / len(all_mods) >= 0.80 and locked <= 4:
        return 1
    return 0


def _similarity_to_givosiran(guide_mods: list[str]) -> float:
    """Normalised Hamming similarity between *guide_mods* and Givosiran.

    Givosiran (Givlaari) is the best-performing FDA-approved siRNA drug
    (83% clinical efficacy).  A high similarity score indicates that the
    input pattern follows a proven chemical design.

    Parameters
    ----------
    guide_mods : list[str]
        Guide strand modifications.

    Returns
    -------
    float
        Similarity in [0.0, 1.0].
    """
    if not guide_mods:
        return 0.0

    ref = GIVOSIRAN_GUIDE_MODS
    # Compare over the shared length.
    compare_len = min(len(guide_mods), len(ref))
    if compare_len == 0:
        return 0.0

    matches = sum(
        1 for a, b in zip(guide_mods[:compare_len], ref[:compare_len])
        if a == b
    )

    # Normalise by the length of the longer strand so that truncated
    # patterns do not get an artificially inflated score.
    max_len = max(len(guide_mods), len(ref))
    return float(matches) / float(max_len)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN PUBLIC FUNCTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_modification_fingerprint(
    guide_mods: list[str],
    passenger_mods: list[str],
) -> dict:
    """Compute an 8-dimensional chemistry fingerprint for an siRNA pattern.

    Parameters
    ----------
    guide_mods : list[str]
        Ordered list of sugar modifications for the guide (antisense) strand,
        one entry per nucleotide position.  Expected names: ``"2'-OMe"``,
        ``"2'-F"``, ``"LNA"``, ``"cEt"``, ``"DNA"``, ``"RNA"``, ``"UNA"``,
        ``"MOE"``.
    passenger_mods : list[str]
        Ordered list of sugar modifications for the passenger (sense) strand.

    Returns
    -------
    dict
        A dictionary with the following keys:

        * **alternation_score** (*float*, 0-1) --
          How alternating the 2'-OMe / 2'-F pattern is on the guide strand.
        * **seed_region_2F_density** (*float*, 0-1) --
          Fraction of guide positions 2-8 that are 2'-F.
        * **three_prime_protection_score** (*float*, 0-1) --
          Fraction of guide positions 17-21 with stabilising modifications.
        * **strand_asymmetry** (*float*, 0-1) --
          RISC-loading difference between guide and passenger.
        * **consecutive_LNA_max** (*int*) --
          Longest run of consecutive LNA residues across both strands.
        * **modification_diversity** (*float*, 0-1) --
          Normalised Shannon entropy of the mod-type distribution.
        * **galnac_compatible** (*int*, 0 or 1) --
          Whether the pattern is compatible with GalNAc conjugation.
        * **similarity_to_givosiran** (*float*, 0-1) --
          Hamming similarity to Givosiran's guide strand pattern.
        * **fingerprint_quality_score** (*float*, 0-100) --
          Composite quality score derived from weighted features.
        * **fingerprint_interpretation** (*str*) --
          Plain-English summary of what the fingerprint means.
    """
    # -- 1. Alternation score (guide strand) ---------------------------------
    alternation = _alternation_score(guide_mods)

    # -- 2. Seed region 2'-F density -----------------------------------------
    seed_2f = _seed_region_2f_density(guide_mods)

    # -- 3. 3' protection score ----------------------------------------------
    end_stable = _three_prime_protection_score(guide_mods)

    # -- 4. Strand asymmetry -------------------------------------------------
    strand_asym = _strand_asymmetry(guide_mods, passenger_mods)

    # -- 5. Consecutive LNA max (across both strands) ------------------------
    combined_mods = list(guide_mods) + list(passenger_mods)
    consec_lna = _consecutive_lna_max(combined_mods)

    # -- 6. Modification diversity -------------------------------------------
    diversity = _modification_diversity(guide_mods, passenger_mods)

    # -- 7. GalNAc compatibility ---------------------------------------------
    galnac_ok = _galnac_compatible(guide_mods, passenger_mods)

    # -- 8. Similarity to Givosiran ------------------------------------------
    similarity = _similarity_to_givosiran(guide_mods)

    # -- Composite quality score (0-100) -------------------------------------
    raw_score = (
        alternation * _W_ALTERNATION
        + seed_2f * _W_SEED_2F
        + end_stable * _W_END_STABLE
        + strand_asym * _W_STRAND_ASYM
        + diversity * _W_DIVERSITY
        + galnac_ok * _W_GALNAC
        + similarity * _W_SIMILARITY
    )

    lna_penalty = max(0, consec_lna - _LNA_PENALTY_THRESHOLD) * _LNA_PENALTY_PER_EXCESS
    quality_score = float(np.clip(raw_score - lna_penalty, 0.0, 100.0))

    # -- Plain-English interpretation ----------------------------------------
    interpretation = _build_interpretation(
        alternation=alternation,
        seed_2f=seed_2f,
        end_stable=end_stable,
        strand_asym=strand_asym,
        consec_lna=consec_lna,
        diversity=diversity,
        galnac_ok=galnac_ok,
        similarity=similarity,
        quality_score=quality_score,
    )

    return {
        "alternation_score": round(float(alternation), 4),
        "seed_region_2F_density": round(float(seed_2f), 4),
        "three_prime_protection_score": round(float(end_stable), 4),
        "strand_asymmetry": round(float(strand_asym), 4),
        "consecutive_LNA_max": int(consec_lna),
        "modification_diversity": round(float(diversity), 4),
        "galnac_compatible": int(galnac_ok),
        "similarity_to_givosiran": round(float(similarity), 4),
        "fingerprint_quality_score": round(quality_score, 2),
        "fingerprint_interpretation": interpretation,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INTERPRETATION BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _build_interpretation(
    *,
    alternation: float,
    seed_2f: float,
    end_stable: float,
    strand_asym: float,
    consec_lna: int,
    diversity: float,
    galnac_ok: int,
    similarity: float,
    quality_score: float,
) -> str:
    """Build a plain-English interpretation of the fingerprint."""
    parts: list[str] = []

    # Overall quality band.
    if quality_score >= 80:
        parts.append(
            f"Overall quality score is {quality_score:.1f}/100, indicating "
            f"an excellent modification pattern with strong clinical potential."
        )
    elif quality_score >= 60:
        parts.append(
            f"Overall quality score is {quality_score:.1f}/100, indicating "
            f"a good modification pattern with room for optimisation."
        )
    elif quality_score >= 40:
        parts.append(
            f"Overall quality score is {quality_score:.1f}/100, indicating "
            f"a moderate pattern that would benefit from significant redesign."
        )
    else:
        parts.append(
            f"Overall quality score is {quality_score:.1f}/100, indicating "
            f"a weak modification pattern that is unlikely to perform well in vivo."
        )

    # Alternation.
    if alternation >= 0.8:
        parts.append(
            f"The guide strand shows strong 2'-OMe/2'-F alternation "
            f"({alternation:.0%}), consistent with proven ESC chemistry."
        )
    elif alternation >= 0.4:
        parts.append(
            f"The guide strand has partial alternation ({alternation:.0%}). "
            f"Consider increasing 2'-OMe/2'-F alternation for improved "
            f"nuclease resistance."
        )
    else:
        parts.append(
            f"The guide strand has low alternation ({alternation:.0%}). "
            f"An alternating 2'-OMe/2'-F pattern is recommended for "
            f"optimal ESC performance."
        )

    # Seed region.
    if seed_2f >= 0.5:
        parts.append(
            f"Seed region (positions 2-8) has high 2'-F density "
            f"({seed_2f:.0%}), supporting target recognition fidelity."
        )
    elif seed_2f >= 0.2:
        parts.append(
            f"Seed region 2'-F density is moderate ({seed_2f:.0%}). "
            f"Increasing 2'-F in positions 2-8 may improve target binding."
        )
    else:
        parts.append(
            f"Seed region has very low 2'-F density ({seed_2f:.0%}). "
            f"This could impair target recognition."
        )

    # 3' protection.
    if end_stable >= 0.8:
        parts.append(
            f"The 3' end (positions 17-21) is well protected "
            f"({end_stable:.0%} stabilising mods)."
        )
    elif end_stable >= 0.4:
        parts.append(
            f"The 3' end has moderate protection ({end_stable:.0%}). "
            f"Additional 2'-OMe or LNA at the 3' terminus could "
            f"improve metabolic stability."
        )
    else:
        parts.append(
            f"The 3' end is poorly protected ({end_stable:.0%}). "
            f"This strand may be rapidly degraded by 3'-exonucleases."
        )

    # LNA warning.
    if consec_lna > _LNA_PENALTY_THRESHOLD:
        parts.append(
            f"WARNING: {consec_lna} consecutive LNA residues detected. "
            f"Runs longer than {_LNA_PENALTY_THRESHOLD} are associated with "
            f"hepatotoxicity and reduced RISC loading. Quality score "
            f"penalised by {(consec_lna - _LNA_PENALTY_THRESHOLD) * _LNA_PENALTY_PER_EXCESS:.0f} points."
        )
    elif consec_lna > 0:
        parts.append(
            f"{consec_lna} consecutive LNA residue(s) detected, within safe limits."
        )

    # GalNAc.
    if galnac_ok:
        parts.append(
            "Pattern is compatible with GalNAc conjugation for hepatocyte delivery."
        )
    else:
        parts.append(
            "Pattern may not be compatible with GalNAc conjugation. "
            "Check modification composition if hepatocyte delivery is intended."
        )

    # Givosiran similarity.
    if similarity >= 0.8:
        parts.append(
            f"High similarity to Givosiran ({similarity:.0%}), "
            f"the best-performing FDA-approved siRNA (83% efficacy)."
        )
    elif similarity >= 0.5:
        parts.append(
            f"Moderate similarity to Givosiran ({similarity:.0%})."
        )
    else:
        parts.append(
            f"Low similarity to Givosiran ({similarity:.0%}). "
            f"The pattern deviates substantially from proven designs."
        )

    return " ".join(parts)
