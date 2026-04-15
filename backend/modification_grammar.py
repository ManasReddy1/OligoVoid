"""Core ontology of siRNA chemical modifications for OligoVoid.

This is the scientific heart of OligoVoid. It encodes:
  1. The complete modification taxonomy with biophysical properties
  2. The siRNA structure model (SiRNAModificationPattern)
  3. Biophysical feasibility rules derived from published SAR data
  4. Known FDA-approved/clinical modification patterns as seed data
  5. Coverage analysis and feasible pattern enumeration

A 21-nucleotide siRNA duplex has two strands:
  Guide (antisense):   positions 1–21, loaded into Ago2, binds target mRNA
  Passenger (sense):   positions 1–21, ejected and degraded after RISC loading

Each nucleotide carries a 2' sugar modification; each inter-nucleotide
linkage may be a natural phosphodiester or a stabilizing modification.
Terminal conjugates (e.g. GalNAc) attach at strand ends for delivery.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from itertools import product
from typing import Literal


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 1 — MODIFICATION TAXONOMY (full biophysical properties)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SUGAR_MODIFICATIONS: dict[str, dict] = {
    "2'-OMe": {
        "full_name": "2'-O-methyl",
        "abbreviation": "m",
        "risc_tolerance": 0.95,
        "nuclease_resistance": 0.85,
        "binding_affinity_delta_tm": +1.0,
        "seed_region_safe": True,
        "cleavage_site_safe": True,
        "notes": "Most widely used, excellent stability",
    },
    "2'-F": {
        "full_name": "2'-Fluoro",
        "abbreviation": "f",
        "risc_tolerance": 0.90,
        "nuclease_resistance": 0.80,
        "binding_affinity_delta_tm": +1.8,
        "seed_region_safe": True,
        "cleavage_site_safe": True,
        "notes": "Preferred in seed region, enhances RISC loading",
    },
    "LNA": {
        "full_name": "Locked Nucleic Acid",
        "abbreviation": "L",
        "risc_tolerance": 0.45,
        "nuclease_resistance": 0.99,
        "binding_affinity_delta_tm": +4.0,
        "seed_region_safe": False,
        "cleavage_site_safe": False,
        "notes": "Highest affinity but restricts RISC loading",
    },
    "cEt": {
        "full_name": "Constrained 2'-O-ethyl",
        "abbreviation": "E",
        "risc_tolerance": 0.50,
        "nuclease_resistance": 0.97,
        "binding_affinity_delta_tm": +3.5,
        "seed_region_safe": False,
        "cleavage_site_safe": False,
        "notes": "High affinity, used in ASOs primarily",
    },
    "DNA": {
        "full_name": "Deoxyribose (unmodified DNA)",
        "abbreviation": "d",
        "risc_tolerance": 0.70,
        "nuclease_resistance": 0.20,
        "binding_affinity_delta_tm": -1.5,
        "seed_region_safe": True,
        "cleavage_site_safe": True,
        "notes": "Supports RNase H cleavage in ASOs",
    },
    "RNA": {
        "full_name": "Unmodified ribose",
        "abbreviation": "r",
        "risc_tolerance": 1.0,
        "nuclease_resistance": 0.10,
        "binding_affinity_delta_tm": 0.0,
        "seed_region_safe": True,
        "cleavage_site_safe": True,
        "notes": "Natural, high activity, low stability",
    },
    "UNA": {
        "full_name": "Unlocked Nucleic Acid",
        "abbreviation": "U",
        "risc_tolerance": 0.85,
        "nuclease_resistance": 0.30,
        "binding_affinity_delta_tm": -2.0,
        "seed_region_safe": True,
        "cleavage_site_safe": False,
        "notes": "Reduces off-target effects, increases flexibility",
    },
    "MOE": {
        "full_name": "2'-O-Methoxyethyl",
        "abbreviation": "e",
        "risc_tolerance": 0.40,
        "nuclease_resistance": 0.92,
        "binding_affinity_delta_tm": +2.0,
        "seed_region_safe": False,
        "cleavage_site_safe": False,
        "notes": "Used in ASOs, too bulky for siRNA RISC",
    },
}

BACKBONE_MODIFICATIONS: dict[str, dict] = {
    "PS": {
        "full_name": "Phosphorothioate",
        "nuclease_resistance_bonus": 0.70,
        "cell_uptake_bonus": 0.60,
        "immunogenicity_risk": 0.35,
        "notes": "Most common backbone mod, promotes uptake",
    },
    "PO": {
        "full_name": "Phosphodiester (natural)",
        "nuclease_resistance_bonus": 0.0,
        "cell_uptake_bonus": 0.0,
        "immunogenicity_risk": 0.05,
        "notes": "Natural backbone, no additional stability",
    },
    "MsPA": {
        "full_name": "Mesyl Phosphoramidate",
        "nuclease_resistance_bonus": 0.75,
        "cell_uptake_bonus": 0.40,
        "immunogenicity_risk": 0.10,
        "notes": "Newer backbone, reduced immunogenicity vs PS",
    },
}

TERMINAL_CONJUGATES: dict[str, dict] = {
    "GalNAc": {
        "full_name": "N-Acetylgalactosamine (trivalent)",
        "target_tissue": "liver",
        "receptor": "ASGPR",
        "uptake_enhancement": 10.0,
        "fda_approved_examples": ["Givosiran", "Lumasiran", "Inclisiran", "Vutrisiran"],
        "position": "3prime_passenger",
        "notes": "Gold standard for liver delivery",
    },
    "Cholesterol": {
        "full_name": "Cholesterol conjugate",
        "target_tissue": "liver, muscle",
        "receptor": "LDL receptor pathway",
        "uptake_enhancement": 3.0,
        "fda_approved_examples": [],
        "position": "3prime_passenger",
        "notes": "Hepatocyte targeting, lower potency than GalNAc",
    },
    "LNP": {
        "full_name": "Lipid Nanoparticle compatible",
        "target_tissue": "liver, any (with targeting)",
        "receptor": "endocytosis",
        "uptake_enhancement": 8.0,
        "fda_approved_examples": ["Onpattro (patisiran)"],
        "position": "formulation",
        "notes": "First FDA-approved siRNA delivery system",
    },
    "None": {
        "full_name": "No conjugate",
        "target_tissue": "requires delivery vehicle",
        "receptor": "N/A",
        "uptake_enhancement": 1.0,
        "fda_approved_examples": [],
        "position": "N/A",
        "notes": "Naked siRNA, low cellular uptake in vivo",
    },
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 2 — ENUMS & CONVENIENCE LISTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SugarMod(str, Enum):
    """2' sugar modifications on the ribose ring."""
    OMe = "2'-OMe"
    F   = "2'-F"
    LNA = "LNA"
    cEt = "cEt"
    DNA = "DNA"
    RNA = "RNA"
    UNA = "UNA"
    MOE = "MOE"


