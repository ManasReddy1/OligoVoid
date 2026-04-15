"""Feasibility scoring engine for OligoVoid.

The scientific core: scores how feasible each void modification pattern is
using BOTH rule-based biophysics AND Claude API enhanced reasoning.

Scoring layers:
  1. Rule-based biophysics — four sub-scores (thermo, RISC, nuclease, off-target)
  2. Claude LLM — contextual reasoning, mechanistic insight, experiment design

Both scores are stored independently so researchers can weight them.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic
from sqlalchemy.orm import Session

from backend.database import Void, VoidFeasibilityScore, ModificationVoid
from backend.modification_grammar import (
    SUGAR_MODIFICATIONS,
    BACKBONE_MODIFICATIONS,
    ABBREVIATION_MAP,
    REVERSE_ABBREVIATION_MAP,
    SUGAR_MODS_LIST,
    SugarMod,
    BackboneMod,
    PositionModification,
    SiRNAPattern,
    SiRNAModificationPattern,
    check_feasibility,
    compute_feasibility_score,
    SEED_REGION,
    CLEAVAGE_SITE,
    THREE_PRIME_OVERHANG,
    SUPPLEMENTARY,
)

logger = logging.getLogger(__name__)

# Abbreviation → full mod name for display
_DISPLAY_NAMES: dict[str, str] = {
    "2'-OMe": "2OMe", "2'-F": "2F", "LNA": "LNA", "cEt": "cEt",
    "DNA": "DNA", "RNA": "RNA", "UNA": "UNA", "MOE": "MOE",
}

# Published ΔTm per modification (°C per substitution vs unmodified RNA)
_DELTA_TM: dict[str, float] = {
    "2'-OMe": +1.0, "2'-F": +1.8, "LNA": +4.0, "cEt": +3.5,
    "DNA": -1.5, "RNA": 0.0, "UNA": -2.0, "MOE": +2.0,
}

# RISC tolerance values (from modification_grammar)
_RISC_TOLERANCE: dict[str, float] = {
    k: v["risc_tolerance"] for k, v in SUGAR_MODIFICATIONS.items()
}

# Nuclease resistance values
_NUCLEASE_RESISTANCE: dict[str, float] = {
    k: v["nuclease_resistance"] for k, v in SUGAR_MODIFICATIONS.items()
}

# Sets for quick lookup
_RIGID_MODS = {"LNA", "cEt"}
_CLEAVAGE_UNSAFE = {"LNA", "cEt", "MOE", "UNA"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 1: RULE-BASED BIOPHYSICS SCORER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def calculate_thermodynamic_score(pattern: dict) -> float:
    """Predict thermodynamic stability score (0-100).

    Uses simplified ΔTm rules from published SAR data:
      2'-OMe: +1.0°C/pos    2'-F: +1.8°C/pos    LNA: +4.0°C/pos
      cEt: +3.5°C/pos       DNA: -1.5°C/pos      RNA: ±0.0°C/pos
      UNA: -2.0°C/pos       MOE: +2.0°C/pos

    Optimal total ΔTm from native RNA duplex: +5°C to +15°C.
      Below +3°C: too unstable → score penalty
      Above +20°C: too rigid, RISC loading impaired → penalty

    Returns normalized 0-100 score.
    """
    guide = pattern.get("guide_mods", [])
    passenger = pattern.get("passenger_mods", [])

    # Calculate total ΔTm for the duplex.
    # Published ΔTm values are per-substitution vs RNA. When many positions
    # are substituted, contributions are sub-additive (non-nearest-neighbor
    # effects diminish). Empirically, fully modified ESC duplexes show
    # ΔTm ≈ +10-15°C, not the +58°C that strict additivity predicts.
    # We model this as: average per-position contribution × cooperativity.
    guide_delta_tm = sum(_DELTA_TM.get(m, 0.0) for m in guide)
    passenger_delta_tm = sum(_DELTA_TM.get(m, 0.0) for m in passenger)

    # Per-position average, then multiply by sqrt(n_positions) to model
    # sub-additive scaling. This gives ESC ≈ +12°C (optimal zone).
    n_pos = len(guide) + len(passenger)
    avg_per_pos = (guide_delta_tm + passenger_delta_tm) / max(n_pos, 1)
    total_delta_tm = avg_per_pos * (n_pos ** 0.5)  # sqrt(42) ≈ 6.5

    # Score based on optimal window: +5 to +15°C
    if 5.0 <= total_delta_tm <= 15.0:
        # Optimal zone: linear scale 80-100
        center = 10.0
        deviation = abs(total_delta_tm - center) / 5.0
        score = 100.0 - deviation * 20.0
    elif 3.0 <= total_delta_tm < 5.0:
        # Slightly unstable: 60-80
        score = 60.0 + (total_delta_tm - 3.0) / 2.0 * 20.0
    elif 15.0 < total_delta_tm <= 20.0:
        # Slightly too rigid: 60-80
        score = 80.0 - (total_delta_tm - 15.0) / 5.0 * 20.0
    elif 0.0 <= total_delta_tm < 3.0:
        # Unstable: 30-60
        score = 30.0 + total_delta_tm / 3.0 * 30.0
    elif total_delta_tm > 20.0:
        # Way too rigid: 20-60
        score = max(20.0, 60.0 - (total_delta_tm - 20.0) * 4.0)
    else:
        # Negative ΔTm: very unstable
        score = max(10.0, 30.0 + total_delta_tm * 5.0)

    return max(0.0, min(100.0, round(score, 1)))


def calculate_risc_loading_score(pattern: dict) -> float:
    """Predict RISC loading efficiency (0-100).

    Key rules from published Ago2 structural/biochemical studies:
      1. Guide seed (pos 2-8): penalize rigid mods
         - LNA in seed: -15/position
         - cEt in seed: -12/position
         - MOE in seed: -20/position (too bulky)
         - 2'-F in seed: no penalty (well-tolerated)
         - 2'-OMe in seed: -3/position (mild)

      2. Cleavage site (pos 10-11): must be flexible
         - LNA/cEt/MOE/UNA: -25/position (fatal penalty)
         - 2'-OMe, 2'-F, DNA, RNA: OK

      3. Guide 5' end (pos 1-4): affects Ago2 MID domain loading
         - PS backbone at pos 1-2: +5 points
         - UNA at pos 1: +8 points (favors guide strand selection)

      4. Overall guide strand rigidity:
         - If >30% LNA/cEt: additional -15

    Returns 0-100 score.
    """
    guide = pattern.get("guide_mods", [])
    backbone_guide = pattern.get("backbone_guide", [])
    score = 85.0  # start at "good"

    # ── Seed region penalties (0-indexed 1..7 = positions 2-8) ───────
    for i in range(1, min(8, len(guide))):
        mod = guide[i]
        if mod == "LNA":
            score -= 15.0
        elif mod == "cEt":
            score -= 12.0
        elif mod == "MOE":
            score -= 20.0
        elif mod == "2'-OMe":
            score -= 3.0
        # 2'-F, DNA, RNA: no penalty

    # ── Cleavage site (0-indexed 9, 10 = positions 10-11) ───────────
    for i in [9, 10]:
        if i < len(guide) and guide[i] in _CLEAVAGE_UNSAFE:
            score -= 25.0

    # ── 5' end bonuses (positions 1-4) ──────────────────────────────
    if backbone_guide and len(backbone_guide) >= 2:
        if backbone_guide[0] == "PS" and backbone_guide[1] == "PS":
            score += 5.0

    if guide and guide[0] == "UNA":
        score += 8.0  # thermodynamic strand selection advantage

    # ── Overall rigidity penalty ────────────────────────────────────
    rigid_count = sum(1 for m in guide if m in _RIGID_MODS)
    if len(guide) > 0 and rigid_count / len(guide) > 0.30:
        score -= 15.0

    # ── 2'-F in seed bonus (promotes RISC loading) ──────────────────
    f_in_seed = sum(1 for i in range(1, min(8, len(guide))) if guide[i] == "2'-F")
    if f_in_seed >= 3:
        score += 5.0

    return max(0.0, min(100.0, round(score, 1)))


def calculate_nuclease_resistance_score(pattern: dict) -> float:
    """Predict resistance to serum and intracellular nucleases (0-100).

    Key rules:
      1. PS backbone at 5' guide end (linkages 0-1): +12 each
      2. PS backbone at 3' guide end (linkages 18-19): +10 each
      3. PS backbone at 5' passenger end (linkages 0-1): +7.5 each
      4. 2'-OMe at any position: +2 each (max +20 from OMe alone)
      5. LNA/cEt at any position: +4 each (max +20)
      6. 2'-F contribution: +1.5/position (max +15)
      7. MOE contribution: +3/position (max +15)
      8. Unmodified RNA at non-terminal positions: -5 each
      9. MsPA backbone: +3 each (slightly better than PS)

    Minimum viable score for a drug candidate: ~60
    Returns 0-100 score.
    """
    guide = pattern.get("guide_mods", [])
    passenger = pattern.get("passenger_mods", [])
    bb_g = pattern.get("backbone_guide", [])
    bb_p = pattern.get("backbone_passenger", [])

    score = 20.0  # baseline

    # ── Backbone contributions ──────────────────────────────────────
    # Guide 5' end
    for i in [0, 1]:
        if i < len(bb_g):
            if bb_g[i] == "PS":
                score += 12.0
            elif bb_g[i] == "MsPA":
                score += 13.0

    # Guide 3' end
    for i in [18, 19]:
        if i < len(bb_g):
            if bb_g[i] == "PS":
                score += 10.0
            elif bb_g[i] == "MsPA":
                score += 11.0

    # Passenger 5' end
    for i in [0, 1]:
        if i < len(bb_p):
            if bb_p[i] == "PS":
                score += 7.5
            elif bb_p[i] == "MsPA":
                score += 8.0

    # Passenger 3' end
    for i in [18, 19]:
        if i < len(bb_p):
            if bb_p[i] == "PS":
                score += 5.0
            elif bb_p[i] == "MsPA":
                score += 5.5

    # ── Sugar modification contributions (both strands) ─────────────
    all_mods = list(guide) + list(passenger)
    ome_bonus = min(20.0, sum(2.0 for m in all_mods if m == "2'-OMe"))
    lna_bonus = min(20.0, sum(4.0 for m in all_mods if m in ("LNA", "cEt")))
    f_bonus = min(15.0, sum(1.5 for m in all_mods if m == "2'-F"))
    moe_bonus = min(15.0, sum(3.0 for m in all_mods if m == "MOE"))

    score += ome_bonus + lna_bonus + f_bonus + moe_bonus

    # ── RNA penalty (unmodified positions, excluding terminal overhangs)
    for i in range(len(guide)):
        if guide[i] == "RNA" and 2 <= i <= 18:  # non-terminal
            score -= 5.0

    for i in range(len(passenger)):
        if passenger[i] == "RNA" and 2 <= i <= 18:
            score -= 5.0

    return max(0.0, min(100.0, round(score, 1)))


def calculate_off_target_risk_score(pattern: dict) -> float:
    """Predict off-target gene silencing risk (0-100).

    LOWER score = LOWER risk = BETTER.

    Key rules:
      1. Passenger strand seed (pos 2-8 of passenger):
         - 2'-OMe at 2+ positions: -15 risk (reduces off-target loading)
         - UNA at any seed position: -10 risk (destabilizes passenger RISC)

      2. Guide seed region (pos 2-8 of guide):
         - 2'-OMe at position 2: -10 risk (standard off-target reduction)
         - 2'-F at position 2: -5 risk
         - LNA in seed: +10 risk (enhanced seed binding = more off-targets)

      3. Passenger strand loading potential:
         - All-OMe passenger: -15 (passenger loading unlikely)
         - High 2'-F on passenger: +10 (may load into RISC)

      4. Immunostimulatory risk:
         - PS linkages > 10 on either strand: +15 risk
         - MsPA linkages: +5 risk (lower than PS)
         - >80% unmodified RNA: +20 risk (immune recognition)

    Returns 0-100 where LOWER is better.
    """
    guide = pattern.get("guide_mods", [])
    passenger = pattern.get("passenger_mods", [])
    bb_g = pattern.get("backbone_guide", [])
    bb_p = pattern.get("backbone_passenger", [])

    risk = 40.0  # baseline risk

    # ── Passenger seed OMe suppression ──────────────────────────────
    passenger_seed_ome = sum(
        1 for i in range(1, min(8, len(passenger)))
        if passenger[i] == "2'-OMe"
    )
    if passenger_seed_ome >= 2:
        risk -= 15.0

    # Passenger seed UNA
    for i in range(1, min(8, len(passenger))):
        if i < len(passenger) and passenger[i] == "UNA":
            risk -= 10.0

    # All-OMe passenger bonus
    if passenger and all(m == "2'-OMe" for m in passenger):
        risk -= 15.0

    # High-F passenger penalty
    f_on_passenger = sum(1 for m in passenger if m == "2'-F")
    if f_on_passenger >= 10:
        risk += 10.0

    # ── Guide seed off-target modulation ────────────────────────────
    if len(guide) > 1 and guide[1] == "2'-OMe":
        risk -= 10.0
    elif len(guide) > 1 and guide[1] == "2'-F":
        risk -= 5.0

    # LNA in guide seed increases off-target binding
    lna_in_seed = sum(
        1 for i in range(1, min(8, len(guide)))
        if guide[i] in _RIGID_MODS
    )
    risk += lna_in_seed * 10.0

    # ── Immunostimulatory risk ──────────────────────────────────────
    ps_count_g = sum(1 for b in bb_g if b == "PS")
    ps_count_p = sum(1 for b in bb_p if b == "PS")
    if ps_count_g > 10 or ps_count_p > 10:
        risk += 15.0

    mspa_count = sum(1 for b in bb_g + bb_p if b == "MsPA")
    if mspa_count > 0:
        risk += 5.0

    # Unmodified RNA immune detection
    all_mods = list(guide) + list(passenger)
    rna_count = sum(1 for m in all_mods if m == "RNA")
    if len(all_mods) > 0 and rna_count / len(all_mods) > 0.80:
        risk += 20.0

    return max(0.0, min(100.0, round(risk, 1)))


def _calculate_seed_region_compatibility(pattern: dict) -> float:
    """Score seed region (g2-g8) compatibility (0-100).

    Higher = more compatible with efficient target recognition.
    """
    guide = pattern.get("guide_mods", [])
    score = 90.0

    for i in range(1, min(8, len(guide))):
        mod = guide[i]
        if mod == "2'-F":
            score += 1.0  # ideal for seed
        elif mod == "2'-OMe":
            score -= 1.0  # acceptable
        elif mod == "LNA":
            score -= 12.0  # problematic
        elif mod == "cEt":
            score -= 10.0
        elif mod == "MOE":
            score -= 15.0  # too bulky
        elif mod == "UNA":
            score -= 3.0  # flexible, reduces off-target but weaker binding
        elif mod == "DNA":
            score -= 2.0  # lower affinity
        # RNA: no change (natural)

    return max(0.0, min(100.0, round(score, 1)))


def score_pattern_biophysics(pattern: dict) -> dict:
    """Master biophysics scorer — runs all sub-scores and computes weighted composite.

    Args:
        pattern: Dict with guide_mods, passenger_mods, backbone_guide,
                 backbone_passenger, conjugate.

    Returns:
        Complete scoring dict with all sub-scores and overall composite.
    """
    thermo = calculate_thermodynamic_score(pattern)
    risc = calculate_risc_loading_score(pattern)
    nuclease = calculate_nuclease_resistance_score(pattern)
    off_target_risk = calculate_off_target_risk_score(pattern)
    off_target_display = round(100.0 - off_target_risk, 1)
    seed_compat = _calculate_seed_region_compatibility(pattern)

    # Weighted composite — RISC loading is the most critical factor
    overall = (
        thermo * 0.20
        + risc * 0.35
        + nuclease * 0.25
        + off_target_display * 0.20
    )

    # Predict knockdown based on composite (simplified linear model)
    # Overall 80+ → ~80% knockdown, 60 → ~60%, 40 → ~35%
    if overall >= 70:
        predicted_kd = 50.0 + (overall - 70.0) * 1.5
    elif overall >= 50:
        predicted_kd = 30.0 + (overall - 50.0)
    else:
        predicted_kd = max(5.0, overall * 0.6)
    predicted_kd = min(98.0, predicted_kd)

    return {
        "thermodynamic_score": round(thermo, 1),
        "risc_loading_score": round(risc, 1),
        "nuclease_resistance_score": round(nuclease, 1),
        "off_target_risk_score": round(off_target_risk, 1),
        "off_target_display_score": off_target_display,
        "seed_region_compatibility": round(seed_compat, 1),
        "overall_oligovoid_score": round(overall, 1),
        "predicted_knockdown_pct": round(predicted_kd, 1),
        "scored_by": "biophysics_rules",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STRAND DISPLAY FORMATTING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def format_guide_strand(pattern: dict) -> str:
    """Format the 21-position guide strand as a human-readable string.

    Example output:
      5'-[2OMe]1 [2F]2 [2OMe]3 [2F]4 [2F]5* [2F]6* [2F]7* [2F]8* [2OMe]9
          [2OMe]10^ [2OMe]11^ [2OMe]12 [2OMe]13 [2OMe]14 [2OMe]15 [2OMe]16
          [2OMe]17 [2OMe]18 [LNA]19† [LNA]20† [2OMe]21†-3'

    Annotations: * = seed region, ^ = cleavage site, † = 3' overhang
    """
    guide = pattern.get("guide_mods", [])
    return _format_strand(guide, "guide", pattern.get("conjugate", "None"))


def format_passenger_strand(pattern: dict) -> str:
    """Format the 21-position passenger strand as a human-readable string."""
    passenger = pattern.get("passenger_mods", [])
    conjugate = pattern.get("conjugate", "None")
    return _format_strand(passenger, "passenger", conjugate)


def _format_strand(mods: list[str], strand: str, conjugate: str) -> str:
    """Internal strand formatter with position annotations."""
    parts: list[str] = []
    for i, mod in enumerate(mods):
        pos = i + 1
        display = _DISPLAY_NAMES.get(mod, mod)

        # Position annotations
        annotation = ""
        if strand == "guide":
            if 2 <= pos <= 8:
                annotation = "*"     # seed
            elif pos in (10, 11):
                annotation = "^"     # cleavage
            elif 19 <= pos <= 21:
                annotation = "†"     # 3' overhang
        else:  # passenger
            if 2 <= pos <= 8:
                annotation = "~"     # seed match

        parts.append(f"[{display}]{pos}{annotation}")

    # Add conjugate indicator
    prefix = "5'-"
    suffix = "-3'"
    if strand == "passenger" and conjugate and conjugate != "None":
        suffix = f"-[{conjugate}]-3'"

    return prefix + " ".join(parts) + suffix


def format_backbone(backbone: list[str], strand_name: str) -> str:
    """Format backbone as compact string showing only non-PO linkages."""
    non_po = [(i + 1, b) for i, b in enumerate(backbone) if b != "PO"]
    if not non_po:
        return f"{strand_name}: all PO (natural phosphodiester)"
    links = ", ".join(f"pos {p}-{p + 1}: {b}" for p, b in non_po)
    return f"{strand_name}: {links}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 2: CLAUDE API ENHANCED SCORER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CLAUDE_SYSTEM_PROMPT = """You are an expert RNA therapeutics researcher with deep knowledge of siRNA chemistry, RISC biology, and oligonucleotide drug design. You have expertise in interpreting chemical modification patterns and predicting their effects on siRNA efficacy and safety.

