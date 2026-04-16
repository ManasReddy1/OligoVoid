"""
Modification Intelligence Report Generator for OligoVoid.

Generates human-readable, beginner-friendly qualitative interpretations
for void candidates. This is what makes OligoVoid interpretable to
non-experts while remaining rigorous for experts.

Author: Manas Reddy
"""

from __future__ import annotations

from typing import Optional

from backend.fda_validation import FDA_APPROVED_SIRNAS, compute_pattern_similarity_to_fda


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REGION LABELS FOR PLAIN ENGLISH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REGION_NAMES = {
    range(1, 2): "5' terminus",
    range(2, 9): "seed region (the drug's address — determines which gene it silences)",
    range(9, 10): "central region",
    range(10, 12): "cleavage site (where the cellular scissors cut the target)",
    range(12, 19): "supplementary region (helps with binding accuracy)",
    range(19, 22): "3' protective zone (shields the drug in the bloodstream)",
}

MOD_PLAIN_NAMES = {
    "2'-OMe": "2'-O-methyl (the workhorse — stable and well-tolerated)",
    "2'-F": "2'-Fluoro (enhances binding, good in the seed region)",
    "LNA": "Locked Nucleic Acid (very strong binding, but can block the cellular machinery)",
    "cEt": "Constrained ethyl (strong binding, mostly used in antisense drugs)",
    "DNA": "DNA (natural, but degrades quickly in blood)",
    "RNA": "RNA (natural, the cell recognizes this, but blood destroys it fast)",
    "UNA": "Unlocked Nucleic Acid (flexible, reduces off-target effects)",
    "MOE": "2'-Methoxyethyl (stable but too bulky for siRNA's cellular machinery)",
}


def _get_region_name(pos: int) -> str:
    """Get the plain English region name for a 1-indexed position."""
    for r, name in REGION_NAMES.items():
        if pos in r:
            return name
    return "unknown region"


def _count_differences(mods_a: list[str], mods_b: list[str]) -> list[dict]:
    """Find positions where two modification lists differ."""
    diffs = []
    for i, (a, b) in enumerate(zip(mods_a, mods_b)):
        if a != b:
            diffs.append({
                "position": i + 1,
                "region": _get_region_name(i + 1),
                "this_pattern": a,
                "fda_pattern": b,
            })
    return diffs


def _score_to_rating(score: float) -> tuple[str, str, str]:
    """Convert a 0-100 score to (rating, traffic_light, adjective)."""
    if score >= 80:
        return "HIGH", "green", "Excellent"
    elif score >= 60:
        return "MEDIUM", "yellow", "Moderate"
    else:
        return "LOW", "red", "Concerning"


def generate_modification_intelligence_report(
    void_pattern: dict,
    scores: Optional[dict] = None,
    fda_comparisons: Optional[list] = None,
) -> dict:
    """
    Generate a structured qualitative report for one void candidate.

    Think of this as a "drug design report card" written by an expert,
    but explainable to anyone.

    Args:
        void_pattern: Dict with guide_mods, passenger_mods, backbone_guide,
                      backbone_passenger, conjugate.
        scores: Optional pre-computed scores dict from score_pattern_biophysics().
                If None, will compute them.
        fda_comparisons: Optional pre-computed FDA similarity list.
                         If None, will compute.

    Returns:
        Structured report dict with 5 sections + overall recommendation.
    """
    # Compute scores if not provided
    if scores is None:
        try:
            from backend.feasibility_scorer import score_pattern_biophysics
            scores = score_pattern_biophysics(void_pattern)
        except Exception:
            scores = _fallback_scores(void_pattern)

    # Compute FDA comparisons if not provided
    if fda_comparisons is None:
        fda_comparisons = compute_pattern_similarity_to_fda(void_pattern)

    closest_fda = fda_comparisons[0] if fda_comparisons else None

    # ── SECTION 1: Executive Summary ──
    overall = scores.get("overall_oligovoid_score", 50.0)
    executive_summary = _generate_executive_summary(void_pattern, scores, closest_fda)

    # ── SECTION 2: What This Pattern Does Differently ──
    what_is_different = _generate_difference_analysis(void_pattern, closest_fda)

    # ── SECTION 3: Risk Assessment ──
    risk_assessment = _generate_risk_assessment(scores)

    # ── SECTION 4: The Hypothesis ──
    hypothesis = _generate_hypothesis(void_pattern, scores, closest_fda)

    # ── SECTION 5: Closest Approved Drug ──
    closest_drug_analysis = _generate_closest_drug_analysis(
        void_pattern, scores, closest_fda
    )

    # ── Overall Recommendation ──
    if overall >= 75 and closest_fda and closest_fda["similarity_pct"] > 60:
        recommendation = "PRIORITIZE"
        rec_plain = (
            "This pattern scores well on biophysics AND is similar to an "
            "FDA-approved drug. It should be among the first candidates tested "
            "in a wet lab."
        )
    elif overall >= 60:
        recommendation = "INVESTIGATE"
        rec_plain = (
            "This pattern shows promise but has some uncertainty. It is worth "
            "further computational analysis or a small-scale cell line experiment "
            "before committing significant resources."
        )
    else:
        recommendation = "LOW_PRIORITY"
        rec_plain = (
            "This pattern has notable biophysical concerns. While it represents "
            "unexplored territory, the predicted scores suggest other candidates "
            "should be tested first."
        )

    return {
        "executive_summary": executive_summary,
        "what_is_different": what_is_different,
        "risk_assessment": risk_assessment,
        "hypothesis": hypothesis,
        "closest_fda_drug": closest_drug_analysis,
        "overall_oligovoid_score": round(overall, 1),
        "overall_recommendation": recommendation,
        "recommendation_plain_english": rec_plain,
    }


