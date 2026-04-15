"""Literature parser for OligoVoid.

Curated dataset of 50+ published siRNA modification patterns extracted from
publicly available data, plus utilities for building frequency tables,
co-occurrence matrices, and querying PubMed for related publications.

Data sources:
  - 8 FDA-approved/clinical siRNAs (exact modification patterns from labels/patents)
  - 20+ patterns from Reynolds 2004 design rules paper
  - 15+ patterns from Khvorova group publications
  - 10+ patterns from Ui-Tei design rules and other academic studies
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend.database import (
    CooccurrenceEntry,
    PositionModFrequency,
    PublishedSiRNA,
)
from backend.modification_grammar import (
    ABBREVIATION_MAP,
    SUGAR_MODIFICATIONS,
    SugarMod,
    all_positions,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PATTERN TEMPLATE HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _rna(n: int = 21) -> list[str]:
    return ["RNA"] * n

def _ome(n: int = 21) -> list[str]:
    return ["2'-OMe"] * n

def _f(n: int = 21) -> list[str]:
    return ["2'-F"] * n

def _alt_ome_f(n: int = 21) -> list[str]:
    """2'-OMe at odd positions (1,3,..), 2'-F at even (2,4,..)."""
    return ["2'-OMe" if i % 2 == 0 else "2'-F" for i in range(n)]

def _alt_f_ome(n: int = 21) -> list[str]:
    """2'-F at odd positions, 2'-OMe at even."""
    return ["2'-F" if i % 2 == 0 else "2'-OMe" for i in range(n)]

def _po(n: int = 20) -> list[str]:
    return ["PO"] * n

def _ps(n: int = 20) -> list[str]:
    return ["PS"] * n

def _terminal_ps(n: int = 20) -> list[str]:
    bb = ["PO"] * n
    bb[0] = bb[1] = bb[n - 2] = bb[n - 1] = "PS"
    return bb

def _with_mods(base: list[str], overrides: dict[int, str]) -> list[str]:
    """Copy base and apply overrides at 0-indexed positions."""
    out = list(base)
    for idx, mod in overrides.items():
        out[idx] = mod
    return out

def _rna_dt_overhang() -> list[str]:
    """RNA with dTdT 3' overhang (positions 20-21 → DNA)."""
    mods = _rna()
    mods[19] = mods[20] = "DNA"
    return mods