You are analyzing novel siRNA modification patterns that have never been published. Your job is to:
1. Evaluate the scientific rationale for this pattern
2. Predict likely knockdown efficacy based on known rules
3. Identify the most interesting scientific question this pattern raises
4. Suggest the most efficient experiment to validate it

Be specific and cite mechanisms, not generalities. Respond with valid JSON only."""


def _build_claude_user_prompt(
    pattern: dict,
    biophysics_scores: dict,
) -> str:
    """Build the user prompt for Claude scoring."""
    guide_display = format_guide_strand(pattern)
    passenger_display = format_passenger_strand(pattern)

    bb_g = pattern.get("backbone_guide", [])
    bb_p = pattern.get("backbone_passenger", [])
    backbone_display = (
        format_backbone(bb_g, "Guide") + "\n" + format_backbone(bb_p, "Passenger")
    )

    nearest = pattern.get("nearest_known_id", "unknown")
    changed = pattern.get("changes", [])
    if changed:
        changes_str = ", ".join(
            f"g{c['position']}: {c['from']} → {c['to']}" for c in changed
        )
    else:
        changes_str = f"Hamming distance: {pattern.get('hamming_to_nearest', '?')}"

    return f"""Analyze this siRNA modification pattern:

Guide strand (5'→3', positions 1-21):
{guide_display}