def _generate_executive_summary(pattern: dict, scores: dict, closest: Optional[dict]) -> str:
    """One-sentence, 5th-grade-level summary."""
    overall = scores.get("overall_oligovoid_score", 50)
    nuclease = scores.get("nuclease_resistance_score", 50)
    risc = scores.get("risc_loading_score", 50)

    if nuclease >= 80 and risc >= 80:
        return (
            "This modification pattern protects the drug in the bloodstream "
            "AND loads well into the cellular machine — two properties that "
            "are hard to achieve simultaneously."
        )
    elif nuclease >= 80:
        return (
            "This pattern is very stable in the bloodstream, meaning the drug "
            "would survive long enough to reach its target cells. However, "
            "the cellular machinery may have some difficulty using it."
        )
    elif risc >= 80:
        return (
            "This pattern loads efficiently into the cell's gene-silencing "
            "machinery, but may degrade faster than ideal in the bloodstream. "
            "A delivery vehicle like GalNAc or LNP would help."
        )
    elif overall >= 65:
        return (
            "This is a balanced modification pattern — no single property is "
            "outstanding, but nothing is critically weak either. It represents "
            "a reasonable starting point for optimization."
        )
    else:
        return (
            "This pattern has notable limitations in either stability or "
            "cellular loading. It is interesting as unexplored territory but "
            "would likely need optimization before wet-lab testing."
        )


def _generate_difference_analysis(pattern: dict, closest: Optional[dict]) -> str:
    """Compare to nearest FDA drug."""
    if closest is None:
        return "No FDA drug comparison available."

    drug_name = closest["drug_name"]
    fda_drug = None
    for d in FDA_APPROVED_SIRNAS:
        if d["drug_name"] == drug_name:
            fda_drug = d
            break

    if fda_drug is None:
        return f"Closest FDA drug: {drug_name} ({closest['similarity_pct']:.0f}% similar)."

    guide_diffs = _count_differences(
        pattern.get("guide_mods", []), fda_drug["guide_mods"]
    )
    pass_diffs = _count_differences(
        pattern.get("passenger_mods", []), fda_drug["passenger_mods"]
    )

    parts = [
        f"Compared to {drug_name} ({fda_drug['brand']}), "
        f"this pattern differs at {len(guide_diffs)} guide strand and "
        f"{len(pass_diffs)} passenger strand positions."
    ]

    # Highlight key differences
    for diff in guide_diffs[:3]:
        region = diff["region"]
        pos = diff["position"]
        this_mod = diff["this_pattern"]
        fda_mod = diff["fda_pattern"]
        parts.append(
            f"At guide position {pos} ({region}): "
            f"this pattern uses {this_mod} instead of {fda_mod}."
        )

    return " ".join(parts)


def _generate_risk_assessment(scores: dict) -> list[dict]:
    """Traffic light assessment for 5 dimensions."""
    dimensions = [
        {
            "dimension": "Nuclease Resistance",
            "key": "nuclease_resistance_score",
            "desc_high": "The drug should survive in blood for 24+ hours",
            "desc_med": "Moderate blood stability — may need delivery vehicle support",
            "desc_low": "Drug will degrade quickly in blood without protection",
        },
        {
            "dimension": "RISC Loading",
            "key": "risc_loading_score",
            "desc_high": "The cellular machinery can efficiently use this drug",
            "desc_med": "The cellular machinery can use this drug, but less efficiently. Worth testing",
            "desc_low": "The cellular machinery may struggle to load this drug. Modifications in the seed region may be too rigid",
        },
        {
            "dimension": "Thermodynamic Stability",
            "key": "thermodynamic_score",
            "desc_high": "The drug-target duplex is stable — strong binding predicted",
            "desc_med": "Binding is adequate but not optimal",
            "desc_low": "Weak target binding predicted — the drug may dissociate before silencing",
        },
        {
            "dimension": "Off-Target Safety",
            "key": "off_target_display_score",
            "desc_high": "Low chance of silencing unintended genes",
            "desc_med": "Moderate chance of affecting genes other than the target. Careful testing recommended",
            "desc_low": "Elevated risk of off-target effects. Cell-line specificity testing strongly recommended",
        },
        {
            "dimension": "Seed Region Compatibility",
            "key": "seed_region_compatibility",
            "desc_high": "Seed region modifications are well-tolerated for target recognition",
            "desc_med": "Seed region has some non-standard modifications — may affect targeting",
            "desc_low": "Seed region modifications may impair target gene recognition",
        },
    ]

    assessment = []
    for dim in dimensions:
        score = scores.get(dim["key"], 50.0)
        rating, light, adj = _score_to_rating(score)

        if rating == "HIGH":
            plain = dim["desc_high"]
        elif rating == "MEDIUM":
            plain = dim["desc_med"]
        else:
            plain = dim["desc_low"]

        assessment.append({
            "dimension": dim["dimension"],
            "score": round(score, 1),
            "rating": rating,
            "traffic_light": light,
            "adjective": adj,
            "plain_english": plain,
        })

    return assessment