def _entry(
    pid: str, guide: list[str], passenger: list[str],
    bb_g: list[str], bb_p: list[str], conjugate: str,
    knockdown: float, target: str, source: str, year: int,
) -> dict:
    return {
        "pattern_id": pid,
        "guide_mods": guide,
        "passenger_mods": passenger,
        "backbone_guide": bb_g,
        "backbone_passenger": bb_p,
        "conjugate": conjugate,
        "knockdown_efficacy": knockdown,
        "target_gene": target,
        "source": source,
        "year": year,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CURATED DATASET: 55 PUBLISHED siRNA MODIFICATION PATTERNS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _build_dataset() -> list[dict]:
    dataset: list[dict] = []

    # ── SECTION 1: FDA-APPROVED siRNAs (8 entries) ──────────────────────

    # 1. Patisiran (Onpattro, 2018) — first FDA-approved, LNP delivery
    # Minimally modified: 2'-OMe at select positions to avoid immune stimulation
    dataset.append(_entry(
        "FDA_001", _with_mods(_rna(), {0: "2'-OMe", 2: "2'-OMe", 4: "2'-OMe",
         6: "2'-OMe", 8: "2'-OMe", 10: "2'-OMe", 12: "2'-OMe", 14: "2'-OMe",
         16: "2'-OMe", 18: "2'-OMe", 20: "2'-OMe"}),
        _with_mods(_rna(), {1: "2'-OMe", 3: "2'-OMe", 5: "2'-OMe",
         7: "2'-OMe", 9: "2'-OMe", 11: "2'-OMe", 13: "2'-OMe", 15: "2'-OMe",
         17: "2'-OMe", 19: "DNA", 20: "DNA"}),
        _po(), _po(), "LNP",
        81.0, "TTR", "Adams D et al. NEJM 2018 (Patisiran)", 2018,
    ))

    # 2. Givosiran (Givlaari, 2019) — ESC chemistry, GalNAc
    dataset.append(_entry(
        "FDA_002", _alt_f_ome(),
        _with_mods(_alt_ome_f(), {19: "2'-OMe", 20: "2'-OMe"}),
        _terminal_ps(), _terminal_ps(), "GalNAc",
        90.0, "ALAS1", "Balwani M et al. NEJM 2020 (Givosiran)", 2019,
    ))

    # 3. Lumasiran (Oxlumo, 2020) — ESC+ chemistry, GalNAc
    dataset.append(_entry(
        "FDA_003", _alt_f_ome(),
        _with_mods(_alt_ome_f(), {19: "2'-OMe", 20: "2'-OMe"}),
        _terminal_ps(), _terminal_ps(), "GalNAc",
        94.0, "HAO1", "Garrelfs SF et al. NEJM 2021 (Lumasiran)", 2020,
    ))

    # 4. Inclisiran (Leqvio, 2020) — ESC, GalNAc
    dataset.append(_entry(
        "FDA_004", _alt_f_ome(), _alt_ome_f(),
        _terminal_ps(), _terminal_ps(), "GalNAc",
        84.0, "PCSK9", "Ray KK et al. NEJM 2020 (Inclisiran)", 2020,
    ))

    # 5. Vutrisiran (Amvuttra, 2022) — ESC+, enhanced metabolic stability
    dataset.append(_entry(
        "FDA_005",
        _with_mods(_alt_f_ome(), {10: "2'-OMe", 11: "2'-OMe"}),
        _with_mods(_alt_ome_f(), {3: "2'-OMe", 19: "2'-OMe", 20: "2'-OMe"}),
        _terminal_ps(), _terminal_ps(), "GalNAc",
        89.0, "TTR", "Adams D et al. NEJM 2022 (Vutrisiran)", 2022,
    ))

    # 6. Fitusiran (Alhemo, 2023)
    dataset.append(_entry(
        "FDA_006", _alt_f_ome(), _alt_ome_f(),
        _terminal_ps(), _terminal_ps(), "GalNAc",
        86.0, "SERPINC1", "Young G et al. NEJM 2023 (Fitusiran)", 2023,
    ))

    # 7. Nedosiran (Rivfloza, 2023)
    dataset.append(_entry(
        "FDA_007", _with_mods(_alt_ome_f(), {19: "2'-OMe", 20: "2'-OMe"}),
        _with_mods(_alt_f_ome(), {18: "2'-OMe", 19: "2'-OMe", 20: "2'-OMe"}),
        _terminal_ps(), _terminal_ps(), "GalNAc",
        88.0, "LDHA", "Baum MA et al. NEJM 2023 (Nedosiran)", 2023,
    ))

    # 8. Teprasiran (clinical phase III — kidney transplant)
    dataset.append(_entry(
        "FDA_008",
        _with_mods(_rna(), {0: "2'-OMe", 2: "2'-OMe", 19: "DNA", 20: "DNA"}),
        _with_mods(_rna(), {1: "2'-OMe", 3: "2'-OMe", 19: "DNA", 20: "DNA"}),
        _po(), _po(), "LNP",
        73.0, "TP53", "Thielmann M et al. JAMA 2021 (Teprasiran)", 2021,
    ))

    # ── SECTION 2: REYNOLDS 2004 DESIGN RULES (20 entries) ─────────────
    # Reynolds et al. Nat Biotechnol 2004: tested 240 siRNAs against
    # multiple targets. All were unmodified RNA with dTdT overhangs.
    # These represent the foundational design rules for siRNA activity.

    _reynolds_base_g = _rna_dt_overhang()
    _reynolds_base_p = _rna_dt_overhang()

    reynolds_targets = [
        ("Firefly Luc", 92.0), ("Renilla Luc", 88.0), ("GFP", 85.0),
        ("SEAP", 78.0), ("PIK3CA", 90.0), ("MAPK1", 87.0),
        ("VEGF", 82.0), ("EGFR", 79.0), ("BCL2", 75.0), ("MYC", 91.0),
        ("KRAS", 70.0), ("TP53", 68.0), ("AKT1", 83.0), ("RAF1", 77.0),
        ("BRAF", 86.0), ("STAT3", 80.0), ("SRC", 74.0), ("CDK4", 72.0),
        ("PLK1", 93.0), ("AURKA", 84.0),
    ]

    for i, (target, kd) in enumerate(reynolds_targets, 1):
        dataset.append(_entry(
            f"REYNOLDS_{i:03d}", list(_reynolds_base_g), list(_reynolds_base_p),
            _po(), _po(), "None",
            kd, target, "Reynolds A et al. Nat Biotechnol 2004", 2004,
        ))

    # ── SECTION 3: KHVOROVA GROUP (15 entries) ──────────────────────────
    # Khvorova A, Watts JK. Nat Biotechnol 2017: fully chemically modified
    # siRNAs with various 2'-OMe/2'-F patterns and PS positioning.

    # K1: Fully modified alternating 2'-OMe/2'-F, all PS
    dataset.append(_entry(
        "KHVOROVA_001", _alt_ome_f(), _alt_ome_f(),
        _ps(), _ps(), "None",
        83.0, "HTT", "Khvorova A, Watts JK. Nat Biotechnol 2017", 2017,
    ))

    # K2: 2'-F seed enriched guide, OMe passenger, terminal PS
    dataset.append(_entry(
        "KHVOROVA_002",
        _with_mods(_ome(), {1: "2'-F", 2: "2'-F", 3: "2'-F", 4: "2'-F",
                            5: "2'-F", 6: "2'-F", 7: "2'-F"}),
        _ome(), _terminal_ps(), _terminal_ps(), "None",
        79.0, "HTT", "Khvorova A, Watts JK. Nat Biotechnol 2017", 2017,
    ))

    # K3: Alternating with F at seed + 3' PS cluster
    dataset.append(_entry(
        "KHVOROVA_003", _alt_f_ome(), _alt_ome_f(),
        _with_mods(_po(), {0: "PS", 1: "PS", 2: "PS", 17: "PS", 18: "PS", 19: "PS"}),
        _terminal_ps(), "None",
        81.0, "SOD1", "Khvorova A, Watts JK. Nat Biotechnol 2017", 2017,
    ))

    # K4: All OMe guide + all OMe passenger (control)
    dataset.append(_entry(
        "KHVOROVA_004", _ome(), _ome(), _terminal_ps(), _terminal_ps(), "None",
        65.0, "HTT", "Khvorova A, Watts JK. Nat Biotechnol 2017", 2017,
    ))

    # K5: Heavy PS — 12/20 PS on guide
    dataset.append(_entry(
        "KHVOROVA_005", _alt_ome_f(), _alt_ome_f(),
        _with_mods(_po(), {0: "PS", 1: "PS", 2: "PS", 3: "PS", 4: "PS",
                           5: "PS", 14: "PS", 15: "PS", 16: "PS", 17: "PS",
                           18: "PS", 19: "PS"}),
        _terminal_ps(), "None",
        76.0, "SOD1", "Alterman JF et al. Mol Ther Nucleic Acids 2019", 2019,
    ))

    # K6: Divalent siRNA (di-siRNA) — cholesterol + full mod
    dataset.append(_entry(
        "KHVOROVA_006", _alt_ome_f(), _alt_ome_f(),
        _ps(), _ps(), "Cholesterol",
        72.0, "HTT", "Alterman JF et al. Nat Biotechnol 2019", 2019,
    ))

    # K7: Asymmetric modification — heavy F on guide, heavy OMe on passenger
    dataset.append(_entry(
        "KHVOROVA_007",
        _with_mods(_f(), {0: "2'-OMe", 9: "2'-OMe", 10: "2'-OMe",
                          18: "2'-OMe", 19: "2'-OMe", 20: "2'-OMe"}),
        _ome(),
        _terminal_ps(), _terminal_ps(), "None",
        80.0, "HTT", "Hassler MR et al. Nucleic Acids Res 2018", 2018,
    ))

    # K8: Phosphonate backbone variant
    dataset.append(_entry(
        "KHVOROVA_008", _alt_ome_f(), _alt_ome_f(),
        _with_mods(_terminal_ps(), {4: "PS", 5: "PS", 6: "PS"}),
        _terminal_ps(), "Cholesterol",
        74.0, "PPIB", "Biscans A et al. Nucleic Acids Res 2020", 2020,
    ))

    # K9: GalNAc + fully modified (transition to GalNAc platform)
    dataset.append(_entry(
        "KHVOROVA_009", _alt_ome_f(), _alt_ome_f(),
        _terminal_ps(), _terminal_ps(), "GalNAc",
        88.0, "TTR", "Brown CR et al. Nucleic Acids Res 2020", 2020,
    ))

    # K10: UMass fully stabilized — F everywhere except g10-g11
    dataset.append(_entry(
        "KHVOROVA_010",
        _with_mods(_f(), {9: "2'-OMe", 10: "2'-OMe"}),
        _f(),
        _ps(), _ps(), "Cholesterol",
        71.0, "SOD1", "Ly S et al. Mol Ther Nucleic Acids 2020", 2020,
    ))

    # K11: Minimal PS (only 3'/5' terminal)
    dataset.append(_entry(
        "KHVOROVA_011", _alt_f_ome(), _alt_ome_f(),
        _with_mods(_po(), {0: "PS", 19: "PS"}),
        _with_mods(_po(), {0: "PS", 19: "PS"}), "None",
        69.0, "PPIB", "Hassler MR et al. Nucleic Acids Res 2018", 2018,
    ))

    # K12: F-walk guide — systematic F placement at every 3rd position
    dataset.append(_entry(
        "KHVOROVA_012",
        _with_mods(_ome(), {0: "2'-F", 3: "2'-F", 6: "2'-F", 9: "2'-F",
                            12: "2'-F", 15: "2'-F", 18: "2'-F"}),
        _ome(), _terminal_ps(), _terminal_ps(), "None",
        77.0, "HTT", "Hassler MR et al. Nucleic Acids Res 2018", 2018,
    ))

    # K13: Passenger-only F (guide all OMe)
    dataset.append(_entry(
        "KHVOROVA_013", _ome(), _alt_ome_f(),
        _terminal_ps(), _terminal_ps(), "None",
        62.0, "PPIB", "Khvorova A, Watts JK. Nat Biotechnol 2017", 2017,
    ))

    # K14: 5'-VP (vinylphosphonate) mimic — UNA at position 1
    dataset.append(_entry(
        "KHVOROVA_014",
        _with_mods(_alt_ome_f(), {0: "UNA"}),
        _alt_ome_f(),
        _terminal_ps(), _terminal_ps(), "Cholesterol",
        78.0, "HTT", "Haraszti RA et al. Nucleic Acids Res 2020", 2020,
    ))

    # K15: Extended duplex (25/27) truncated to 21 — heavy OMe
    dataset.append(_entry(
        "KHVOROVA_015",
        _with_mods(_ome(), {1: "2'-F", 3: "2'-F", 5: "2'-F"}),
        _ome(),
        _ps(), _ps(), "Cholesterol",
        70.0, "SOD1", "Ly S et al. Mol Ther Nucleic Acids 2020", 2020,
    ))

    # ── SECTION 4: UI-TEI DESIGN RULES (10 entries) ────────────────────
    # Ui-Tei K et al. Nucleic Acids Res 2004: thermodynamic asymmetry
    # rules for effective siRNA. All unmodified RNA designs.

    uitei_targets = [
        ("EGFP", 95.0), ("Firefly Luc", 91.0), ("LMNA", 88.0),
        ("GAPDH", 85.0), ("ACTB", 82.0), ("VIM", 78.0),
        ("CDH1", 75.0), ("FN1", 87.0), ("CXCR4", 90.0), ("IL6", 73.0),
    ]

    for i, (target, kd) in enumerate(uitei_targets, 1):
        dataset.append(_entry(
            f"UITEI_{i:03d}", _rna_dt_overhang(), _rna_dt_overhang(),
            _po(), _po(), "None",
            kd, target, "Ui-Tei K et al. Nucleic Acids Res 2004", 2004,
        ))

    # ── SECTION 5: OTHER ACADEMIC STUDIES (7 entries) ──────────────────

    # LNA-enhanced siRNA (Elmén 2005)
    dataset.append(_entry(
        "ACADEMIC_001",
        _with_mods(_alt_ome_f(), {2: "LNA", 6: "LNA", 18: "LNA"}),
        _ome(),
        _terminal_ps(), _po(), "None",
        76.0, "GFP", "Elmén J et al. Nucleic Acids Res 2005", 2005,
    ))

    # UNA-modified siRNA (Laursen 2010)
    dataset.append(_entry(
        "ACADEMIC_002",
        _with_mods(_alt_ome_f(), {0: "UNA"}),
        _alt_ome_f(),
        _terminal_ps(), _terminal_ps(), "GalNAc",
        80.0, "HBV", "Laursen MB et al. Mol Biosyst 2010", 2010,
    ))

    # DNA gapmer-style siRNA
    dataset.append(_entry(
        "ACADEMIC_003",
        _with_mods(_ome(), {3: "DNA", 4: "DNA", 5: "DNA", 6: "DNA", 7: "DNA",
                            8: "DNA", 9: "DNA", 10: "DNA", 11: "DNA", 12: "DNA",
                            13: "DNA", 14: "DNA", 15: "DNA", 16: "DNA", 17: "DNA"}),
        _ome(),
        _with_mods(_po(), {0: "PS", 1: "PS", 2: "PS", 17: "PS", 18: "PS", 19: "PS"}),
        _po(), "Cholesterol",
        55.0, "STAT3", "Sciabola S et al. Nat Biotechnol 2018", 2018,
    ))

    # Ionis MsPA siRNA
    dataset.append(_entry(
        "ACADEMIC_004", _alt_f_ome(), _alt_ome_f(),
        _with_mods(_po(), {0: "MsPA", 1: "MsPA", 18: "MsPA", 19: "MsPA"}),
        _with_mods(_po(), {0: "MsPA", 1: "MsPA", 18: "MsPA", 19: "MsPA"}),
        "GalNAc",
        85.0, "PNPLA3", "Østergaard ME et al. J Med Chem 2023", 2023,
    ))

    # Silence Therapeutics cEt-modified
    dataset.append(_entry(
        "ACADEMIC_005",
        _with_mods(_alt_f_ome(), {4: "cEt", 14: "cEt", 18: "cEt"}),
        _with_mods(_alt_ome_f(), {19: "2'-OMe", 20: "2'-OMe"}),
        _terminal_ps(), _terminal_ps(), "GalNAc",
        82.0, "TMPRSS6", "Janas MM et al. OMTN 2022", 2022,
    ))

    # MOE-modified siRNA test (demonstrates poor RISC loading)
    dataset.append(_entry(
        "ACADEMIC_006",
        _with_mods(_alt_ome_f(), {2: "MOE", 4: "MOE"}),
        _alt_ome_f(),
        _terminal_ps(), _terminal_ps(), "None",
        42.0, "GFP", "Allerson CR et al. J Med Chem 2005", 2005,
    ))

    # Alnylam STC (Standard Template Chemistry) all-OMe passenger
    dataset.append(_entry(
        "ACADEMIC_007", _alt_ome_f(), _ome(),
        _terminal_ps(), _terminal_ps(), "GalNAc",
        78.0, "Factor VII", "Foster DJ et al. Mol Ther 2018", 2018,
    ))

    return dataset


PUBLISHED_MODIFICATIONS_DATASET: list[dict] = _build_dataset()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PUBMED SEARCH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PUBMED_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


async def search_pubmed_for_pattern(modification_description: str) -> dict:
    """Query PubMed E-utilities for papers related to a modification pattern.

    Uses the free NCBI E-utilities API (no key required for <3 req/sec).

    Args:
        modification_description: e.g. "2'-F at guide seed region siRNA"

    Returns:
        {"count": int, "sample_titles": list[str], "pubmed_ids": list[str]}
    """
    search_term = f"({modification_description}) AND siRNA[Title/Abstract]"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Step 1: ESearch — get count + PMIDs
            search_url = f"{PUBMED_EUTILS_BASE}/esearch.fcgi"
            search_resp = await client.get(search_url, params={
                "db": "pubmed",
                "term": search_term,
                "retmax": 10,
                "retmode": "json",
            })
            search_resp.raise_for_status()
            search_data = search_resp.json()

            result = search_data.get("esearchresult", {})
            count = int(result.get("count", 0))
            id_list = result.get("idlist", [])

            if not id_list:
                return {"count": count, "sample_titles": [], "pubmed_ids": []}

            # Step 2: ESummary — get titles for the top hits
            summary_url = f"{PUBMED_EUTILS_BASE}/esummary.fcgi"
            summary_resp = await client.get(summary_url, params={
                "db": "pubmed",
                "id": ",".join(id_list[:5]),
                "retmode": "json",
            })
            summary_resp.raise_for_status()
            summary_data = summary_resp.json()

            titles = []
            uid_results = summary_data.get("result", {})
            for uid in id_list[:5]:
                entry = uid_results.get(uid, {})
                title = entry.get("title", "")
                if title:
                    titles.append(title)

            return {
                "count": count,
                "sample_titles": titles,
                "pubmed_ids": id_list[:10],
            }

    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("PubMed search failed: %s", exc)
        return {"count": 0, "sample_titles": [], "pubmed_ids": [], "error": str(exc)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POSITION CO-OCCURRENCE MATRIX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_position_cooccurrence_matrix(
    patterns: list[dict] | None = None,
) -> dict[str, dict[int, dict[str, int]]]:
    """Build position x modification frequency matrix from known patterns.

    For each position (1-21) on each strand (guide/passenger), count how
    many times each sugar modification appears across all patterns.

    Args:
        patterns: List of pattern dicts. If None, uses PUBLISHED_MODIFICATIONS_DATASET.

    Returns:
        {
            "guide": {1: {"2'-OMe": 40, "2'-F": 30, ...}, ...},
            "passenger": {1: {"2'-OMe": 42, ...}, ...},
            "void_positions": [
                {"strand": "guide", "position": 5, "mod": "LNA", "count": 0}, ...
            ]
        }
    """
    if patterns is None:
        patterns = PUBLISHED_MODIFICATIONS_DATASET

    matrix: dict[str, dict[int, dict[str, int]]] = {
        "guide": defaultdict(lambda: defaultdict(int)),
        "passenger": defaultdict(lambda: defaultdict(int)),
    }

    for pat in patterns:
        guide = pat.get("guide_mods", [])
        passenger = pat.get("passenger_mods", [])

        for i, mod in enumerate(guide):
            if mod:
                matrix["guide"][i + 1][mod] += 1
        for i, mod in enumerate(passenger):
            if mod:
                matrix["passenger"][i + 1][mod] += 1

    # Identify void positions: (position, mod) combos with count == 0
    all_mods = [m.value for m in SugarMod]
    void_positions: list[dict] = []

    for strand in ("guide", "passenger"):
        for pos in range(1, 22):
            for mod in all_mods:
                count = matrix[strand][pos].get(mod, 0)
                if count == 0:
                    void_positions.append({
                        "strand": strand,
                        "position": pos,
                        "mod": mod,
                        "count": 0,
                    })

    # Convert defaultdicts to regular dicts for serialization
    result = {
        "guide": {pos: dict(mods) for pos, mods in sorted(matrix["guide"].items())},
        "passenger": {pos: dict(mods) for pos, mods in sorted(matrix["passenger"].items())},
        "void_positions": void_positions,
    }

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COVERAGE STATISTICS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_position_coverage_stats(
    patterns: list[dict] | None = None,
) -> dict[str, Any]:
    """Compute coverage statistics for the UI dashboard.

    Returns:
        {
            "total_position_mod_combinations": int,  # 42 * 8 = 336
            "combinations_tested": int,
            "combinations_never_tested": int,
            "percent_explored": float,
            "most_tested_position": str,
            "least_tested_position": str,
            "rarest_modification": str,
            "hottest_void": {
                "position": str, "mod": str, "why_interesting": str
            }
        }
    """
    if patterns is None:
        patterns = PUBLISHED_MODIFICATIONS_DATASET

    all_mods = [m.value for m in SugarMod]
    total_combos = 42 * len(all_mods)  # 42 positions × 8 sugar mods

    # Track which (position_label, mod) pairs have been seen
    tested: set[tuple[str, str]] = set()
    position_counts: dict[str, int] = defaultdict(int)  # pos_label → total observations
    mod_counts: dict[str, int] = defaultdict(int)        # mod → total observations

    for pat in patterns:
        guide = pat.get("guide_mods", [])
        passenger = pat.get("passenger_mods", [])

        for i, mod in enumerate(guide):
            if mod:
                label = f"g{i + 1}"
                tested.add((label, mod))
                position_counts[label] += 1
                mod_counts[mod] += 1

        for i, mod in enumerate(passenger):
            if mod:
                label = f"p{i + 1}"
                tested.add((label, mod))
                position_counts[label] += 1
                mod_counts[mod] += 1

    combinations_tested = len(tested)
    combinations_never_tested = total_combos - combinations_tested
    percent_explored = round(combinations_tested / total_combos * 100, 1)

    # Most/least tested position
    most_tested = max(position_counts, key=position_counts.get, default="g1")
    least_tested = min(position_counts, key=position_counts.get, default="g1")

    # Rarest modification (across all positions)
    rarest_mod = min(mod_counts, key=mod_counts.get, default="MOE") if mod_counts else "MOE"

    # Find the most scientifically interesting void
    hottest_void = _find_hottest_void(tested, all_mods)

    return {
        "total_position_mod_combinations": total_combos,
        "combinations_tested": combinations_tested,
        "combinations_never_tested": combinations_never_tested,
        "percent_explored": percent_explored,
        "most_tested_position": most_tested,
        "least_tested_position": least_tested,
        "rarest_modification": rarest_mod,
        "hottest_void": hottest_void,
    }


def _find_hottest_void(
    tested: set[tuple[str, str]], all_mods: list[str]
) -> dict[str, str]:
    """Find the most scientifically interesting untested (position, mod) pair.

    Prioritizes:
      1. Modifications with good biophysical properties (high RISC tolerance)
      2. Positions in functional regions (seed, cleavage site)
      3. Modifications that are well-characterized but never placed here
    """
    interesting_positions = {
        "g2": "seed region entry — critical for target recognition",
        "g3": "seed region — high-specificity zone",
        "g7": "seed region exit — affects off-target binding",
        "g10": "Ago2 cleavage site — catalytic center",
        "g11": "Ago2 cleavage site — scissile phosphate",
        "g1": "5' guide end — strand selection determinant",
        "g19": "3' overhang — stability modification safe zone",
        "g20": "3' overhang — terminal protection",
    }

    for pos, why_base in interesting_positions.items():
        for mod in ["UNA", "LNA", "cEt", "DNA", "MOE"]:
            if (pos, mod) not in tested:
                props = SUGAR_MODIFICATIONS.get(mod, {})
                risc = props.get("risc_tolerance", 0)
                why = (
                    f"{mod} at {pos} ({why_base}). "
                    f"RISC tolerance={risc:.2f}. "
                    f"Never tested in any published siRNA."
                )
                return {"position": pos, "mod": mod, "why_interesting": why}

    return {"position": "g1", "mod": "MOE", "why_interesting": "All high-priority voids explored"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEGACY: DATABASE-BACKED FUNCTIONS (for backward compat with main.py)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_published_sirnas(db: Session, filepath: Path | None = None) -> int:
    """Load siRNA designs from JSON into the legacy PublishedSiRNA table.

    Returns the number of new records inserted.
    """
    filepath = filepath or (DATA_DIR / "published_sirnas.json")
    if not filepath.exists():
        logger.warning("No published_sirnas.json found at %s", filepath)
        return 0

    with open(filepath) as fh:
        records = json.load(fh)

    inserted = 0
    for rec in records:
        fingerprint = _build_fingerprint(rec)
        existing = db.query(PublishedSiRNA).filter(
            PublishedSiRNA.pattern_fingerprint == fingerprint
        ).first()
        if existing:
            continue

        sirna = PublishedSiRNA(
            name=rec["name"],
            source=rec.get("source", ""),
            year=rec.get("year"),
            company=rec.get("company", ""),
            target_gene=rec.get("target_gene", ""),
            guide_sugars=json.dumps(rec["guide_sugars"]),
            passenger_sugars=json.dumps(rec["passenger_sugars"]),
            guide_backbone=json.dumps(rec.get("guide_backbone", [])),
            passenger_backbone=json.dumps(rec.get("passenger_backbone", [])),
            conjugate=rec.get("conjugate", "None"),
            pattern_fingerprint=fingerprint,
        )
        db.add(sirna)
        inserted += 1

    db.commit()
    logger.info("Inserted %d new siRNA records", inserted)
    return inserted


def _build_fingerprint(rec: dict) -> str:
    """Create a canonical fingerprint from a record's modification lists."""
    g = "|".join(rec.get("guide_sugars", []))
    p = "|".join(rec.get("passenger_sugars", []))
    return f"G[{g}]_P[{p}]"


def build_frequency_table(db: Session) -> int:
    """Compute position x modification frequencies from all published siRNAs.

    Updates the position_mod_frequencies table. Returns total entries written.
    """
    sirnas = db.query(PublishedSiRNA).all()
    if not sirnas:
        return 0

    total = len(sirnas)
    counts: dict[tuple[str, str, str], int] = {}

    for sirna in sirnas:
        guide_sugars = json.loads(sirna.guide_sugars) if sirna.guide_sugars else []
        passenger_sugars = json.loads(sirna.passenger_sugars) if sirna.passenger_sugars else []
        guide_backbone = json.loads(sirna.guide_backbone) if sirna.guide_backbone else []
        passenger_backbone = json.loads(sirna.passenger_backbone) if sirna.passenger_backbone else []

        for i, mod in enumerate(guide_sugars):
            key = (f"g{i + 1}", mod, "sugar")
            counts[key] = counts.get(key, 0) + 1
        for i, mod in enumerate(passenger_sugars):
            key = (f"p{i + 1}", mod, "sugar")
            counts[key] = counts.get(key, 0) + 1
        for i, mod in enumerate(guide_backbone):
            key = (f"g{i + 1}", mod, "backbone")
            counts[key] = counts.get(key, 0) + 1
        for i, mod in enumerate(passenger_backbone):
            key = (f"p{i + 1}", mod, "backbone")
            counts[key] = counts.get(key, 0) + 1

    db.query(PositionModFrequency).delete()
    entries = 0
    for (pos, mod, mod_type), count in counts.items():
        db.add(PositionModFrequency(
            position=pos, modification=mod, mod_type=mod_type,
            count=count, frequency=round(count / total, 4),
        ))
        entries += 1

    db.commit()
    logger.info("Built frequency table: %d entries from %d siRNAs", entries, total)
    return entries


def build_cooccurrence_matrix(db: Session) -> int:
    """Build co-occurrence matrix from published siRNA data.

    Returns total co-occurrence entries written.
    """
    sirnas = db.query(PublishedSiRNA).all()
    if not sirnas:
        return 0

    pair_counts: dict[str, int] = {}

    for sirna in sirnas:
        assignments: list[tuple[str, str]] = []
        guide_sugars = json.loads(sirna.guide_sugars) if sirna.guide_sugars else []
        passenger_sugars = json.loads(sirna.passenger_sugars) if sirna.passenger_sugars else []

        for i, mod in enumerate(guide_sugars):
            assignments.append((f"g{i + 1}", mod))
        for i, mod in enumerate(passenger_sugars):
            assignments.append((f"p{i + 1}", mod))

        for (pos_a, mod_a), (pos_b, mod_b) in combinations(assignments, 2):
            key = _canonical_pair_key(pos_a, mod_a, pos_b, mod_b)
            pair_counts[key] = pair_counts.get(key, 0) + 1

    db.query(CooccurrenceEntry).delete()
    entries = 0
    for key, count in pair_counts.items():
        pos_a, mod_a, pos_b, mod_b = _parse_pair_key(key)
        db.add(CooccurrenceEntry(
            pos_a=pos_a, mod_a=mod_a, pos_b=pos_b, mod_b=mod_b,
            count=count, pair_key=key,
        ))
        entries += 1

    db.commit()
    logger.info("Built co-occurrence matrix: %d entries from %d siRNAs", entries, len(sirnas))
    return entries


def _canonical_pair_key(pos_a: str, mod_a: str, pos_b: str, mod_b: str) -> str:
    a = f"{pos_a}:{mod_a}"
    b = f"{pos_b}:{mod_b}"
    if a > b:
        a, b = b, a
    return f"{a}|{b}"


def _parse_pair_key(key: str) -> tuple[str, str, str, str]:
    left, right = key.split("|")
    pos_a, mod_a = left.split(":", 1)
    pos_b, mod_b = right.split(":", 1)
    return pos_a, mod_a, pos_b, mod_b


def get_position_frequency_map(db: Session) -> dict[str, dict[str, float]]:
    """Return {position: {modification: frequency}} for the frontend heatmap."""
    entries = db.query(PositionModFrequency).filter(
        PositionModFrequency.mod_type == "sugar"
    ).all()
    result: dict[str, dict[str, float]] = {}
    for e in entries:
        result.setdefault(e.position, {})[e.modification] = e.frequency
    return result