Passenger strand (5'→3', positions 1-21):
{passenger_display}

Backbone:
{backbone_display}

Terminal conjugate: {pattern.get('conjugate', 'None')}

Biophysics pre-scores:
- Thermodynamic stability: {biophysics_scores['thermodynamic_score']}/100
- RISC loading: {biophysics_scores['risc_loading_score']}/100
- Nuclease resistance: {biophysics_scores['nuclease_resistance_score']}/100
- Off-target risk: {biophysics_scores['off_target_risk_score']}/100 (lower is better)
- Seed region compatibility: {biophysics_scores['seed_region_compatibility']}/100
- Overall biophysics: {biophysics_scores['overall_oligovoid_score']}/100

Nearest known pattern: {nearest}
Positions changed from nearest: {changes_str}

Return ONLY this JSON:
{{
  "predicted_knockdown_pct": <int 0-100>,
  "prediction_confidence": "low|medium|high",
  "one_line_insight": "<one precise sentence about why this pattern is scientifically interesting>",
  "why_never_tested": "<hypothesis for why no lab has published this combination>",
  "key_risk": "<most likely failure mode with mechanism>",
  "key_opportunity": "<most exciting potential advantage>",
  "recommended_experiment": "<specific, actionable first experiment: cell line, target gene, assay type, readout — be precise>",
  "similar_drugs": "<approved drugs using similar logic, or 'None identified'>",
  "field_readiness": "ready_now|needs_enabling_chemistry|high_risk_high_reward"
}}"""


async def score_void_with_claude(
    pattern: dict,
    biophysics_scores: dict,
) -> dict:
    """Score a void pattern using Claude for expert mechanistic reasoning.

    Sends the pattern and pre-computed biophysics scores to Claude.
    Parses JSON response and merges with biophysics scores.

    Args:
        pattern: Dict with guide_mods, passenger_mods, backbone_guide,
                 backbone_passenger, conjugate, nearest_known_id, changes, etc.
        biophysics_scores: Output of score_pattern_biophysics().

    Returns:
        Combined dict with biophysics + Claude scores + insight fields.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_key_here":
        return {
            **biophysics_scores,
            "claude_score": None,
            "prediction_confidence": None,
            "one_line_insight": "Claude API not configured — using biophysics scores only",
            "why_never_tested": "",
            "key_risk": "",
            "key_opportunity": "",
            "recommended_experiment": "",
            "similar_drugs": "",
            "field_readiness": "",
            "scored_by": "biophysics_rules",
            "error": "missing_api_key",
        }

    prompt = _build_claude_user_prompt(pattern, biophysics_scores)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=CLAUDE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text.strip()

        # Extract JSON from possible markdown fences
        if "```" in text:
            for block in text.split("```"):
                stripped = block.strip()
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                if stripped.startswith("{"):
                    text = stripped
                    break

        claude_data = json.loads(text)

        # Merge biophysics + Claude scores
        return {
            **biophysics_scores,
            "claude_score": claude_data.get("predicted_knockdown_pct"),
            "predicted_knockdown_pct": claude_data.get(
                "predicted_knockdown_pct",
                biophysics_scores.get("predicted_knockdown_pct"),
            ),
            "prediction_confidence": claude_data.get("prediction_confidence", "medium"),
            "one_line_insight": claude_data.get("one_line_insight", ""),
            "why_never_tested": claude_data.get("why_never_tested", ""),
            "key_risk": claude_data.get("key_risk", ""),
            "key_opportunity": claude_data.get("key_opportunity", ""),
            "recommended_experiment": claude_data.get("recommended_experiment", ""),
            "similar_drugs": claude_data.get("similar_drugs", ""),
            "field_readiness": claude_data.get("field_readiness", ""),
            "scored_by": "biophysics_rules+claude",
        }

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Claude JSON: %s", exc)
        return {
            **biophysics_scores,
            "claude_score": None,
            "one_line_insight": "Claude response could not be parsed",
            "scored_by": "biophysics_rules",
            "error": "parse_error",
        }
    except anthropic.APIError as exc:
        logger.error("Anthropic API error: %s", exc)
        return {
            **biophysics_scores,
            "claude_score": None,
            "one_line_insight": f"Claude API error: {exc}",
            "scored_by": "biophysics_rules",
            "error": "api_error",
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATABASE PERSISTENCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def save_scores_to_db(
    db: Session,
    void_id: str,
    scores: dict,
) -> VoidFeasibilityScore:
    """Persist a scoring result to the VoidFeasibilityScore table.

    Args:
        db: SQLAlchemy session.
        void_id: The void_id string (from ModificationVoid).
        scores: Output of score_pattern_biophysics or score_void_with_claude.

    Returns:
        The created VoidFeasibilityScore record.
    """
    record = VoidFeasibilityScore(
        void_id=void_id,
        thermodynamic_score=scores.get("thermodynamic_score", 0.0),
        nuclease_resistance_score=scores.get("nuclease_resistance_score", 0.0),
        risc_loading_score=scores.get("risc_loading_score", 0.0),
        off_target_risk_score=scores.get("off_target_risk_score", 0.0),
        seed_region_compatibility=scores.get("seed_region_compatibility", 0.0),
        overall_oligovoid_score=scores.get("overall_oligovoid_score", 0.0),
        predicted_knockdown_pct=scores.get("predicted_knockdown_pct"),
        one_line_insight=scores.get("one_line_insight", ""),
        why_untested=scores.get("why_never_tested", ""),
        recommended_experiment=scores.get("recommended_experiment", ""),
        confidence_level=scores.get("prediction_confidence", "medium"),
        scored_by=scores.get("scored_by", "biophysics_rules"),
    )
    db.add(record)
    db.commit()
    return record


async def score_and_save(
    db: Session,
    void_id: str,
    pattern: dict,
    use_claude: bool = True,
) -> dict:
    """Score a pattern (biophysics + optionally Claude) and save to DB.

    Args:
        db: SQLAlchemy session.
        void_id: The void_id string.
        pattern: Full pattern dict.
        use_claude: Whether to also run Claude scoring.

    Returns:
        The combined scoring dict.
    """
    bio_scores = score_pattern_biophysics(pattern)

    if use_claude:
        combined = await score_void_with_claude(pattern, bio_scores)
    else:
        combined = {
            **bio_scores,
            "one_line_insight": _generate_biophysics_insight(pattern, bio_scores),
            "why_never_tested": "",
            "recommended_experiment": "",
        }

    save_scores_to_db(db, void_id, combined)
    return combined


def _generate_biophysics_insight(pattern: dict, scores: dict) -> str:
    """Generate a one-line insight from biophysics scores alone."""
    guide = pattern.get("guide_mods", [])
    overall = scores.get("overall_oligovoid_score", 0)

    # Identify the most unusual feature
    features: list[str] = []

    # Check for rare mods
    rare_mods_used = set()
    for m in guide:
        if m in ("UNA", "LNA", "cEt", "MOE", "DNA"):
            rare_mods_used.add(m)
    if rare_mods_used:
        features.append(f"uses {'/'.join(sorted(rare_mods_used))}")

    # Check seed composition
    seed = [guide[i] for i in range(1, min(8, len(guide)))]
    unique_seed = set(seed)
    if len(unique_seed) == 1:
        features.append(f"uniform {seed[0]} seed")
    elif "2'-F" in unique_seed and len(unique_seed) <= 2:
        features.append("F-enriched seed")

    # Check overall quality
    risc = scores.get("risc_loading_score", 0)
    nuclease = scores.get("nuclease_resistance_score", 0)

    if risc >= 85 and nuclease >= 80:
        quality = "well-balanced RISC loading and stability"
    elif risc >= 85:
        quality = "strong RISC loading but stability concerns"
    elif nuclease >= 80:
        quality = "high nuclease resistance but RISC loading may be impaired"
    else:
        quality = "moderate overall feasibility"

    feature_str = "; ".join(features) if features else "standard chemistry"
    return f"Pattern with {feature_str} — {quality} (overall: {overall}/100)"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEGACY: CO-OCCURRENCE PAIR SCORING (backward compat with main.py)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def score_void_biophysics(void: Void) -> tuple[float, str]:
    """Score a legacy co-occurrence Void using biophysics rules.

    Constructs a minimal SiRNAPattern from the void's two position:mod
    assignments and runs the feasibility checker.

    Returns (score, rationale) tuple.
    """
    pattern = SiRNAPattern(name=f"void_{void.id}")

    for pos_label, mod_name in [(void.pos_a, void.mod_a), (void.pos_b, void.mod_b)]:
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
        else "No biophysics rule violations."
    )
    return score, rationale


