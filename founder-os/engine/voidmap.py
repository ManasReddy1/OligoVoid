"""Occupancy of the design space, and the classification of its holes.

A cell is keyed by (unlock, audience-class, mechanic). Shipped products make it
occupied; dead products make it tombstoned; neither makes it a void. Tombstoned
cells paired with a fresh unlock are the highest-value region, because "right
idea, wrong decade" is the most reliable source of opportunity.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from genome import _norm_key

OCCUPIED = "occupied"
TOMBSTONED = "tombstoned"
VOID = "void"
FRONTIER = "frontier"       # void, and its unlock crossed recently


@dataclass
class Cell:
    unlock: str
    audience: str
    mechanic: str
    state: str
    products: list[str]
    tombstones: list[str]

    @property
    def key(self) -> str:
        return f"{self.unlock}|{self.audience}|{self.mechanic}"


class VoidMap:
    def __init__(self, unlocks: list[dict], audiences: list[str],
                 products: list[dict], fresh_unlock_ids: set[str] | None = None):
        self.unlocks = unlocks
        self.audiences = [_norm_key(a) for a in audiences]
        self.fresh = fresh_unlock_ids or set()
        self.mechanics: list[str] = []
        self._occ: dict[tuple[str, str], list[str]] = defaultdict(list)
        self._tomb: dict[tuple[str, str], list[str]] = defaultdict(list)
        self._ingest(products)

    def _ingest(self, products: Iterable[dict]) -> None:
        seen = set()
        for p in products:
            mech = _norm_key(p.get("mechanic", "") or "unknown")
            aud = _norm_key(p.get("audience", "") or "unknown")
            if mech not in seen:
                seen.add(mech)
                self.mechanics.append(mech)
            bucket = self._tomb if p.get("status") == "dead" else self._occ
            bucket[(aud, mech)].append(p.get("name", "?"))

    # -- queries ----------------------------------------------------------

    def state(self, unlock_key: str, audience: str, mechanic: str) -> str:
        aud, mech = _norm_key(audience), _norm_key(mechanic)
        if self._occ.get((aud, mech)):
            return OCCUPIED
        if self._tomb.get((aud, mech)):
            return TOMBSTONED
        return FRONTIER if unlock_key in self.fresh else VOID

    def cell(self, unlock_key: str, audience: str, mechanic: str) -> Cell:
        aud, mech = _norm_key(audience), _norm_key(mechanic)
        return Cell(unlock=unlock_key, audience=aud, mechanic=mech,
                    state=self.state(unlock_key, audience, mechanic),
                    products=self._occ.get((aud, mech), []),
                    tombstones=self._tomb.get((aud, mech), []))

    def coverage(self) -> dict[str, Any]:
        """How much of the enumerated space anybody has actually touched."""
        total = len(self.unlocks) * len(self.audiences) * max(1, len(self.mechanics))
        counts = {OCCUPIED: 0, TOMBSTONED: 0, VOID: 0, FRONTIER: 0}
        for u in self.unlocks:
            uk = u.get("key", "")
            for a in self.audiences:
                for m in self.mechanics:
                    counts[self.state(uk, a, m)] += 1
        touched = counts[OCCUPIED] + counts[TOMBSTONED]
        return {"total_cells": total,
                "counts": counts,
                "explored_fraction": round(touched / total, 4) if total else 0.0,
                "void_fraction": round(1 - (touched / total), 4) if total else 0.0}

    def revival_candidates(self) -> list[dict[str, Any]]:
        """Tombstoned cells whose cause of death a fresh unlock may dissolve."""
        out = []
        for (aud, mech), names in self._tomb.items():
            if self._occ.get((aud, mech)):
                continue                      # somebody made it work since
            for u in self.unlocks:
                if u.get("key") in self.fresh:
                    out.append({"audience": aud, "mechanic": mech,
                                "dead": names, "unlock": u.get("key"),
                                "unlock_title": u.get("title", "")})
        return out
