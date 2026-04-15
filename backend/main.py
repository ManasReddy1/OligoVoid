"""FastAPI application for OligoVoid — siRNA modification research intelligence.

Endpoints:
  GET  /api/stats              — dashboard key numbers
  GET  /api/voids              — top voids with scores
  GET  /api/void/{void_id}     — full detail for one void
  GET  /api/modification-map   — position × modification heatmap matrix
  POST /api/score/custom       — biophysics + Claude scoring for custom pattern
  POST /api/dmtl/run           — run DMTL simulation
  GET  /api/dmtl/latest        — latest DMTL run results
  GET  /api/velocity/top       — top voids by closure velocity
  POST /api/community/result   — submit community validation result
  GET  /api/known-patterns     — all known FDA-approved/published patterns
  GET  /api/ontology           — full modification taxonomy
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

# ── Imports from OligoVoid modules ───────────────────────────────────────

from backend.database import (  # noqa: E402
    Base,
    KnownSiRNA,
    ModificationVoid,
    VoidFeasibilityScore,
    VoidClosureVelocity,
    DMTLCycleLog,
    CommunityResult,
    PublishedSiRNA,
    Void,
    init_db,
    get_db,
    seed_known_patterns,
    seed_demo_voids,
)
from backend.modification_grammar import (  # noqa: E402
    SUGAR_MODIFICATIONS,
    BACKBONE_MODIFICATIONS,
    TERMINAL_CONJUGATES,
    SUGAR_MODS_LIST,
    BACKBONE_MODS_LIST,
    CONJUGATE_LIST,
    ABBREVIATION_MAP,
    REVERSE_ABBREVIATION_MAP,
    SugarMod,
    all_positions,
    get_ontology_stats,
    get_known_pattern_coverage,
    KNOWN_PATTERNS,
    SEED_REGION,
    CLEAVAGE_SITE,
)
from backend.literature_parser import (  # noqa: E402
    PUBLISHED_MODIFICATIONS_DATASET,
    load_published_sirnas,
    build_frequency_table,
    build_cooccurrence_matrix,
    build_position_cooccurrence_matrix,
    get_position_coverage_stats,
    get_position_frequency_map,
    search_pubmed_for_pattern,
)
from backend.void_detector import (  # noqa: E402
    detect_voids,
    enumerate_modification_voids,
    calculate_hamming_to_nearest,
    get_void_novelty_score,
    classify_void_type,
    get_void_summary,
    get_top_voids,
    get_voids_by_position,
)
from backend.feasibility_scorer import (  # noqa: E402
    score_pattern_biophysics,
    score_void_with_claude,
    save_scores_to_db,
    score_and_save,
    format_guide_strand,
    format_passenger_strand,
    score_void_biophysics,
    score_void_combined,
    batch_score_biophysics,
)
from backend.active_learner import (  # noqa: E402
    ActiveLearner,
    run_dmtl_demo,
    suggest_next_void,
    record_dmtl_cycle,
    get_dmtl_history,
)
from backend.velocity_tracker import (  # noqa: E402
    get_velocity_history,
    get_fastest_closing,
    get_stale_voids,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# APP SETUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app = FastAPI(
    title="OligoVoid",
    description="siRNA modification design space research intelligence platform",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup: init DB, seed known patterns ────────────────────────────────

@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("OligoVoid database initialized")

    db = next(get_db())
    try:
        # Seed known patterns if not present
        known_count = db.query(KnownSiRNA).count()
        if known_count == 0:
            seed_known_patterns(db)
            seed_demo_voids(db)
            logger.info("Seeded known patterns and demo voids")

        # Auto-load published siRNAs on first run
        pub_count = db.query(PublishedSiRNA).count()
        if pub_count == 0:
            loaded = load_published_sirnas(db)
            if loaded > 0:
                build_frequency_table(db)
                build_cooccurrence_matrix(db)
                logger.info("Auto-loaded %d published siRNAs and built matrices", loaded)
    finally:
        db.close()


# ── In-memory cache for DMTL results ────────────────────────────────────

_latest_dmtl_result: Optional[dict] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FRONTEND SERVING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FRONTEND_DIR = PROJECT_ROOT / "frontend"


@app.get("/", response_class=FileResponse)
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


# Mount static files AFTER all API routes are defined (at bottom of file)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/stats — Dashboard key numbers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    """Key dashboard numbers for OligoVoid."""
    known_count = db.query(KnownSiRNA).count()
    void_count = db.query(ModificationVoid).count()
    scored_count = db.query(VoidFeasibilityScore).count()
    dmtl_count = db.query(DMTLCycleLog).count()

    # Top OligoVoid score
    top_score_row = (
        db.query(VoidFeasibilityScore.overall_oligovoid_score)
        .order_by(VoidFeasibilityScore.overall_oligovoid_score.desc())
        .first()
    )
    top_score = top_score_row[0] if top_score_row else 0.0

    # Position coverage stats from literature parser
    coverage_stats = get_position_coverage_stats()

    return {
        "known_patterns": known_count,
        "total_void_candidates": void_count,
        "voids_scored": scored_count,
        "modification_space_explored_pct": coverage_stats["percent_explored"],
        "top_oligovoid_score": top_score,
        "active_dmtl_cycles_run": dmtl_count,
        "position_coverage": coverage_stats,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/voids — Top voids with scores
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/voids")
def list_voids(
    limit: int = Query(20, ge=1, le=200),
    min_score: float = Query(0.0, ge=0.0, le=100.0),
    void_type: Optional[str] = Query(None, description="Filter: conservative_variant, regional_explorer, modification_pioneer, chemistry_hybrid"),
    sort_by: str = Query("overall_oligovoid_score", description="Sort field"),
    db: Session = Depends(get_db),
):
    """Top voids with full scores, sorted by chosen field."""
    # Query voids with their scores
    query = (
        db.query(ModificationVoid, VoidFeasibilityScore)
        .outerjoin(
            VoidFeasibilityScore,
            ModificationVoid.void_id == VoidFeasibilityScore.void_id,
        )
        .filter(ModificationVoid.is_void == True)  # noqa: E712
    )

    if min_score > 0:
        query = query.filter(
            VoidFeasibilityScore.overall_oligovoid_score >= min_score
        )

    # Sort
    sort_map = {
        "overall_oligovoid_score": VoidFeasibilityScore.overall_oligovoid_score.desc().nullslast(),
        "thermodynamic_score": VoidFeasibilityScore.thermodynamic_score.desc().nullslast(),
        "risc_loading_score": VoidFeasibilityScore.risc_loading_score.desc().nullslast(),
        "nuclease_resistance_score": VoidFeasibilityScore.nuclease_resistance_score.desc().nullslast(),
        "predicted_knockdown_pct": VoidFeasibilityScore.predicted_knockdown_pct.desc().nullslast(),
        "hamming_distance": ModificationVoid.hamming_distance_to_nearest.desc(),
    }
    order_clause = sort_map.get(sort_by, sort_map["overall_oligovoid_score"])
    query = query.order_by(order_clause)

    rows = query.limit(limit).all()

    results = []
    for void, score in rows:
        entry = _void_to_response(void, score)

        # Apply void_type filter in-memory (classification is computed, not stored)
        if void_type:
            void_dict = _void_to_pattern_dict(void)
            cls = classify_void_type(void_dict)
            if cls["void_type"] != void_type:
                continue
            entry["classification"] = cls
        else:
            void_dict = _void_to_pattern_dict(void)
            entry["classification"] = classify_void_type(void_dict)

        results.append(entry)

    return {"count": len(results), "voids": results}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/void/{void_id} — Full detail for one void
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/void/{void_id}")
def get_void_detail(void_id: str, db: Session = Depends(get_db)):
    """Full detail for one void: scores, position breakdown, nearest comparison, DMTL history."""
    void = db.query(ModificationVoid).filter(
        ModificationVoid.void_id == void_id
    ).first()
    if not void:
        raise HTTPException(status_code=404, detail="Void not found")

    # All scores for this void
    scores = (
        db.query(VoidFeasibilityScore)
        .filter(VoidFeasibilityScore.void_id == void_id)
        .order_by(VoidFeasibilityScore.scored_at.desc())
        .all()
    )

    # Nearest known pattern comparison
    nearest_pattern = None
    position_diff: list[dict] = []
    if void.closest_known_pattern_id:
        nearest = db.query(KnownSiRNA).filter(
            KnownSiRNA.pattern_id == void.closest_known_pattern_id
        ).first()
        if nearest:
            nearest_pattern = _known_to_response(nearest)
            # Position-by-position comparison
            for i in range(21):
                v_char = void.guide_notation[i] if i < len(void.guide_notation) else "?"
                n_char = nearest.guide_notation[i] if i < len(nearest.guide_notation) else "?"
                if v_char != n_char:
                    v_mod = REVERSE_ABBREVIATION_MAP.get(v_char, v_char)
                    n_mod = REVERSE_ABBREVIATION_MAP.get(n_char, n_char)
                    position_diff.append({
                        "strand": "guide",
                        "position": i + 1,
                        "void_mod": v_mod,
                        "known_mod": n_mod,
                        "void_abbrev": v_char,
                        "known_abbrev": n_char,
                    })
            for i in range(21):
                v_char = void.passenger_notation[i] if i < len(void.passenger_notation) else "?"
                n_char = nearest.passenger_notation[i] if i < len(nearest.passenger_notation) else "?"
                if v_char != n_char:
                    v_mod = REVERSE_ABBREVIATION_MAP.get(v_char, v_char)
                    n_mod = REVERSE_ABBREVIATION_MAP.get(n_char, n_char)
                    position_diff.append({
                        "strand": "passenger",
                        "position": i + 1,
                        "void_mod": v_mod,
                        "known_mod": n_mod,
                        "void_abbrev": v_char,
                        "known_abbrev": n_char,
                    })

    # DMTL history for this void
    dmtl_logs = (
        db.query(DMTLCycleLog)
        .filter(DMTLCycleLog.recommended_void_id == void_id)
        .order_by(DMTLCycleLog.cycle_number.asc())
        .all()
    )

    # Community results
    community = (
        db.query(CommunityResult)
        .filter(CommunityResult.void_id == void_id)
        .order_by(CommunityResult.submitted_at.desc())
        .all()
    )

    # Closure velocity
    velocity = db.query(VoidClosureVelocity).filter(
        VoidClosureVelocity.void_id == void_id
    ).first()

    # Position-by-position modification breakdown
    guide_breakdown = _notation_to_position_list(void.guide_notation, "guide")
    passenger_breakdown = _notation_to_position_list(void.passenger_notation, "passenger")

    return {
        "void_id": void.void_id,
        "description": void.description,
        "guide_notation": void.guide_notation,
        "passenger_notation": void.passenger_notation,
        "backbone_guide": json.loads(void.backbone_guide) if void.backbone_guide else [],
        "backbone_passenger": json.loads(void.backbone_passenger) if void.backbone_passenger else [],
        "conjugate": void.conjugate,
        "is_void": void.is_void,
        "hamming_distance_to_nearest": void.hamming_distance_to_nearest,
        "closest_known_pattern_id": void.closest_known_pattern_id,
        "times_similar_tested": void.times_similar_tested,

        "scores": [
            {
                "scored_by": s.scored_by,
                "overall_oligovoid_score": s.overall_oligovoid_score,
                "thermodynamic_score": s.thermodynamic_score,
                "risc_loading_score": s.risc_loading_score,
                "nuclease_resistance_score": s.nuclease_resistance_score,
                "off_target_risk_score": s.off_target_risk_score,
                "seed_region_compatibility": s.seed_region_compatibility,
                "predicted_knockdown_pct": s.predicted_knockdown_pct,
                "one_line_insight": s.one_line_insight,
                "why_untested": s.why_untested,
                "recommended_experiment": s.recommended_experiment,
                "confidence_level": s.confidence_level,
                "scored_at": s.scored_at.isoformat() if s.scored_at else None,
            }
            for s in scores
        ],

        "position_breakdown": {
            "guide": guide_breakdown,
            "passenger": passenger_breakdown,
        },

        "nearest_known_pattern": nearest_pattern,
        "position_differences": position_diff,

        "dmtl_history": [
            {
                "cycle_number": d.cycle_number,
                "recommendation_reason": d.recommendation_reason,
                "acquisition_function": d.acquisition_function,
                "information_gain": d.information_gain,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in dmtl_logs
        ],

        "community_results": [
            {
                "reporter": c.reporter,
                "result": c.result,
                "reported_knockdown": c.reported_knockdown,
                "notes": c.notes,
                "submitted_at": c.submitted_at.isoformat() if c.submitted_at else None,
            }
            for c in community
        ],

        "closure_velocity": {
            "papers_2018_2020": velocity.papers_2018_2020 if velocity else 0,
            "papers_2020_2022": velocity.papers_2020_2022 if velocity else 0,
            "papers_2022_2024": velocity.papers_2022_2024 if velocity else 0,
            "papers_2024_2026": velocity.papers_2024_2026 if velocity else 0,
            "velocity_trend": velocity.velocity_trend if velocity else 0.0,
            "classification": velocity.classification if velocity else "unknown",
        } if velocity else None,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/modification-map — Heatmap data
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/modification-map")
def modification_map():
    """Position × modification co-occurrence matrix for heatmap visualization."""
    matrix = build_position_cooccurrence_matrix()

    # Reformat for frontend
    guide_strand: dict[str, dict[str, int]] = {}
    for pos_num, mods in matrix["guide"].items():
        guide_strand[f"position_{pos_num}"] = mods

    passenger_strand: dict[str, dict[str, int]] = {}
    for pos_num, mods in matrix["passenger"].items():
        passenger_strand[f"position_{pos_num}"] = mods

    void_positions = [
        {
            "strand": vp["strand"],
            "position": vp["position"],
            "modification": vp["mod"],
        }
        for vp in matrix["void_positions"]
    ]

    return {
        "guide_strand": guide_strand,
        "passenger_strand": passenger_strand,
        "void_positions": void_positions,
        "total_patterns": len(PUBLISHED_MODIFICATIONS_DATASET),
        "sugar_modifications": SUGAR_MODS_LIST,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/score/custom — Score a custom pattern
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CustomPatternRequest(BaseModel):
    guide_modifications: list[str] = Field(..., min_length=21, max_length=21)
    passenger_modifications: list[str] = Field(..., min_length=21, max_length=21)
    backbone_guide: list[str] = Field(default_factory=lambda: ["PO"] * 20, min_length=20, max_length=20)
    backbone_passenger: list[str] = Field(default_factory=lambda: ["PO"] * 20, min_length=20, max_length=20)
    conjugate: str = "None"


@app.post("/api/score/custom")
async def score_custom_pattern(req: CustomPatternRequest):
    """Score a user-submitted custom siRNA modification pattern.

    Runs biophysics scoring immediately, then Claude scoring.
    Returns full scores within ~8 seconds.
    """
    # Validate mod codes
    valid_mods = set(SUGAR_MODS_LIST)
    for i, mod in enumerate(req.guide_modifications):
        if mod not in valid_mods:
            raise HTTPException(400, f"Invalid guide modification at position {i + 1}: '{mod}'. Valid: {SUGAR_MODS_LIST}")
    for i, mod in enumerate(req.passenger_modifications):
        if mod not in valid_mods:
            raise HTTPException(400, f"Invalid passenger modification at position {i + 1}: '{mod}'. Valid: {SUGAR_MODS_LIST}")

    valid_bb = {"PO", "PS", "MsPA"}
    for i, bb in enumerate(req.backbone_guide):
        if bb not in valid_bb:
            raise HTTPException(400, f"Invalid guide backbone at linkage {i + 1}: '{bb}'")
    for i, bb in enumerate(req.backbone_passenger):
        if bb not in valid_bb:
            raise HTTPException(400, f"Invalid passenger backbone at linkage {i + 1}: '{bb}'")

    pattern = {
        "guide_mods": req.guide_modifications,
        "passenger_mods": req.passenger_modifications,
        "backbone_guide": req.backbone_guide,
        "backbone_passenger": req.backbone_passenger,
        "conjugate": req.conjugate,
    }

    # Find nearest known
    known_dicts = [
        {"pattern_id": p.get("pattern_id", ""), "guide_mods": p["guide_mods"], "passenger_mods": p["passenger_mods"]}
        for p in PUBLISHED_MODIFICATIONS_DATASET
    ]
    nearest_id, hamming = calculate_hamming_to_nearest(pattern, known_dicts)
    pattern["nearest_known_id"] = nearest_id
    pattern["hamming_to_nearest"] = hamming

    # Biophysics scores
    bio_scores = score_pattern_biophysics(pattern)

    # Claude scoring (async)
    combined = await score_void_with_claude(pattern, bio_scores)

    # Novelty score
    novelty = get_void_novelty_score(pattern, PUBLISHED_MODIFICATIONS_DATASET)

    # Classification
    pattern_for_cls = {**pattern, "hamming_to_nearest": hamming, "changes": []}
    classification = classify_void_type(pattern_for_cls)

    # Format display
    guide_display = format_guide_strand(pattern)
    passenger_display = format_passenger_strand(pattern)

    return {
        **combined,
        "novelty_score": novelty,
        "nearest_known_pattern": nearest_id,
        "hamming_to_nearest": hamming,
        "classification": classification,
        "guide_display": guide_display,
        "passenger_display": passenger_display,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/dmtl/run — Run DMTL simulation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DMTLRunRequest(BaseModel):
    n_cycles: int = Field(default=8, ge=1, le=20)
    acquisition_function: str = Field(default="balanced")


@app.post("/api/dmtl/run")
async def run_dmtl(
    req: DMTLRunRequest,
    db: Session = Depends(get_db),
):
    """Run DMTL simulation and return full cycle log."""
    global _latest_dmtl_result

    result = await run_dmtl_demo(n_cycles=req.n_cycles, db=db)
    _latest_dmtl_result = result
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/dmtl/latest — Latest DMTL results
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/dmtl/latest")
def dmtl_latest(db: Session = Depends(get_db)):
    """Return the latest DMTL run results for dashboard display."""
    global _latest_dmtl_result
    if _latest_dmtl_result:
        return _latest_dmtl_result

    # Fall back to DB logs — deduplicate by taking the latest entry per cycle_number
    from sqlalchemy import func as sa_func
    subq = (
        db.query(sa_func.max(DMTLCycleLog.id).label("max_id"))
        .group_by(DMTLCycleLog.cycle_number)
        .subquery()
    )
    logs = (
        db.query(DMTLCycleLog)
        .join(subq, DMTLCycleLog.id == subq.c.max_id)
        .order_by(DMTLCycleLog.cycle_number.asc())
        .all()
    )
    if not logs:
        return {"title": "No DMTL runs yet", "summary": {}, "cycles": []}

    return {
        "title": f"DMTL History: {len(logs)} Cycles",
        "summary": {
            "total_cycles": len(logs),
            "uncertainty_reduction_pct": None,
            "coverage_improvement_pct": None,
        },
        "cycles": [
            {
                "cycle": log.cycle_number,
                "void_tested": log.recommended_void_id,
                "expected_kd": None,
                "actual_kd": None,
                "uncertainty_before": log.model_uncertainty_before,
                "uncertainty_after": log.model_uncertainty_after,
                "info_gain": log.information_gain,
                "patterns_known": None,
                "reason": log.recommendation_reason,
                "what_we_learn": "",
            }
            for log in logs
        ],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/velocity/top — Top voids by closure velocity
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/velocity/top")
def velocity_top(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Top voids by Void Closure Velocity (fastest closing = most urgent)."""
    velocities = (
        db.query(VoidClosureVelocity, ModificationVoid, VoidFeasibilityScore)
        .join(ModificationVoid, VoidClosureVelocity.void_id == ModificationVoid.void_id)
        .outerjoin(VoidFeasibilityScore, VoidClosureVelocity.void_id == VoidFeasibilityScore.void_id)
        .order_by(VoidClosureVelocity.velocity_trend.desc())
        .limit(limit)
        .all()
    )

    return {
        "count": len(velocities),
        "voids": [
            {
                "void_id": vel.void_id,
                "velocity_trend": vel.velocity_trend,
                "classification": vel.classification,
                "papers_2018_2020": vel.papers_2018_2020,
                "papers_2020_2022": vel.papers_2020_2022,
                "papers_2022_2024": vel.papers_2022_2024,
                "papers_2024_2026": vel.papers_2024_2026,
                "urgency_rank": vel.urgency_rank,
                "guide_notation": void.guide_notation,
                "passenger_notation": void.passenger_notation,
                "description": void.description,
                "overall_score": score.overall_oligovoid_score if score else None,
                "predicted_knockdown": score.predicted_knockdown_pct if score else None,
            }
            for vel, void, score in velocities
        ],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/community/result — Submit community validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CommunityResultRequest(BaseModel):
    void_id: str
    reporter: str = "anonymous"
    result: str = Field(default="pending", description="worked|partial|failed|pending")
    reported_knockdown: Optional[float] = None
    notes: str = ""


@app.post("/api/community/result")
def submit_community_result(
    req: CommunityResultRequest,
    db: Session = Depends(get_db),
):
    """Submit a community validation result for a void."""
    # Verify the void exists
    void = db.query(ModificationVoid).filter(
        ModificationVoid.void_id == req.void_id
    ).first()
    if not void:
        raise HTTPException(404, f"Void {req.void_id} not found")

    if req.result not in ("worked", "partial", "failed", "pending"):
        raise HTTPException(400, "result must be: worked, partial, failed, or pending")

    record = CommunityResult(
        void_id=req.void_id,
        reporter=req.reporter,
        result=req.result,
        reported_knockdown=req.reported_knockdown,
        notes=req.notes,
    )
    db.add(record)
    db.commit()

    # If the void was validated (worked), optionally mark it as no longer void
    if req.result == "worked" and req.reported_knockdown and req.reported_knockdown >= 50:
        void.is_void = False
        db.commit()

    return {
        "status": "submitted",
        "void_id": req.void_id,
        "result": req.result,
        "reported_knockdown": req.reported_knockdown,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/known-patterns — All known FDA/published patterns
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/known-patterns")
def known_patterns(db: Session = Depends(get_db)):
    """Return all known FDA-approved and published siRNA patterns."""
    patterns = db.query(KnownSiRNA).order_by(KnownSiRNA.year_published.desc()).all()

    return {
        "count": len(patterns),
        "patterns": [_known_to_response(p) for p in patterns],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/ontology — Full modification taxonomy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/ontology")
def ontology():
    """Full modification taxonomy for UI dropdowns and reference."""
    return {
        "sugar_modifications": SUGAR_MODIFICATIONS,
        "backbone_modifications": BACKBONE_MODIFICATIONS,
        "terminal_conjugates": TERMINAL_CONJUGATES,
        "abbreviation_map": ABBREVIATION_MAP,
        "reverse_abbreviation_map": REVERSE_ABBREVIATION_MAP,
        "sugar_mods_list": SUGAR_MODS_LIST,
        "backbone_mods_list": BACKBONE_MODS_LIST,
        "conjugate_list": CONJUGATE_LIST,
        "stats": get_ontology_stats(),
        "known_pattern_coverage": get_known_pattern_coverage(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEGACY ROUTES (backward compat)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/grammar")
def get_grammar():
    """Return the modification grammar stats."""
    return get_ontology_stats()


@app.get("/api/positions")
def get_positions():
    return {"positions": all_positions(), "total": len(all_positions())}


@app.get("/api/published")
def list_published(db: Session = Depends(get_db)):
    """List all published siRNA designs from legacy table."""
    sirnas = db.query(PublishedSiRNA).order_by(PublishedSiRNA.year.desc()).all()
    return {
        "count": len(sirnas),
        "sirnas": [
            {
                "id": s.id,
                "name": s.name,
                "source": s.source,
                "year": s.year,
                "company": s.company,
                "target_gene": s.target_gene,
                "guide_sugars": json.loads(s.guide_sugars) if s.guide_sugars else [],
                "passenger_sugars": json.loads(s.passenger_sugars) if s.passenger_sugars else [],
                "guide_backbone": json.loads(s.guide_backbone) if s.guide_backbone else [],
                "passenger_backbone": json.loads(s.passenger_backbone) if s.passenger_backbone else [],
                "conjugate": s.conjugate,
            }
            for s in sirnas
        ],
    }


@app.post("/api/published/reload")
def reload_published(db: Session = Depends(get_db)):
    loaded = load_published_sirnas(db)
    freq_count = build_frequency_table(db)
    cooc_count = build_cooccurrence_matrix(db)
    return {"sirnas_loaded": loaded, "frequency_entries": freq_count, "cooccurrence_entries": cooc_count}


@app.get("/api/frequencies")
def get_frequencies(db: Session = Depends(get_db)):
    freq_map = get_position_frequency_map(db)
    return {"frequencies": freq_map, "sugar_mods": SUGAR_MODS_LIST}


@app.post("/api/voids/detect")
def run_void_detection(
    threshold: int = Query(3, ge=1, le=20),
    positions: str = Query(None),
    modifications: str = Query(None),
    db: Session = Depends(get_db),
):
    pos_filter = positions.split(",") if positions else None
    mod_filter = modifications.split(",") if modifications else None
    new_voids = detect_voids(db, threshold=threshold, position_filter=pos_filter, mod_filter=mod_filter)
    summary = get_void_summary(db)
    return {"new_voids_detected": new_voids, **summary}


@app.get("/api/voids/summary")
def void_summary(db: Session = Depends(get_db)):
    return get_void_summary(db)


@app.post("/api/score/biophysics")
def score_biophysics_batch(
    void_ids: str = Query(None),
    db: Session = Depends(get_db),
):
    ids = [int(x) for x in void_ids.split(",")] if void_ids else None
    count = batch_score_biophysics(db, void_ids=ids)
    return {"scored": count}


@app.post("/api/score/{void_id}")
async def score_single_void(void_id: int, db: Session = Depends(get_db)):
    void = db.query(Void).filter(Void.id == void_id).first()
    if not void:
        raise HTTPException(status_code=404, detail="Void not found")
    return await score_void_combined(void, db)


@app.get("/api/dmtl/suggest")
def dmtl_suggest(top_k: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    return {"suggestions": suggest_next_void(db, top_k=top_k)}


@app.post("/api/dmtl/record")
def dmtl_record(void_id: int = Query(...), outcome: str = Query("pending"), db: Session = Depends(get_db)):
    cycle = record_dmtl_cycle(db, void_id=void_id, outcome=outcome)
    return {"cycle_number": cycle.cycle_number, "void_id": cycle.suggested_void_id, "outcome": cycle.outcome}


@app.get("/api/dmtl/history")
def dmtl_history(db: Session = Depends(get_db)):
    return {"cycles": get_dmtl_history(db)}


@app.get("/api/velocity/fastest")
def fastest_closing(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    return {"voids": get_fastest_closing(db, limit)}


@app.get("/api/velocity/stale")
def stale_voids_route(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    return {"voids": get_stale_voids(db, limit)}


@app.get("/api/velocity/{void_id}")
def void_velocity(void_id: int, db: Session = Depends(get_db)):
    history = get_velocity_history(db, void_id)
    void = db.query(Void).filter(Void.id == void_id).first()
    if not void:
        raise HTTPException(status_code=404, detail="Void not found")
    return {"void_id": void_id, "current_velocity": void.closure_velocity, "history": history}


# ── PubMed search (async) ───────────────────────────────────────────────

@app.get("/api/pubmed/search")
async def pubmed_search(query: str = Query(..., min_length=3)):
    """Search PubMed for papers related to a modification description."""
    result = await search_pubmed_for_pattern(query)
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RESPONSE HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _void_to_response(void: ModificationVoid, score: Optional[VoidFeasibilityScore]) -> dict:
    """Convert a ModificationVoid + optional score to API response dict."""
    return {
        "void_id": void.void_id,
        "guide_notation": void.guide_notation,
        "passenger_notation": void.passenger_notation,
        "conjugate": void.conjugate,
        "hamming_distance_to_nearest": void.hamming_distance_to_nearest,
        "closest_known_pattern_id": void.closest_known_pattern_id,
        "times_similar_tested": void.times_similar_tested,
        "description": void.description,
        "overall_oligovoid_score": score.overall_oligovoid_score if score else None,
        "thermodynamic_score": score.thermodynamic_score if score else None,
        "risc_loading_score": score.risc_loading_score if score else None,
        "nuclease_resistance_score": score.nuclease_resistance_score if score else None,
        "off_target_risk_score": score.off_target_risk_score if score else None,
        "seed_region_compatibility": score.seed_region_compatibility if score else None,
        "predicted_knockdown_pct": score.predicted_knockdown_pct if score else None,
        "one_line_insight": score.one_line_insight if score else "",
        "why_untested": score.why_untested if score else "",
        "recommended_experiment": score.recommended_experiment if score else "",
        "confidence_level": score.confidence_level if score else None,
        "scored_by": score.scored_by if score else None,
    }


def _void_to_pattern_dict(void: ModificationVoid) -> dict:
    """Convert a ModificationVoid DB record to a pattern dict for scoring/classification."""
    guide = [REVERSE_ABBREVIATION_MAP.get(c, c) for c in void.guide_notation]
    passenger = [REVERSE_ABBREVIATION_MAP.get(c, c) for c in void.passenger_notation]
    return {
        "guide_mods": guide,
        "passenger_mods": passenger,
        "backbone_guide": json.loads(void.backbone_guide) if void.backbone_guide else [],
        "backbone_passenger": json.loads(void.backbone_passenger) if void.backbone_passenger else [],
        "conjugate": void.conjugate,
        "hamming_to_nearest": void.hamming_distance_to_nearest,
        "nearest_known_id": void.closest_known_pattern_id,
        "changes": [],
    }


def _known_to_response(p: KnownSiRNA) -> dict:
    """Convert a KnownSiRNA DB record to API response dict."""
    guide_mods = [REVERSE_ABBREVIATION_MAP.get(c, c) for c in p.guide_notation]
    passenger_mods = [REVERSE_ABBREVIATION_MAP.get(c, c) for c in p.passenger_notation]

    return {
        "pattern_id": p.pattern_id,
        "drug_name": p.drug_name,
        "guide_notation": p.guide_notation,
        "passenger_notation": p.passenger_notation,
        "guide_modifications": guide_mods,
        "passenger_modifications": passenger_mods,
        "backbone_guide": json.loads(p.backbone_guide) if p.backbone_guide else [],
        "backbone_passenger": json.loads(p.backbone_passenger) if p.backbone_passenger else [],
        "conjugate": p.conjugate,
        "reported_knockdown": p.reported_knockdown,
        "target_gene": p.target_gene,
        "cell_line": p.cell_line,
        "source_paper": p.source_paper,
        "year_published": p.year_published,
        "company": p.company,
    }


def _notation_to_position_list(notation: str, strand: str) -> list[dict]:
    """Convert a 21-char notation string to a list of position dicts."""
    positions = []
    for i, char in enumerate(notation):
        pos = i + 1
        mod_name = REVERSE_ABBREVIATION_MAP.get(char, char)
        region = "other"
        if strand == "guide":
            if 2 <= pos <= 8:
                region = "seed"
            elif pos in (10, 11):
                region = "cleavage_site"
            elif 13 <= pos <= 16:
                region = "supplementary"
            elif 19 <= pos <= 21:
                region = "3prime_overhang"
            elif pos == 1:
                region = "5prime_end"
        else:
            if 2 <= pos <= 8:
                region = "seed_match"

        positions.append({
            "position": pos,
            "strand": strand,
            "abbreviation": char,
            "modification": mod_name,
            "region": region,
        })
    return positions


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STATIC FILES (must be mounted LAST to avoid catching /api/* routes)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