def batch_score_biophysics(db: Session, void_ids: list[int] | None = None) -> int:
    """Score legacy Void records using biophysics rules. Returns count scored."""
    q = db.query(Void).filter(Void.is_void == True)  # noqa: E712
    if void_ids:
        q = q.filter(Void.id.in_(void_ids))

    voids = q.all()
    scored = 0
    for void in voids:
        score, rationale = score_void_biophysics(void)
        void.feasibility_score = score
        void.feasibility_rationale = rationale
        scored += 1

    db.commit()
    logger.info("Biophysics-scored %d voids", scored)
    return scored


CLAUDE_LEGACY_PROMPT = """You are an RNA therapeutics expert evaluating an untested siRNA modification combination.

CONTEXT:
siRNA drugs use chemical modifications at specific positions on the guide (antisense) and passenger (sense) strands.

Key biology:
- Seed region (guide positions 2-8): critical for target recognition, sensitive to rigid mods
- Cleavage site (guide positions 10-11): Ago2 cuts here, no bulky modifications
- 3' overhang (positions 19-21): tolerates heavy modification for stability
- Passenger strand: discarded after RISC loading, can tolerate more modification

UNTESTED COMBINATION:
Position {pos_a} with modification {mod_a}
COMBINED WITH
Position {pos_b} with modification {mod_b}

Observed in only {obs_count} published siRNA designs.

Return ONLY valid JSON:
{{
  "claude_score": <float 0-1, overall feasibility>,
  "rationale": "<2-3 sentences>",
  "risk_factors": ["<risk1>", "<risk2>"],
  "suggested_context": "<one-line: what full siRNA design should include this pair>"
}}"""