def _generate_hypothesis(pattern: dict, scores: dict, closest: Optional[dict]) -> dict:
    """Generate testable hypothesis."""
    nuclease = scores.get("nuclease_resistance_score", 50)
    risc = scores.get("risc_loading_score", 50)
    thermo = scores.get("thermodynamic_score", 50)
    overall = scores.get("overall_oligovoid_score", 50)

    # Why it might work
    strengths = []
    if nuclease >= 75:
        strengths.append("high nuclease resistance")
    if risc >= 75:
        strengths.append("efficient RISC loading")
    if thermo >= 75:
        strengths.append("strong target binding")

    if strengths:
        works = f"the combination of {' and '.join(strengths)} produces effective gene silencing"
    else:
        works = "the novel modification combination creates an unexpected synergy not captured by current rules"

    # Why it might fail
    weaknesses = []
    if nuclease < 60:
        weaknesses.append("rapid degradation in serum before reaching target cells")
    if risc < 60:
        weaknesses.append("poor RISC loading due to seed region rigidity")
    if thermo < 60:
        weaknesses.append("weak target duplex stability leading to premature dissociation")

    if weaknesses:
        fails = weaknesses[0]
    else:
        fails = "unforeseen cellular toxicity or delivery challenges not captured by the biophysics model"

    # Fastest experiment
    conjugate = pattern.get("conjugate", "None")
    if conjugate == "GalNAc":
        cell_line = "Huh-7 hepatocytes (GalNAc-receptor expressing)"
    elif conjugate == "LNP":
        cell_line = "HeLa or HepG2 cells with lipofectamine transfection"
    else:
        cell_line = "HeLa cells with lipofectamine transfection"

    experiment = (
        f"Transfect {cell_line} with 10 nM siRNA, "
        f"measure target mRNA knockdown by qRT-PCR at 48 hours. "
        f"Include Inclisiran as positive control."
    )

    return {
        "if_it_works": f"If this pattern works, the most likely reason is: {works}.",
        "if_it_fails": f"If it fails, the most likely reason is: {fails}.",
        "fastest_experiment": experiment,
    }


def _generate_closest_drug_analysis(
    pattern: dict, scores: dict, closest: Optional[dict]
) -> dict:
    """Detailed comparison to closest FDA drug."""
    if closest is None:
        return {
            "drug_name": "Unknown",
            "similarity_positions": 0,
            "similarity_pct": 0.0,
            "their_efficacy": 0.0,
            "estimated_success_probability": 0.0,
            "probability_basis": "No FDA drug comparison available.",
        }

    overall = scores.get("overall_oligovoid_score", 50)
    sim_pct = closest["similarity_pct"]

    # Estimated probability based on similarity + biophysics
    # High similarity to high-efficacy drug + good biophysics = higher chance
    base_prob = sim_pct / 100.0  # similarity contribution
    bio_factor = overall / 100.0  # biophysics contribution
    estimated_prob = round(100.0 * (0.6 * base_prob + 0.4 * bio_factor), 1)
    estimated_prob = min(85.0, max(5.0, estimated_prob))  # clamp

    basis = (
        f"Based on {sim_pct:.0f}% structural similarity to {closest['drug_name']} "
        f"(clinical efficacy: {closest['clinical_efficacy_pct']:.0f}%) "
        f"weighted by OligoVoid biophysics score ({overall:.0f}/100). "
        f"This is a rough estimate — wet-lab validation is required."
    )

    return {
        "drug_name": closest["drug_name"],
        "brand": closest.get("brand", ""),
        "target_gene": closest.get("target_gene", ""),
        "similarity_positions": closest["positions_identical"],
        "total_positions": closest["total_positions"],
        "similarity_pct": sim_pct,
        "their_efficacy": closest["clinical_efficacy_pct"],
        "estimated_success_probability": estimated_prob,
        "probability_basis": basis,
    }


def _fallback_scores(pattern: dict) -> dict:
    """Generate approximate scores when feasibility_scorer is unavailable."""
    guide = pattern.get("guide_mods", [])
    f_count = guide.count("2'-F")
    ome_count = guide.count("2'-OMe")

    return {
        "thermodynamic_score": min(95, 50 + f_count * 2 + ome_count * 1.5),
        "risc_loading_score": min(95, 60 + f_count * 1.5),
        "nuclease_resistance_score": min(95, 40 + ome_count * 2 + f_count * 1.5),
        "off_target_risk_score": 30.0,
        "off_target_display_score": 70.0,
        "seed_region_compatibility": 75.0,
        "overall_oligovoid_score": 65.0,
    }
