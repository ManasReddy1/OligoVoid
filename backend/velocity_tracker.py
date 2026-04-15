"""Void Closure Velocity engine for OligoVoid.

Tracks how fast each research gap is being filled over time. A high closure
velocity means the community is converging on this combination — the void
is about to disappear. This helps prioritize: test fast-closing voids before
someone else publishes, or focus on stable voids that nobody is exploring.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.database import Void, VelocitySnapshot

logger = logging.getLogger(__name__)


def record_snapshot(db: Session, void_id: int, observation_count: int) -> VelocitySnapshot:
    """Record a point-in-time observation count for a void."""
    snapshot = VelocitySnapshot(
        void_id=void_id,
        observation_count=observation_count,
        snapshot_date=datetime.now(timezone.utc),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def compute_velocity(db: Session, void_id: int) -> float:
    """Compute closure velocity (observations per 365-day period).

    Uses linear regression over all snapshots. Returns 0.0 if fewer
    than 2 snapshots exist.
    """
    snapshots = (
        db.query(VelocitySnapshot)
        .filter(VelocitySnapshot.void_id == void_id)
        .order_by(VelocitySnapshot.snapshot_date.asc())
        .all()
    )

    if len(snapshots) < 2:
        return 0.0

    first_date = snapshots[0].snapshot_date
    points = []
    for s in snapshots:
        days = (s.snapshot_date - first_date).total_seconds() / 86400.0
        points.append((days, s.observation_count))

    n = len(points)
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_x2 = sum(p[0] ** 2 for p in points)

    denom = n * sum_x2 - sum_x ** 2
    if denom == 0:
        return 0.0

    slope_per_day = (n * sum_xy - sum_x * sum_y) / denom
    velocity_per_year = slope_per_day * 365.0

    return round(velocity_per_year, 4)


def update_void_velocity(db: Session, void: Void) -> float:
    """Record current observation count and recompute velocity."""
    record_snapshot(db, void.id, void.observation_count)
    velocity = compute_velocity(db, void.id)
    void.closure_velocity = velocity
    db.commit()
    return velocity


def get_velocity_history(db: Session, void_id: int) -> list[dict]:
    """Return the snapshot history for a void."""
    snapshots = (
        db.query(VelocitySnapshot)
        .filter(VelocitySnapshot.void_id == void_id)
        .order_by(VelocitySnapshot.snapshot_date.asc())
        .all()
    )
    return [
        {
            "date": s.snapshot_date.isoformat(),
            "observation_count": s.observation_count,
        }
        for s in snapshots
    ]


def get_fastest_closing(db: Session, limit: int = 10) -> list[dict]:
    """Return voids with the highest closure velocity."""
    voids = (
        db.query(Void)
        .filter(Void.is_void == True)  # noqa: E712
        .filter(Void.closure_velocity > 0)
        .order_by(Void.closure_velocity.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": v.id,
            "pos_a": v.pos_a,
            "mod_a": v.mod_a,
            "pos_b": v.pos_b,
            "mod_b": v.mod_b,
            "closure_velocity": v.closure_velocity,
            "observation_count": v.observation_count,
            "feasibility_score": v.feasibility_score,
        }
        for v in voids
    ]


def get_stale_voids(db: Session, limit: int = 10) -> list[dict]:
    """Return voids with zero or near-zero velocity — stable research gaps nobody is filling."""
    voids = (
        db.query(Void)
        .filter(Void.is_void == True)  # noqa: E712
        .filter(Void.closure_velocity <= 0.0)
        .filter(Void.feasibility_score >= 0.5)
        .order_by(Void.feasibility_score.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": v.id,
            "pos_a": v.pos_a,
            "mod_a": v.mod_a,
            "pos_b": v.pos_b,
            "mod_b": v.mod_b,
            "closure_velocity": v.closure_velocity,
            "observation_count": v.observation_count,
            "feasibility_score": v.feasibility_score,
        }
        for v in voids
    ]