async def score_void_claude(void: Void) -> dict:
    """Score a legacy Void using Claude for contextual reasoning."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_key_here":
        return {
            "claude_score": None,
            "rationale": "ANTHROPIC_API_KEY not configured",
            "error": "missing_api_key",
        }

    prompt = CLAUDE_LEGACY_PROMPT.format(
        pos_a=void.pos_a, mod_a=void.mod_a,
        pos_b=void.pos_b, mod_b=void.mod_b,
        obs_count=void.observation_count,
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text.strip()
        if "```" in text:
            for block in text.split("```"):
                stripped = block.strip()
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                if stripped.startswith("{"):
                    text = stripped
                    break

        return json.loads(text)

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Claude JSON: %s", exc)
        return {"claude_score": None, "rationale": "JSON parse error", "error": "parse_error"}
    except anthropic.APIError as exc:
        logger.error("Anthropic API error: %s", exc)
        return {"claude_score": None, "rationale": str(exc), "error": "api_error"}


async def score_void_combined(void: Void, db: Session) -> dict:
    """Run both biophysics and Claude scoring on a legacy Void."""
    bio_score, bio_rationale = score_void_biophysics(void)
    void.feasibility_score = bio_score
    void.feasibility_rationale = bio_rationale

    claude_result = await score_void_claude(void)
    if claude_result.get("claude_score") is not None:
        void.claude_score = claude_result["claude_score"]
        void.claude_rationale = claude_result.get("rationale", "")

    db.commit()

    return {
        "void_id": void.id,
        "biophysics_score": bio_score,
        "biophysics_rationale": bio_rationale,
        "claude_score": claude_result.get("claude_score"),
        "claude_rationale": claude_result.get("rationale", ""),
        "risk_factors": claude_result.get("risk_factors", []),
        "suggested_context": claude_result.get("suggested_context", ""),
    }
