"""SQLAlchemy models, initialization, and seed data for OligoVoid.

Six primary tables for the research intelligence platform:
  KnownSiRNA              — published/FDA-approved modification patterns
  ModificationVoid        — untested patterns (the "voids")
  VoidFeasibilityScore    — biophysics + LLM feasibility scores per void
  VoidClosureVelocity     — temporal tracking of how fast voids are being filled
  DMTLCycleLog            — Design-Make-Test-Learn cycle records
  CommunityResult         — crowd-sourced experimental results

Plus legacy tables retained for backward compatibility with
void_detector.py, literature_parser.py, and feasibility_scorer.py.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "oligovoid.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def _utcnow():
    return datetime.now(timezone.utc)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TABLE 1 — KnownSiRNA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class KnownSiRNA(Base):
    """A published or FDA-approved siRNA modification pattern."""

    __tablename__ = "known_sirnas"

    id = Column(Integer, primary_key=True, index=True)
    pattern_id = Column(String(64), unique=True, nullable=False, index=True)
    drug_name = Column(String(256), nullable=False)
    guide_notation = Column(String(21), nullable=False)      # 21-char abbreviation string
    passenger_notation = Column(String(21), nullable=False)
    backbone_guide = Column(Text, default="")                 # JSON array of 20 linkages
    backbone_passenger = Column(Text, default="")
    conjugate = Column(String(64), default="None")
    reported_knockdown = Column(Float, nullable=True)         # 0-100%
    target_gene = Column(String(128), default="")
    cell_line = Column(String(128), default="")
    source_paper = Column(Text, default="")
    year_published = Column(Integer, nullable=True)
    company = Column(String(128), default="")
    created_at = Column(DateTime, default=_utcnow)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TABLE 2 — ModificationVoid
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ModificationVoid(Base):
    """An untested siRNA modification pattern — a research gap."""

    __tablename__ = "modification_voids"

    id = Column(Integer, primary_key=True, index=True)
    void_id = Column(String(32), unique=True, nullable=False, index=True)
    guide_notation = Column(String(21), nullable=False)
    passenger_notation = Column(String(21), nullable=False)
    backbone_guide = Column(Text, default="")
    backbone_passenger = Column(Text, default="")
    conjugate = Column(String(64), default="None")
    is_void = Column(Boolean, default=True)
    closest_known_pattern_id = Column(
        String(64), ForeignKey("known_sirnas.pattern_id"), nullable=True
    )
    hamming_distance_to_nearest = Column(Integer, default=0)
    times_similar_tested = Column(Integer, default=0)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TABLE 3 — VoidFeasibilityScore
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class VoidFeasibilityScore(Base):
    """Multi-dimensional feasibility score for a void.

    Each void can have multiple scores (one per scorer: biophysics_rules,
    claude_api). The most recent of each type is authoritative.
    """

    __tablename__ = "void_feasibility_scores"

    id = Column(Integer, primary_key=True, index=True)
    void_id = Column(
        String(32), ForeignKey("modification_voids.void_id"), nullable=False, index=True
    )
    thermodynamic_score = Column(Float, default=0.0)          # predicted ΔG stability
    nuclease_resistance_score = Column(Float, default=0.0)
    risc_loading_score = Column(Float, default=0.0)
    off_target_risk_score = Column(Float, default=0.0)        # LOWER is better
    seed_region_compatibility = Column(Float, default=0.0)
    overall_oligovoid_score = Column(Float, default=0.0)
    predicted_knockdown_pct = Column(Float, nullable=True)    # 0-100
    one_line_insight = Column(Text, default="")
    why_untested = Column(Text, default="")
    recommended_experiment = Column(Text, default="")
    confidence_level = Column(String(16), default="medium")   # low/medium/high
    scored_by = Column(String(32), default="biophysics_rules")
    scored_at = Column(DateTime, default=_utcnow)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TABLE 4 — VoidClosureVelocity
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class VoidClosureVelocity(Base):
    """Temporal tracking of publication activity around a void.

    Papers are binned by 2-year window. The velocity_trend is the linear
    slope (papers per 2-year bin). Classification:
      cold     = 0 papers total
      warming  = 1-3 papers, positive trend
      hot      = 4+ papers or steep positive trend
      closed   = void is no longer a void (enough evidence exists)
    """

    __tablename__ = "void_closure_velocity"

    id = Column(Integer, primary_key=True, index=True)
    void_id = Column(
        String(32), ForeignKey("modification_voids.void_id"), nullable=False, index=True
    )
    papers_2018_2020 = Column(Integer, default=0)
    papers_2020_2022 = Column(Integer, default=0)
    papers_2022_2024 = Column(Integer, default=0)
    papers_2024_2026 = Column(Integer, default=0)
    velocity_trend = Column(Float, default=0.0)               # linear slope
    classification = Column(String(16), default="cold")       # cold/warming/hot/closed
    urgency_rank = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TABLE 5 — DMTLCycleLog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DMTLCycleLog(Base):
    """A Design-Make-Test-Learn cycle — tracks what OligoVoid recommended
    and what information was gained."""

    __tablename__ = "dmtl_cycle_logs"

    id = Column(Integer, primary_key=True, index=True)
    cycle_number = Column(Integer, nullable=False, index=True)
    recommended_void_id = Column(
        String(32), ForeignKey("modification_voids.void_id"), nullable=True
    )
    recommendation_reason = Column(Text, default="")
    acquisition_function = Column(String(32), default="uncertainty")
    model_uncertainty_before = Column(Float, default=0.0)
    model_uncertainty_after = Column(Float, default=0.0)      # simulated post-test
    information_gain = Column(Float, default=0.0)
    created_at = Column(DateTime, default=_utcnow)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TABLE 6 — CommunityResult
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CommunityResult(Base):
    """Crowd-sourced experimental results for tested voids."""

    __tablename__ = "community_results"

    id = Column(Integer, primary_key=True, index=True)
    void_id = Column(
        String(32), ForeignKey("modification_voids.void_id"), nullable=False, index=True
    )
    reporter = Column(String(256), default="anonymous")
    result = Column(String(32), default="pending")            # worked/partial/failed
    reported_knockdown = Column(Float, nullable=True)         # 0-100
    notes = Column(Text, default="")
    submitted_at = Column(DateTime, default=_utcnow)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEGACY TABLES — retained for backward compat with void_detector,
# literature_parser, feasibility_scorer, active_learner, velocity_tracker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PublishedSiRNA(Base):
    """Legacy: imported siRNA designs from published_sirnas.json."""

    __tablename__ = "published_sirnas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False, index=True)
    source = Column(Text, default="")
    year = Column(Integer, nullable=True)
    company = Column(String(128), default="")
    target_gene = Column(String(128), default="")
    guide_sugars = Column(Text, default="")
    passenger_sugars = Column(Text, default="")
    guide_backbone = Column(Text, default="")
    passenger_backbone = Column(Text, default="")
    conjugate = Column(String(64), default="None")
    pattern_fingerprint = Column(Text, default="", index=True)
    created_at = Column(DateTime, default=_utcnow)


class PositionModFrequency(Base):
    """Position × modification frequency from published data."""

    __tablename__ = "position_mod_frequencies"

    id = Column(Integer, primary_key=True, index=True)
    position = Column(String(8), nullable=False, index=True)
    modification = Column(String(32), nullable=False, index=True)
    mod_type = Column(String(16), default="sugar")
    count = Column(Integer, default=0)
    frequency = Column(Float, default=0.0)


class CooccurrenceEntry(Base):
    """Co-occurrence count for a (position:mod, position:mod) pair."""

    __tablename__ = "cooccurrence"

    id = Column(Integer, primary_key=True, index=True)
    pos_a = Column(String(8), nullable=False, index=True)
    mod_a = Column(String(32), nullable=False)
    pos_b = Column(String(8), nullable=False, index=True)
    mod_b = Column(String(32), nullable=False)
    count = Column(Integer, default=0)
    pair_key = Column(String(128), unique=True, index=True)


class Void(Base):
    """Legacy: co-occurrence pair voids for void_detector.py."""

    __tablename__ = "voids"

    id = Column(Integer, primary_key=True, index=True)
    pos_a = Column(String(8), nullable=False, index=True)
    mod_a = Column(String(32), nullable=False)
    pos_b = Column(String(8), nullable=False, index=True)
    mod_b = Column(String(32), nullable=False)
    pair_key = Column(String(128), unique=True, index=True)
    observation_count = Column(Integer, default=0)
    is_void = Column(Boolean, default=True)
    feasibility_score = Column(Float, nullable=True)
    feasibility_rationale = Column(Text, default="")
    claude_score = Column(Float, nullable=True)
    claude_rationale = Column(Text, default="")
    information_gain = Column(Float, default=0.0)
    closure_velocity = Column(Float, default=0.0)
    last_scanned = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class VelocitySnapshot(Base):
    """Legacy: point-in-time snapshot for velocity tracking."""

    __tablename__ = "velocity_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    void_id = Column(Integer, nullable=False, index=True)
    observation_count = Column(Integer, default=0)
    snapshot_date = Column(DateTime, default=_utcnow)


class DMTLCycle(Base):
    """Legacy: DMTL cycle for active_learner.py."""

    __tablename__ = "dmtl_cycles"

    id = Column(Integer, primary_key=True, index=True)
    cycle_number = Column(Integer, default=1)
    suggested_void_id = Column(Integer, nullable=True)
    suggestion_rationale = Column(Text, default="")
    outcome = Column(Text, default="")
    information_gained = Column(Float, default=0.0)
    created_at = Column(DateTime, default=_utcnow)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATABASE INIT & DEPENDENCY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SEED: known patterns
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Metadata for the 5 known patterns (keyed by pattern_id from modification_grammar)
_KNOWN_PATTERN_META: dict[str, dict] = {
    "ESC_001": {
        "drug_name": "Inclisiran (Leqvio)",
        "target_gene": "PCSK9",
        "cell_line": "HepG2",
        "year_published": 2020,
        "company": "Alnylam / Novartis",
    },
    "STD_001": {
        "drug_name": "Patisiran (Onpattro)",
        "target_gene": "TTR",
        "cell_line": "Hep3B",
        "year_published": 2018,
        "company": "Alnylam",
    },
    "ESC_002": {
        "drug_name": "Givosiran (Givlaari)",
        "target_gene": "ALAS1",
        "cell_line": "Primary hepatocytes",
        "year_published": 2020,
        "company": "Alnylam",
    },
    "CLASSIC_001": {
        "drug_name": "Standard siRNA (academic baseline)",
        "target_gene": "Various (reporter genes)",
        "cell_line": "HeLa",
        "year_published": 2004,
        "company": "Academic",
    },
    "KHVOROVA_001": {
        "drug_name": "Fully-stabilized siRNA",
        "target_gene": "HTT",
        "cell_line": "Primary hepatocytes",
        "year_published": 2017,
        "company": "UMass Chan Medical School",
    },
}


def seed_known_patterns(db) -> int:
    """Insert the 5 known patterns from modification_grammar.py into KnownSiRNA.

    Returns number of records inserted.
    """
    from backend.modification_grammar import KNOWN_PATTERNS, ABBREVIATION_MAP

    inserted = 0
    for pat in KNOWN_PATTERNS:
        if db.query(KnownSiRNA).filter(KnownSiRNA.pattern_id == pat.pattern_id).first():
            continue

        guide_n = "".join(
            ABBREVIATION_MAP.get(m, "?") for m in pat.guide_modifications
        )
        passenger_n = "".join(
            ABBREVIATION_MAP.get(m, "?") for m in pat.passenger_modifications
        )
        meta = _KNOWN_PATTERN_META.get(pat.pattern_id, {})

        record = KnownSiRNA(
            pattern_id=pat.pattern_id,
            drug_name=meta.get("drug_name", pat.source),
            guide_notation=guide_n,
            passenger_notation=passenger_n,
            backbone_guide=json.dumps(pat.guide_backbone),
            backbone_passenger=json.dumps(pat.passenger_backbone),
            conjugate=pat.terminal_conjugate,
            reported_knockdown=pat.knockdown_efficacy,
            target_gene=meta.get("target_gene", ""),
            cell_line=meta.get("cell_line", ""),
            source_paper=pat.source,
            year_published=meta.get("year_published"),
            company=meta.get("company", ""),
        )
        db.add(record)
        inserted += 1

    db.commit()
    logger.info("Seeded %d known siRNA patterns", inserted)
    return inserted


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SEED: demo voids
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _void_hash(guide: str, passenger: str, conjugate: str, backbone: str = "") -> str:
    """Deterministic 12-char hex hash for a void pattern."""
    raw = f"{guide}|{passenger}|{conjugate}|{backbone}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _hamming(a: str, b: str) -> int:
    """Hamming distance between two equal-length notation strings."""
    return sum(1 for x, y in zip(a, b) if x != y)


def _find_nearest_known(
    guide_n: str, passenger_n: str, known: list[KnownSiRNA]
) -> tuple[str, int]:
    """Return (pattern_id, hamming_distance) of the closest known pattern."""
    best_id = ""
    best_dist = 999
    for k in known:
        d = _hamming(guide_n, k.guide_notation) + _hamming(passenger_n, k.passenger_notation)
        if d < best_dist:
            best_dist = d
            best_id = k.pattern_id
    return best_id, best_dist


# ESC reference notations for building variants
_ESC_GUIDE = "mfmfmfmfmfmfmfmfmfmfm"
_ESC_PASS = "mfmfmfmfmfmfmfmfmfmfm"
_BB_TERMINAL_PS = '["PS","PS","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PS","PS"]'
_BB_TERMINAL_MSPA = '["MsPA","MsPA","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","MsPA","MsPA"]'
_BB_ALL_PS = '["PS","PS","PS","PS","PS","PS","PS","PS","PS","PS","PS","PS","PS","PS","PS","PS","PS","PS","PS","PS"]'


# Void definitions: (guide_notation, passenger_notation, backbone_guide, backbone_passenger, conjugate, description)
_DEMO_VOID_DEFS: list[tuple[str, str, str, str, str, str]] = [
    # 1. UNA at guide position 1 — strand selection advantage
    (
        "Ufmfmfmfmfmfmfmfmfmfm",
        _ESC_PASS,
        _BB_TERMINAL_PS, _BB_TERMINAL_PS,
        "GalNAc",
        "ESC + UNA at guide position 1: thermodynamically favors guide strand RISC loading",
    ),
    # 2. LNA at guide positions 17-18 — 3' stability boost
    (
        "mfmfmfmfmfmfmfmfLLmfm",
        _ESC_PASS,
        _BB_TERMINAL_PS, _BB_TERMINAL_PS,
        "GalNAc",
        "ESC + LNA at guide g17-g18: extreme 3' thermostability without seed/cleavage interference",
    ),
    # 3. All 2'-F guide — maximum RISC loading potential
    (
        "fffffffffffffffffffff",
        _ESC_PASS,
        _BB_TERMINAL_PS, _BB_TERMINAL_PS,
        "GalNAc",
        "All-fluorine guide strand: maximizes 2'-F RISC loading at cost of nuclease resistance",
    ),
    # 4. LNA-spiked passenger + ESC guide — ultra-stable passenger
    (
        _ESC_GUIDE,
        "LmLmLmLmLmLmLmLmLmLmL",
        _BB_TERMINAL_PS, _BB_TERMINAL_PS,
        "GalNAc",
        "ESC guide + alternating LNA/OMe passenger: tests whether rigid passenger blocks RISC unwinding",
    ),
    # 5. MsPA backbone + ESC sugar pattern — reduced immunogenicity
    (
        _ESC_GUIDE,
        _ESC_PASS,
        _BB_TERMINAL_MSPA, _BB_TERMINAL_MSPA,
        "GalNAc",
        "ESC sugars + mesyl phosphoramidate backbone: PS-equivalent stability with lower immune activation",
    ),
    # 6. DNA at cleavage site (g10-g11) — natural catalytic geometry
    (
        "mfmfmfmfmddfmfmfmfmfm",
        _ESC_PASS,
        _BB_TERMINAL_PS, _BB_TERMINAL_PS,
        "GalNAc",
        "ESC + DNA at g10-g11 cleavage site: preserves native Ago2 catalytic geometry for slicing",
    ),
    # 7. All-OMe passenger — simplified synthesis
    (
        _ESC_GUIDE,
        "mmmmmmmmmmmmmmmmmmmmm",
        _BB_TERMINAL_PS, _BB_TERMINAL_PS,
        "GalNAc",
        "ESC guide + uniform 2'-OMe passenger: reduces synthesis complexity and off-target passenger loading",
    ),
    # 8. F-seed + LNA-3' guide — specificity + terminal stability
    (
        "mfffffffmfmfmfmfmfLLm",
        _ESC_PASS,
        _BB_TERMINAL_PS, _BB_TERMINAL_PS,
        "GalNAc",
        "2'-F enriched seed (g2-g8) + LNA at g19-g20: optimal RISC loading + extreme 3' exonuclease protection",
    ),
    # 9. UNA-g1 + cEt-g19/g20 — complementary terminal effects
    (
        "UfmfmfmfmfmfmfmfmfEEm",
        _ESC_PASS,
        _BB_TERMINAL_PS, _BB_TERMINAL_PS,
        "GalNAc",
        "UNA at 5' (flexible, strand selection) + cEt at 3' (rigid, stability): opposing terminal chemistry",
    ),
    # 10. ESC + cholesterol conjugate — extrahepatic targeting
    (
        _ESC_GUIDE,
        _ESC_PASS,
        _BB_TERMINAL_PS, _BB_TERMINAL_PS,
        "Cholesterol",
        "Standard ESC chemistry with cholesterol conjugate: enables muscle/CNS delivery beyond liver",
    ),
]

# Feasibility scores for each void: (thermo, nuclease, risc, offtarget, seed, overall, knockdown,
#   insight, why_untested, experiment, confidence)
_DEMO_VOID_SCORES: list[tuple] = [
    # Void 1: UNA at g1
    (68, 75, 88, 18, 95, 82, 78,
     "UNA at guide 5' end thermodynamically favors guide strand RISC loading over passenger",
     "UNA modifications are newer; no systematic siRNA study combining UNA-g1 with ESC chemistry",
     "Synthesize ESC+UNA(g1) targeting TTR in HepG2 cells, compare IC50 to standard ESC",
     "high"),
    # Void 2: LNA at g17-g18
    (92, 94, 78, 35, 95, 85, 82,
     "LNA at 3' end dramatically increases duplex Tm without affecting seed or cleavage regions",
     "LNA in siRNA context is understudied; most LNA research is in ASOs, not GalNAc-siRNAs",
     "Position-walk LNA at guide 3' end (g17-g21), measure duplex Tm and silencing in HepG2",
     "high"),
    # Void 3: All F guide
    (72, 65, 95, 42, 95, 68, 65,
     "Maximum 2'-F may optimize RISC loading but sacrifices nuclease resistance vs mixed OMe/F",
     "2'-F is more expensive than 2'-OMe; no incentive to test all-F when alternating works well",
     "Compare all-F guide vs ESC guide with identical passenger/backbone, qPCR knockdown in HepG2",
     "medium"),
    # Void 4: LNA-spiked passenger
    (95, 98, 38, 55, 90, 45, 35,
     "Heavy LNA on passenger may prevent efficient duplex unwinding during RISC loading",
     "Conventional wisdom says rigid passenger impairs RISC; untested whether partial LNA is tolerated",
     "Titrate LNA on passenger (2, 4, 6, 8, 11 positions), measure RISC loading by Ago2 IP-western",
     "medium"),
    # Void 5: MsPA backbone
    (80, 88, 85, 25, 95, 86, 80,
     "Mesyl phosphoramidate backbone matches PS nuclease resistance with lower immunogenicity",
     "MsPA is an Ionis innovation for ASOs; systematic siRNA application lags behind",
     "Replace terminal PS with MsPA in ESC design, compare innate immune markers + potency in mice",
     "high"),
    # Void 6: DNA at cleavage
    (62, 70, 82, 30, 95, 75, 72,
     "DNA at cleavage site preserves native Ago2 catalytic geometry; may enhance slicing kcat",
     "DNA destabilizes the duplex locally; groups default to 2'-OMe/F at cleavage positions",
     "Compare DNA, RNA, 2'-OMe, 2'-F at g10-g11 in matched ESC context, measure kcat by in vitro cleavage assay",
     "medium"),
    # Void 7: All-OMe passenger
    (85, 90, 72, 20, 95, 78, 70,
     "Uniform 2'-OMe passenger simplifies synthesis and reduces off-target passenger strand loading",
     "ESC alternating pattern on both strands was established early; all-OMe passenger not prioritized",
     "Compare all-OMe vs ESC passenger with identical guide, dual-luciferase assay in HeLa cells",
     "high"),
    # Void 8: F-seed + LNA-3'
    (88, 90, 80, 28, 92, 83, 79,
     "Combining F-rich seed for RISC loading with LNA 3'-end for stability may yield optimal pharmacology",
     "LNA and 2'-F have been studied separately but rarely combined in one guide strand with GalNAc",
     "Synthesize F-seed/LNA-3' guide in GalNAc context, measure Tm + silencing duration timecourse",
     "medium"),
    # Void 9: UNA-g1 + cEt-g19/g20
    (78, 82, 85, 15, 95, 84, 80,
     "UNA at 5' favors guide selection; cEt at 3' provides strong terminal stability — complementary effects",
     "Combining two non-standard modifications (UNA + cEt) in one strand requires custom synthesis optimization",
     "Synthesize UNA(g1)+cEt(g19-20) guide, measure strand loading ratio by mass spec + silencing durability",
     "medium"),
    # Void 10: ESC + cholesterol
    (80, 85, 85, 30, 95, 80, 60,
     "Cholesterol conjugation enables muscle and CNS delivery where GalNAc (liver-only) cannot reach",
     "Industry focused on liver via GalNAc; cholesterol-siRNA potency is lower, deprioritized after 2018",
     "Inject cholesterol-ESC siRNA targeting muscle gene (e.g., MSTN), biodistribution + qPCR in mice",
     "low"),
]

# Closure velocity data for demo voids
_DEMO_VOID_VELOCITIES: list[tuple[int, int, int, int]] = [
    # (papers_18_20, papers_20_22, papers_22_24, papers_24_26)
    (0, 1, 1, 2),   # void 1: warming — UNA gaining interest
    (0, 0, 1, 1),   # void 2: cold/warming
    (1, 1, 0, 0),   # void 3: cooling — tested then abandoned
    (0, 0, 0, 1),   # void 4: nearly cold
    (0, 0, 2, 3),   # void 5: warming fast — MsPA is trendy
    (1, 0, 1, 0),   # void 6: flat
    (0, 1, 0, 1),   # void 7: sporadic
    (0, 0, 0, 1),   # void 8: emerging
    (0, 0, 0, 0),   # void 9: completely cold
    (2, 1, 0, 0),   # void 10: cooling — cholesterol fell out of favor
]


def seed_demo_voids(db) -> int:
    """Generate 10 interesting void patterns derived from ESC and insert them.

    Populates ModificationVoid, VoidFeasibilityScore, and VoidClosureVelocity.
    Returns number of voids inserted.
    """
    # We need known patterns loaded first for nearest-neighbor calculation
    known = db.query(KnownSiRNA).all()
    if not known:
        seed_known_patterns(db)
        known = db.query(KnownSiRNA).all()

    inserted = 0
    for i, (g_n, p_n, bb_g, bb_p, conj, desc) in enumerate(_DEMO_VOID_DEFS):
        vid = _void_hash(g_n, p_n, conj, bb_g)

        if db.query(ModificationVoid).filter(ModificationVoid.void_id == vid).first():
            continue

        nearest_id, hamming = _find_nearest_known(g_n, p_n, known)
        # Count how many known patterns are within hamming ≤ 5
        times_similar = sum(
            1 for k in known
            if _hamming(g_n, k.guide_notation) + _hamming(p_n, k.passenger_notation) <= 5
        )

        void = ModificationVoid(
            void_id=vid,
            guide_notation=g_n,
            passenger_notation=p_n,
            backbone_guide=bb_g,
            backbone_passenger=bb_p,
            conjugate=conj,
            is_void=True,
            closest_known_pattern_id=nearest_id,
            hamming_distance_to_nearest=hamming,
            times_similar_tested=times_similar,
            description=desc,
        )
        db.add(void)
        db.flush()  # get void_id available for FK references

        # ── Feasibility score ────────────────────────────────────────
        (thermo, nuc, risc, ot, seed, overall, kd,
         insight, why, experiment, confidence) = _DEMO_VOID_SCORES[i]

        score = VoidFeasibilityScore(
            void_id=vid,
            thermodynamic_score=float(thermo),
            nuclease_resistance_score=float(nuc),
            risc_loading_score=float(risc),
            off_target_risk_score=float(ot),
            seed_region_compatibility=float(seed),
            overall_oligovoid_score=float(overall),
            predicted_knockdown_pct=float(kd),
            one_line_insight=insight,
            why_untested=why,
            recommended_experiment=experiment,
            confidence_level=confidence,
            scored_by="biophysics_rules",
        )
        db.add(score)

        # ── Closure velocity ─────────────────────────────────────────
        p18, p20, p22, p24 = _DEMO_VOID_VELOCITIES[i]
        total_papers = p18 + p20 + p22 + p24
        # Linear slope across 4 bins (x = 0,1,2,3)
        bins = [p18, p20, p22, p24]
        n = len(bins)
        sx = sum(range(n))
        sy = sum(bins)
        sxy = sum(j * bins[j] for j in range(n))
        sx2 = sum(j * j for j in range(n))
        denom = n * sx2 - sx * sx
        trend = (n * sxy - sx * sy) / denom if denom else 0.0

        if total_papers == 0:
            classification = "cold"
        elif total_papers >= 4 or trend > 0.8:
            classification = "hot"
        elif trend > 0:
            classification = "warming"
        else:
            classification = "cold"

        vel = VoidClosureVelocity(
            void_id=vid,
            papers_2018_2020=p18,
            papers_2020_2022=p20,
            papers_2022_2024=p22,
            papers_2024_2026=p24,
            velocity_trend=round(trend, 3),
            classification=classification,
            urgency_rank=i + 1,
        )
        db.add(vel)
        inserted += 1

    db.commit()
    logger.info("Seeded %d demo voids with scores and velocity data", inserted)
    return inserted