class BackboneMod(str, Enum):
    """Internucleotide linkage modifications."""
    PO   = "PO"
    PS   = "PS"
    MsPA = "MsPA"


class Conjugate(str, Enum):
    """Terminal conjugation chemistries for delivery."""
    GalNAc      = "GalNAc"
    Cholesterol = "Cholesterol"
    LNP         = "LNP"
    Antibody    = "Antibody"
    NONE        = "None"


SUGAR_MODS_LIST: list[str] = [m.value for m in SugarMod]
BACKBONE_MODS_LIST: list[str] = [m.value for m in BackboneMod]
CONJUGATE_LIST: list[str] = [c.value for c in Conjugate]

ABBREVIATION_MAP: dict[str, str] = {
    v["full_name"]: v["abbreviation"]
    for v in SUGAR_MODIFICATIONS.values()
}
# Also key by the canonical sugar name
ABBREVIATION_MAP.update({
    k: v["abbreviation"] for k, v in SUGAR_MODIFICATIONS.items()
})

REVERSE_ABBREVIATION_MAP: dict[str, str] = {
    v: k for k, v in ABBREVIATION_MAP.items()
    if k in SUGAR_MODIFICATIONS  # only canonical names
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 3 — STRAND CONSTANTS & FUNCTIONAL REGIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GUIDE_LENGTH = 21
PASSENGER_LENGTH = 21
TOTAL_POSITIONS = GUIDE_LENGTH + PASSENGER_LENGTH  # 42
NUM_LINKAGES = 20  # 20 inter-nucleotide linkages per 21-mer strand

StrandType = Literal["guide", "passenger"]

# Functional regions on the guide strand (1-indexed positions)
SEED_REGION = range(2, 9)             # g2–g8: critical for target recognition
CLEAVAGE_SITE = range(10, 12)         # g10–g11: Ago2 catalytic site
SUPPLEMENTARY = range(13, 17)         # g13–g16: supplementary pairing
THREE_PRIME_OVERHANG = range(19, 22)  # g19–g21: 3' overhang, stability mods OK

# Sets of sugar mods by rigidity class (for feasibility rules)
_CLEAVAGE_UNSAFE = {"LNA", "cEt", "MOE", "UNA"}
_SEED_RIGID = {"LNA", "cEt"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 4 — DATACLASSES (PositionModification kept for backward compat)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class PositionModification:
    """A single position's modification assignment (legacy interface).

    Used by void_detector and feasibility_scorer for sparse pattern checks.
    """
    strand: StrandType
    position: int           # 1-indexed
    sugar: SugarMod
    backbone: BackboneMod = BackboneMod.PO

    @property
    def label(self) -> str:
        return f"{'g' if self.strand == 'guide' else 'p'}{self.position}"

    def __str__(self) -> str:
        bb = f"+{self.backbone.value}" if self.backbone != BackboneMod.PO else ""
        return f"{self.label}:{self.sugar.value}{bb}"


@dataclass
class FeasibilityViolation:
    """A biophysics rule violation with severity and explanation."""
    rule_id: str
    severity: Literal["fatal", "major", "minor"]
    position: str           # e.g. "g10" or "g2-g8"
    message: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 5 — SiRNAModificationPattern (primary structure model)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SiRNAModificationPattern:
    """A complete chemical modification pattern for a 21-mer siRNA duplex.

    Guide strand:     positions 1-21 (antisense, binds mRNA via Ago2)
    Passenger strand: positions 1-21 (sense, discarded after RISC loading)

    Functional regions on the guide strand:
      Seed (g2-g8):      critical for target recognition and specificity
      Cleavage (g10-g11): Ago2 catalytic site — must be unmodified or flexible
      3' overhang (g19-g21): modifications here improve stability safely
      Passenger seed match (p2-p8): contributes to off-target risk
    """

    REGION_DEFINITIONS = {
        "guide_seed":           range(1, 8),   # 0-indexed 1-7 → positions 2-8
        "guide_cleavage":       range(9, 11),  # 0-indexed 9-10 → positions 10-11
        "guide_3overhang":      range(18, 21), # 0-indexed 18-20 → positions 19-21
        "guide_5end":           range(0, 4),   # 0-indexed 0-3 → positions 1-4
        "passenger_seed_match": range(1, 8),   # 0-indexed 1-7 → positions 2-8
    }

    def __init__(self):
        self.guide_modifications: list[str | None] = [None] * 21
        self.passenger_modifications: list[str | None] = [None] * 21
        self.guide_backbone: list[str] = ["PO"] * NUM_LINKAGES
        self.passenger_backbone: list[str] = ["PO"] * NUM_LINKAGES
        self.terminal_conjugate: str = "None"
        self.conjugate_position: str = "3prime_passenger"
        self.pattern_id: str | None = None
        self.source: str = ""
        self.knockdown_efficacy: float | None = None  # 0-100

    def to_notation(self) -> str:
        """Convert to shorthand notation.

        Example:
          Guide:     mfmfmfmfmfmfmfmfmfmfm
          Passenger: fmfmfmfmfmfmfmfmfmfmf
        """
        def _abbrev(mod: str | None) -> str:
            if mod is None:
                return "?"
            return ABBREVIATION_MAP.get(mod, "?")

        g = "".join(_abbrev(m) for m in self.guide_modifications)
        p = "".join(_abbrev(m) for m in self.passenger_modifications)
        return f"Guide:     {g}\nPassenger: {p}"

    def to_dict(self) -> dict:
        """Serialize for database storage or API response."""
        return {
            "pattern_id": self.pattern_id,
            "guide_modifications": self.guide_modifications,
            "passenger_modifications": self.passenger_modifications,
            "guide_backbone": self.guide_backbone,
            "passenger_backbone": self.passenger_backbone,
            "terminal_conjugate": self.terminal_conjugate,
            "conjugate_position": self.conjugate_position,
            "source": self.source,
            "knockdown_efficacy": self.knockdown_efficacy,
            "notation": self.to_notation(),
            "fingerprint": self.fingerprint,
        }

    def from_notation(
        self, guide_str: str, passenger_str: str
    ) -> "SiRNAModificationPattern":
        """Parse shorthand notation into this pattern.

        Each character maps via REVERSE_ABBREVIATION_MAP:
          m→2'-OMe, f→2'-F, L→LNA, E→cEt, d→DNA, r→RNA, U→UNA, e→MOE
        """
        self.guide_modifications = [
            REVERSE_ABBREVIATION_MAP.get(c) for c in guide_str
        ]
        self.passenger_modifications = [
            REVERSE_ABBREVIATION_MAP.get(c) for c in passenger_str
        ]
        return self

    @property
    def fingerprint(self) -> str:
        """Canonical hash for deduplication."""
        g = "|".join(m or "?" for m in self.guide_modifications)
        p = "|".join(m or "?" for m in self.passenger_modifications)
        raw = f"G[{g}]_P[{p}]_BB[{''.join(self.guide_backbone)}|{''.join(self.passenger_backbone)}]"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def get_region(self, region_name: str) -> list[str | None]:
        """Return the sugar modifications in a named guide region."""
        r = self.REGION_DEFINITIONS.get(region_name)
        if r is None:
            return []
        source = (
            self.passenger_modifications
            if region_name.startswith("passenger")
            else self.guide_modifications
        )
        return [source[i] for i in r]

    def __repr__(self) -> str:
        pid = self.pattern_id or self.fingerprint
        return f"<SiRNAModificationPattern {pid}>"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 6 — LEGACY SiRNAPattern (backward compat for void_detector/scorer)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SiRNAPattern:
    """Legacy sparse pattern representation.

    Used by void_detector and feasibility_scorer to check individual
    position-modification pairs without constructing a full 42-position pattern.
    """
    name: str
    guide: list[PositionModification] = field(default_factory=list)
    passenger: list[PositionModification] = field(default_factory=list)
    conjugate_5p_guide: Conjugate = Conjugate.NONE
    conjugate_3p_guide: Conjugate = Conjugate.NONE
    conjugate_5p_passenger: Conjugate = Conjugate.NONE
    conjugate_3p_passenger: Conjugate = Conjugate.NONE
    source: str = ""
    year: int | None = None

    @property
    def guide_sugars(self) -> list[str]:
        return [m.sugar.value for m in sorted(self.guide, key=lambda m: m.position)]

    @property
    def passenger_sugars(self) -> list[str]:
        return [m.sugar.value for m in sorted(self.passenger, key=lambda m: m.position)]

    @property
    def pattern_fingerprint(self) -> str:
        g = "|".join(str(m) for m in sorted(self.guide, key=lambda m: m.position))
        p = "|".join(str(m) for m in sorted(self.passenger, key=lambda m: m.position))
        return f"G[{g}]_P[{p}]"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 7 — BIOPHYSICS FEASIBILITY RULES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def check_feasibility(
    pattern: SiRNAModificationPattern | SiRNAPattern,
) -> list[FeasibilityViolation]:
    """Evaluate a modification pattern against known biophysics rules.

    Accepts both SiRNAModificationPattern (full) and SiRNAPattern (sparse legacy).
    Returns a list of violations. Empty list = fully feasible.
    """
    if isinstance(pattern, SiRNAModificationPattern):
        return _check_full_pattern(pattern)
    return _check_legacy_pattern(pattern)


def _check_full_pattern(p: SiRNAModificationPattern) -> list[FeasibilityViolation]:
    """Feasibility rules for the full SiRNAModificationPattern."""
    violations: list[FeasibilityViolation] = []
    gm = p.guide_modifications
    pm = p.passenger_modifications
    gb = p.guide_backbone
    pb = p.passenger_backbone

    # ── Rule 1: Cleavage site (g10-g11) — no rigid/bulky mods ────────────
    for idx in [9, 10]:  # 0-indexed
        mod = gm[idx]
        if mod and mod in _CLEAVAGE_UNSAFE:
            violations.append(FeasibilityViolation(
                rule_id="CLEAVAGE_RIGID",
                severity="fatal",
                position=f"g{idx + 1}",
                message=(
                    f"Modification {mod} at guide position {idx + 1} blocks Ago2 "
                    f"catalytic cleavage. Only 2'-OMe, 2'-F, DNA, or RNA tolerated."
                ),
            ))

    # ── Rule 2: Seed region (g2-g8) — limit rigid mods ───────────────────
    lna_cet_in_seed = sum(
        1 for i in range(1, 8) if gm[i] and gm[i] in _SEED_RIGID
    )
    if lna_cet_in_seed > 2:
        violations.append(FeasibilityViolation(
            rule_id="SEED_OVER_RIGID",
            severity="major",
            position="g2-g8",
            message=(
                f"{lna_cet_in_seed} rigid modifications (LNA/cEt) in seed region. "
                f"More than 2 impairs RISC loading and target recognition."
            ),
        ))

    # ── Rule 3: Prefer 2'-F in seed for RISC loading ────────────────────
    guide_filled = sum(1 for m in gm if m is not None)
    f_in_seed = sum(1 for i in range(1, 8) if gm[i] == "2'-F")
    if f_in_seed == 0 and guide_filled >= 8:
        violations.append(FeasibilityViolation(
            rule_id="SEED_NO_FLUORO",
            severity="minor",
            position="g2-g8",
            message=(
                "No 2'-F in seed region. Fluorine at seed positions "
                "improves RISC loading thermodynamics."
            ),
        ))

    # ── Rule 4: Terminal PS for exonuclease protection ───────────────────
    for strand_name, bb, prefix in [("guide", gb, "g"), ("passenger", pb, "p")]:
        if len(bb) >= NUM_LINKAGES:
            terminal_ps = sum(1 for i in [0, 1, 18, 19] if bb[i] == "PS")
            if terminal_ps == 0:
                violations.append(FeasibilityViolation(
                    rule_id="NO_TERMINAL_PS",
                    severity="major",
                    position=f"{prefix}1-2,{prefix}20-21",
                    message=(
                        f"No PS backbone at {strand_name} termini. "
                        f"Terminal PS protects against 3'/5' exonucleases."
                    ),
                ))

    # ── Rule 5: Excessive PS causes toxicity ─────────────────────────────
    for strand_name, bb, prefix in [("guide", gb, "g"), ("passenger", pb, "p")]:
        ps_count = sum(1 for b in bb if b == "PS")
        if ps_count > 10:
            violations.append(FeasibilityViolation(
                rule_id="EXCESSIVE_PS",
                severity="major",
                position=f"{prefix}1-21",
                message=(
                    f"{ps_count}/{len(bb)} PS linkages on {strand_name} strand. "
                    f">10 PS increases hepatotoxicity and non-specific protein binding."
                ),
            ))

    # ── Rule 6: Excessive LNA/cEt prevents duplex unwinding ─────────────
    for strand_name, mods, prefix in [("guide", gm, "g"), ("passenger", pm, "p")]:
        filled = [m for m in mods if m is not None]
        rigid = sum(1 for m in filled if m in _SEED_RIGID)
        if len(filled) >= 15 and rigid > len(filled) * 0.5:
            violations.append(FeasibilityViolation(
                rule_id="EXCESSIVE_LNA",
                severity="fatal",
                position=f"{prefix}1-21",
                message=(
                    f"{rigid}/{len(filled)} positions have LNA/cEt on {strand_name}. "
                    f"Over 50% rigid sugars prevents duplex unwinding by helicase."
                ),
            ))

    # ── Rule 7: Internal UNA on guide reduces binding ────────────────────
    for i in range(2, 18):  # 0-indexed 2-17 → positions 3-18
        if gm[i] and gm[i] == "UNA":
            violations.append(FeasibilityViolation(
                rule_id="UNA_INTERNAL",
                severity="minor",
                position=f"g{i + 1}",
                message=(
                    f"UNA at internal guide position {i + 1} may reduce binding "
                    f"affinity. UNA best suited for position 1 or passenger strand."
                ),
            ))

    # ── Rule 8: GalNAc placement ─────────────────────────────────────────
    if p.terminal_conjugate == "GalNAc":
        if p.conjugate_position not in ("3prime_passenger", "3prime_sense"):
            violations.append(FeasibilityViolation(
                rule_id="GALNAC_WRONG_POSITION",
                severity="fatal",
                position=p.conjugate_position,
                message=(
                    "GalNAc must be conjugated to passenger strand 3' end. "
                    "Other positions block RISC loading or Ago2 binding."
                ),
            ))

    # ── Rule 9: All-RNA strand will be degraded in vivo ──────────────────
    for strand_name, mods, prefix in [("guide", gm, "g"), ("passenger", pm, "p")]:
        filled = [m for m in mods if m is not None]
        rna_count = sum(1 for m in filled if m == "RNA")
        if len(filled) >= 15 and rna_count > len(filled) * 0.8:
            violations.append(FeasibilityViolation(
                rule_id="MOSTLY_UNMODIFIED",
                severity="major",
                position=f"{prefix}1-21",
                message=(
                    f"{rna_count}/{len(filled)} positions are unmodified RNA on "
                    f"{strand_name}. >80% unmodified gives <1 hour serum half-life."
                ),
            ))

    # ── Rule 10: MOE in seed blocks RISC loading ─────────────────────────
    moe_in_seed = sum(1 for i in range(1, 8) if gm[i] == "MOE")
    if moe_in_seed > 0:
        violations.append(FeasibilityViolation(
            rule_id="MOE_IN_SEED",
            severity="major",
            position="g2-g8",
            message=(
                f"{moe_in_seed} MOE modifications in seed region. "
                f"MOE is too bulky for efficient RISC loading at seed positions."
            ),
        ))

    return violations


def _check_legacy_pattern(pattern: SiRNAPattern) -> list[FeasibilityViolation]:
    """Feasibility rules for legacy sparse SiRNAPattern (PositionModification lists)."""
    violations: list[FeasibilityViolation] = []
    guide_by_pos = {m.position: m for m in pattern.guide}
    passenger_by_pos = {m.position: m for m in pattern.passenger}

    # Rule 1: Cleavage site
    for pos in CLEAVAGE_SITE:
        mod = guide_by_pos.get(pos)
        if mod and mod.sugar.value in _CLEAVAGE_UNSAFE:
            violations.append(FeasibilityViolation(
                rule_id="CLEAVAGE_RIGID",
                severity="fatal",
                position=f"g{pos}",
                message=(
                    f"Modification {mod.sugar.value} at guide position {pos} "
                    f"blocks Ago2 catalytic cleavage."
                ),
            ))

    # Rule 2: Seed rigid
    rigid_in_seed = sum(
        1 for pos in SEED_REGION
        if guide_by_pos.get(pos) and guide_by_pos[pos].sugar.value in _SEED_RIGID
    )
    if rigid_in_seed > 2:
        violations.append(FeasibilityViolation(
            rule_id="SEED_OVER_RIGID",
            severity="major",
            position="g2-g8",
            message=f"{rigid_in_seed} LNA/cEt in seed region. >2 impairs RISC loading.",
        ))

    # Rule 3: Seed fluoro
    f_in_seed = sum(
        1 for pos in SEED_REGION
        if guide_by_pos.get(pos) and guide_by_pos[pos].sugar == SugarMod.F
    )
    if f_in_seed == 0 and len(guide_by_pos) >= 8:
        violations.append(FeasibilityViolation(
            rule_id="SEED_NO_FLUORO",
            severity="minor",
            position="g2-g8",
            message="No 2'-F in seed region.",
        ))

    # Rule 4: Terminal PS
    for strand_name, mods_by_pos, prefix in [
        ("guide", guide_by_pos, "g"),
        ("passenger", passenger_by_pos, "p"),
    ]:
        terminal_ps = sum(
            1 for pos in [1, 2, 20, 21]
            if mods_by_pos.get(pos) and mods_by_pos[pos].backbone == BackboneMod.PS
        )
        if terminal_ps == 0 and len(mods_by_pos) >= 10:
            violations.append(FeasibilityViolation(
                rule_id="NO_TERMINAL_PS",
                severity="major",
                position=f"{prefix}1-2,{prefix}20-21",
                message=f"No PS at {strand_name} termini.",
            ))

    # Rule 5: Excessive PS
    for strand_name, strand_mods, prefix in [
        ("guide", pattern.guide, "g"),
        ("passenger", pattern.passenger, "p"),
    ]:
        ps_count = sum(1 for m in strand_mods if m.backbone == BackboneMod.PS)
        if ps_count > 10:
            violations.append(FeasibilityViolation(
                rule_id="EXCESSIVE_PS",
                severity="major",
                position=f"{prefix}1-21",
                message=f"{ps_count} PS on {strand_name}. >10 increases hepatotoxicity.",
            ))

    # Rule 6: Excessive LNA
    for strand_name, strand_mods, prefix in [
        ("guide", pattern.guide, "g"),
        ("passenger", pattern.passenger, "p"),
    ]:
        rigid = sum(1 for m in strand_mods if m.sugar.value in _SEED_RIGID)
        if len(strand_mods) >= 15 and rigid > len(strand_mods) * 0.5:
            violations.append(FeasibilityViolation(
                rule_id="EXCESSIVE_LNA",
                severity="fatal",
                position=f"{prefix}1-21",
                message=f"{rigid}/{len(strand_mods)} LNA/cEt on {strand_name}.",
            ))

    # Rule 7: Internal UNA
    for pos in range(3, 19):
        mod = guide_by_pos.get(pos)
        if mod and mod.sugar == SugarMod.UNA:
            violations.append(FeasibilityViolation(
                rule_id="UNA_INTERNAL",
                severity="minor",
                position=f"g{pos}",
                message=f"UNA at internal guide position {pos}.",
            ))

    # Rule 8: GalNAc placement
    if pattern.conjugate_5p_guide == Conjugate.GalNAc:
        violations.append(FeasibilityViolation(
            rule_id="GALNAC_WRONG_END",
            severity="fatal",
            position="guide 5'",
            message="GalNAc at guide 5' blocks RISC loading.",
        ))
    if pattern.conjugate_3p_guide == Conjugate.GalNAc:
        violations.append(FeasibilityViolation(
            rule_id="GALNAC_WRONG_STRAND",
            severity="fatal",
            position="guide 3'",
            message="GalNAc at guide 3' clashes with Ago2 PAZ domain.",
        ))

    return violations


def compute_feasibility_score(violations: list[FeasibilityViolation]) -> float:
    """Convert violations into a 0.0–1.0 feasibility score.

    1.0 = no violations.  Fatal = -0.35, major = -0.15, minor = -0.05.
    """
    score = 1.0
    for v in violations:
        if v.severity == "fatal":
            score -= 0.35
        elif v.severity == "major":
            score -= 0.15
        elif v.severity == "minor":
            score -= 0.05
    return max(0.0, round(score, 3))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 8 — KNOWN PATTERNS (FDA-approved & clinically studied seed data)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _alt_ome_f() -> list[str]:
    """2'-OMe at odd positions (1,3,5..), 2'-F at even (2,4,6..)."""
    return ["2'-OMe", "2'-F"] * 10 + ["2'-OMe"]

def _alt_f_ome() -> list[str]:
    """2'-F at odd positions, 2'-OMe at even."""
    return ["2'-F", "2'-OMe"] * 10 + ["2'-F"]

def _terminal_ps() -> list[str]:
    """PS at linkages 0,1,18,19 — standard Alnylam terminal protection."""
    bb = ["PO"] * NUM_LINKAGES
    bb[0] = bb[1] = bb[18] = bb[19] = "PS"
    return bb

def _make_known_pattern(
    pattern_id: str,
    guide_mods: list[str],
    passenger_mods: list[str],
    guide_bb: list[str],
    passenger_bb: list[str],
    conjugate: str,
    source: str,
    efficacy: float,
) -> SiRNAModificationPattern:
    p = SiRNAModificationPattern()
    p.pattern_id = pattern_id
    p.guide_modifications = guide_mods
    p.passenger_modifications = passenger_mods
    p.guide_backbone = guide_bb
    p.passenger_backbone = passenger_bb
    p.terminal_conjugate = conjugate
    p.source = source
    p.knockdown_efficacy = efficacy
    return p


def _build_known_patterns() -> list[SiRNAModificationPattern]:
    """Construct the 5 canonical known patterns."""
    patterns: list[SiRNAModificationPattern] = []

    # ── Pattern 1: Alnylam ESC (Inclisiran) ───────────────────────────
    # Alternating 2'-OMe/2'-F, terminal PS, GalNAc delivery
    patterns.append(_make_known_pattern(
        pattern_id="ESC_001",
        guide_mods=_alt_ome_f(),
        passenger_mods=_alt_ome_f(),
        guide_bb=_terminal_ps(),
        passenger_bb=_terminal_ps(),
        conjugate="GalNAc",
        source="Inclisiran (FDA 2021), Ray KK et al. NEJM 2020",
        efficacy=84.0,
    ))

    # ── Pattern 2: Patisiran (first FDA-approved siRNA) ───────────────
    # Alternating 2'-OMe/2'-F, all PO backbone, LNP delivery
    patterns.append(_make_known_pattern(
        pattern_id="STD_001",
        guide_mods=_alt_ome_f(),
        passenger_mods=_alt_ome_f(),
        guide_bb=["PO"] * NUM_LINKAGES,
        passenger_bb=["PO"] * NUM_LINKAGES,
        conjugate="LNP",
        source="Patisiran (FDA 2018), Adams D et al. NEJM 2018",
        efficacy=81.0,
    ))

    # ── Pattern 3: Givosiran ──────────────────────────────────────────
    # Mostly 2'-OMe, 2'-F at specific positions, terminal PS, GalNAc
    giv_guide = ["2'-OMe"] * 21
    for i in [1, 5, 7, 13, 15]:  # 0-idx → positions 2, 6, 8, 14, 16
        giv_guide[i] = "2'-F"
    giv_pass = ["2'-OMe"] * 21
    for i in [1, 5, 7]:  # 0-idx → positions 2, 6, 8
        giv_pass[i] = "2'-F"
    patterns.append(_make_known_pattern(
        pattern_id="ESC_002",
        guide_mods=giv_guide,
        passenger_mods=giv_pass,
        guide_bb=_terminal_ps(),
        passenger_bb=_terminal_ps(),
        conjugate="GalNAc",
        source="Givosiran (FDA 2019), Balwani M et al. NEJM 2020",
        efficacy=90.0,
    ))

    # ── Pattern 4: Standard Chemistry (Reynolds 2004) ─────────────────
    # Alternating 2'-OMe/2'-F, no conjugate, all PO — the academic baseline
    patterns.append(_make_known_pattern(
        pattern_id="CLASSIC_001",
        guide_mods=_alt_ome_f(),
        passenger_mods=_alt_ome_f(),
        guide_bb=["PO"] * NUM_LINKAGES,
        passenger_bb=["PO"] * NUM_LINKAGES,
        conjugate="None",
        source="Reynolds A et al. Nat Biotechnol 2004",
        efficacy=70.0,
    ))

    # ── Pattern 5: Khvorova Lab Chemistry ─────────────────────────────
    # 2'-F in seed (g2-g8), 2'-OMe elsewhere, all PS backbone
    khv_guide = ["2'-OMe"] * 21
    for i in range(1, 8):  # 0-idx 1-7 → positions 2-8
        khv_guide[i] = "2'-F"
    patterns.append(_make_known_pattern(
        pattern_id="KHVOROVA_001",
        guide_mods=khv_guide,
        passenger_mods=["2'-OMe"] * 21,
        guide_bb=["PS"] * NUM_LINKAGES,
        passenger_bb=["PS"] * NUM_LINKAGES,
        conjugate="None",
        source="Khvorova A, Watts JK. Nat Biotechnol 2017",
        efficacy=83.0,
    ))

    return patterns


KNOWN_PATTERNS: list[SiRNAModificationPattern] = _build_known_patterns()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 9 — COVERAGE ANALYSIS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_known_pattern_coverage() -> dict:
    """Analyze which (position, modification) pairs the known patterns cover.

    Returns:
        total_position_mod_combos: 42 positions × 8 sugar mods = 336
        tested_position_mod_combos: how many of those appear in KNOWN_PATTERNS
        coverage_pct: percentage
        untested_modifications: sugar mods never used at any position
        untested_positions: positions with zero data
        position_coverage: per-position breakdown of tested vs untested mods
        num_known_patterns: count of seed patterns
    """
    all_mods = set(SUGAR_MODS_LIST)
    all_pos = set(all_positions())
    tested: set[tuple[str, str]] = set()

    for pat in KNOWN_PATTERNS:
        for i, mod in enumerate(pat.guide_modifications):
            if mod:
                tested.add((f"g{i + 1}", mod))
        for i, mod in enumerate(pat.passenger_modifications):
            if mod:
                tested.add((f"p{i + 1}", mod))

    total = len(all_pos) * len(all_mods)
    tested_mods = {mod for _, mod in tested}
    tested_positions = {pos for pos, _ in tested}

    position_coverage: dict[str, dict] = {}
    for pos in sorted(all_pos, key=_position_sort_key):
        mods_at_pos = {mod for p, mod in tested if p == pos}
        position_coverage[pos] = {
            "tested_mods": sorted(mods_at_pos),
            "untested_mods": sorted(all_mods - mods_at_pos),
            "coverage": round(len(mods_at_pos) / len(all_mods), 3),
        }

    return {
        "total_position_mod_combos": total,
        "tested_position_mod_combos": len(tested),
        "coverage_pct": round(len(tested) / total * 100, 1),
        "untested_modifications": sorted(all_mods - tested_mods),
        "untested_positions": sorted(all_pos - tested_positions, key=_position_sort_key),
        "num_known_patterns": len(KNOWN_PATTERNS),
        "position_coverage": position_coverage,
    }


def _position_sort_key(pos: str) -> tuple[int, int]:
    """Sort key: guide before passenger, then by position number."""
    strand = 0 if pos.startswith("g") else 1
    num = int(pos[1:])
    return (strand, num)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 10 — FEASIBLE PATTERN ENUMERATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Template archetypes for systematic sampling

_GUIDE_SUGAR_TEMPLATES: dict[str, list[str]] = {
    "all_ome": ["2'-OMe"] * 21,
    "all_f": ["2'-F"] * 21,
    "esc_standard": _alt_ome_f(),
    "esc_inverted": _alt_f_ome(),
    "f_seed_ome_rest": (
        ["2'-OMe"] + ["2'-F"] * 7 + ["2'-OMe"] * 13
    ),
    "f_seed_dna_cleave": (
        ["2'-OMe"] + ["2'-F"] * 7 + ["2'-OMe"]
        + ["DNA", "DNA"]
        + ["2'-OMe"] * 10
    ),
    "ome_lna_3prime": (
        ["2'-OMe"] * 18 + ["LNA", "LNA", "2'-OMe"]
    ),
    "esc_lna_3prime": (
        ["2'-OMe", "2'-F"] * 9 + ["LNA", "2'-F", "2'-OMe"]
    ),
    "una_start_f_seed": (
        ["UNA"] + ["2'-F"] * 7 + ["2'-OMe"] * 13
    ),
    "f_dominant": (
        ["2'-OMe"] + ["2'-F"] * 8 + ["2'-OMe", "2'-OMe"]
        + ["2'-F"] * 8 + ["2'-OMe", "2'-OMe"]
    ),
    "ome_dna_central": (
        ["2'-OMe"] * 4 + ["DNA"] * 8 + ["2'-OMe"] * 4
        + ["DNA"] * 2 + ["2'-OMe"] * 3
    ),
    "all_rna_baseline": ["RNA"] * 21,
}

_PASSENGER_SUGAR_TEMPLATES: dict[str, list[str]] = {
    "all_ome": ["2'-OMe"] * 21,
    "esc_standard": _alt_ome_f(),
    "esc_inverted": _alt_f_ome(),
    "all_f": ["2'-F"] * 21,
    "ome_f_sparse": (
        ["2'-OMe"] + ["2'-F"] + ["2'-OMe"] * 3
        + ["2'-F"] + ["2'-OMe"] + ["2'-F"] + ["2'-OMe"] * 13
    ),
}

_BACKBONE_TEMPLATES: dict[str, list[str]] = {
    "all_po": ["PO"] * NUM_LINKAGES,
    "terminal_ps": _terminal_ps(),
    "all_ps": ["PS"] * NUM_LINKAGES,
    "terminal_mspa": (
        ["MsPA", "MsPA"] + ["PO"] * 16 + ["MsPA", "MsPA"]
    ),
}

_CONJUGATE_OPTIONS = ["GalNAc", "Cholesterol", "LNP", "None"]


def enumerate_all_feasible_patterns(
    max_lna_count: int = 3,
    require_cleavage_site_unmodified: bool = True,
    allow_seed_lna: bool = False,
) -> list[SiRNAModificationPattern]:
    """Generate candidate patterns respecting biological constraints.

    Systematic grid over archetype templates (12 guide × 5 passenger ×
    4 backbone × 4 conjugate = 960 combinations), filtered by:
      - max_lna_count: max LNA+cEt across both strands
      - require_cleavage_site_unmodified: g10/g11 must be DNA or RNA
      - allow_seed_lna: whether LNA/cEt are allowed at g2-g8

    Patterns that cause fatal feasibility violations are excluded.
    Output is capped at ~1000 representative patterns.
    """
    patterns: list[SiRNAModificationPattern] = []
    seen: set[str] = set()

    for g_name, g_template in _GUIDE_SUGAR_TEMPLATES.items():
        g_mods = list(g_template)  # copy

        # Enforce cleavage site constraint
        if require_cleavage_site_unmodified:
            if g_mods[9] not in ("DNA", "RNA"):
                g_mods[9] = "DNA"
            if g_mods[10] not in ("DNA", "RNA"):
                g_mods[10] = "DNA"

        # Check seed LNA constraint
        if not allow_seed_lna:
            seed_has_rigid = any(g_mods[i] in _SEED_RIGID for i in range(1, 8))
            if seed_has_rigid:
                continue

        for p_name, p_mods in _PASSENGER_SUGAR_TEMPLATES.items():
            # LNA count across both strands
            lna_total = sum(1 for m in g_mods if m in _SEED_RIGID)
            lna_total += sum(1 for m in p_mods if m in _SEED_RIGID)
            if lna_total > max_lna_count:
                continue

            for bb_name, bb_template in _BACKBONE_TEMPLATES.items():
                for conj in _CONJUGATE_OPTIONS:
                    pat = SiRNAModificationPattern()
                    pat.guide_modifications = list(g_mods)
                    pat.passenger_modifications = list(p_mods)
                    pat.guide_backbone = list(bb_template)
                    pat.passenger_backbone = list(bb_template)
                    pat.terminal_conjugate = conj
                    pat.pattern_id = f"{g_name}__{p_name}__{bb_name}__{conj}"

                    # Deduplicate by fingerprint
                    fp = pat.fingerprint
                    if fp in seen:
                        continue
                    seen.add(fp)

                    # Filter fatal violations
                    violations = _check_full_pattern(pat)
                    if any(v.severity == "fatal" for v in violations):
                        continue

                    pat.knockdown_efficacy = None
                    patterns.append(pat)

                    if len(patterns) >= 1000:
                        return patterns

    return patterns


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 11 — DESIGN SPACE HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def all_positions() -> list[str]:
    """Return all 42 position labels: g1..g21, p1..p21."""
    return [f"g{i}" for i in range(1, 22)] + [f"p{i}" for i in range(1, 22)]


def position_sugar_pairs() -> list[tuple[str, str]]:
    """Every (position, sugar_mod) combination: 42 × 8 = 336."""
    return [(pos, s.value) for pos in all_positions() for s in SugarMod]


def cooccurrence_pair_space() -> int:
    """C(336, 2) = 56,280 unique co-occurrence pairs to scan."""
    n = len(position_sugar_pairs())
    return n * (n - 1) // 2


def get_ontology_stats() -> dict:
    """Summary statistics for the modification grammar."""
    return {
        "sugar_modifications": len(SugarMod),
        "backbone_modifications": len(BackboneMod),
        "conjugate_types": len(Conjugate),
        "guide_length": GUIDE_LENGTH,
        "passenger_length": PASSENGER_LENGTH,
        "total_positions": TOTAL_POSITIONS,
        "position_sugar_pairs": len(position_sugar_pairs()),
        "cooccurrence_pair_space": cooccurrence_pair_space(),
        "sugar_mods": SUGAR_MODS_LIST,
        "backbone_mods": BACKBONE_MODS_LIST,
        "conjugates": CONJUGATE_LIST,
        "known_patterns": len(KNOWN_PATTERNS),
        "functional_regions": {
            "seed": {"positions": "g2-g8", "note": "Critical for target recognition"},
            "cleavage_site": {"positions": "g10-g11", "note": "Ago2 catalytic site"},
            "supplementary": {"positions": "g13-g16", "note": "Supplementary pairing"},
            "three_prime_overhang": {"positions": "g19-g21", "note": "Stability mods safe"},
        },
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE LOAD SUMMARY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_stats = get_ontology_stats()
_cov = get_known_pattern_coverage()
print(
    f"[OligoVoid Grammar] {_stats['total_positions']} positions × "
    f"{_stats['sugar_modifications']} sugar mods = "
    f"{_stats['position_sugar_pairs']} position-sugar pairs → "
    f"{_stats['cooccurrence_pair_space']:,} co-occurrence pairs to scan | "
    f"{_stats['known_patterns']} known patterns covering "
    f"{_cov['coverage_pct']}% of position-mod space"
)
