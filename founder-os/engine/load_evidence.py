"""Load harvested evidence into the world model.

Idempotent: re-running replaces the store's evidence rather than duplicating
it. Every row must carry a live source_url or it is refused at the store layer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from store import Store

DATA = Path(__file__).parent / "data"


def load_json(name: str) -> list[dict]:
    p = DATA / name
    if not p.exists():
        print(f"  ! {name} missing, skipped")
        return []
    try:
        d = json.loads(p.read_text())
    except ValueError as e:
        print(f"  ! {name} is not valid JSON: {e}")
        return []
    return d if isinstance(d, list) else []


def main(db: str | None = None, reset: bool = False) -> None:
    """Load evidence incrementally.

    Wiping the store is destructive in a way that is easy to miss: ideas cite
    signals by id, so a reload that reassigns ids silently orphans every
    citation in every existing cycle and gate L2 starts killing sound ideas.
    So by default this adds what is new and leaves the rest alone. `--reset`
    is available for a genuinely fresh start.
    """
    s = Store(db) if db else Store()
    if reset:
        s.db.executescript("DELETE FROM signals; DELETE FROM products;")
        s.db.commit()
        print("  store reset")

    seen_sig = {(r["kind"], r["source_url"], r["title"]) for r in s.signals()}
    seen_prod = {(p["name"], p["source_url"]) for p in s.products()}

    n = {"UNLOCK": 0, "PAIN": 0, "TOMBSTONE": 0, "PRODUCT": 0, "PRIOR": 0}
    skipped = 0

    def add_signal(kind, title, url, **kw):
        nonlocal skipped
        if (kind, url, title) in seen_sig:
            skipped += 1
            return False
        seen_sig.add((kind, url, title))
        s.add_signal(kind, title, url, **kw)
        return True

    def add_product(name, **kw):
        nonlocal skipped
        key = (name, kw.get("source_url", ""))
        if key in seen_prod:
            skipped += 1
            return False
        seen_prod.add(key)
        s.add_product(name, **kw)
        return True

    for u in load_json("unlocks.json"):
        if not add_signal("UNLOCK", u["title"], u["source_url"],
                     body=u.get("note", ""), payload=u,
                          source_name="capability_curve",
                          dated_at=u.get("dated_at"),
                          confidence=float(u.get("confidence", 0.8))):
            continue
        n["UNLOCK"] += 1

    for name in ("pains_health.json", "pains_life.json", "pains.json"):
        for p in load_json(name):
            url = p.get("source_url")
            if not url:
                continue
            title = f"{p.get('who', '?')}: {p.get('what_breaks', '')}"[:200]
            if not add_signal("PAIN", title, url,
                              body=p.get("quote", ""), payload=p,
                              source_name="pain_miner",
                              dated_at=p.get("dated_at"),
                              confidence=float(p.get("confidence", 0.6))):
                continue
            n["PAIN"] += 1

    for t in load_json("tombstones.json"):
        url = t.get("source_url")
        if not url:
            continue
        if not add_signal("TOMBSTONE", f"{t.get('name')} ({t.get('died', '?')})",
                          url, body=t.get("stated_cause", ""), payload=t,
                          source_name="graveyard", dated_at=t.get("dated_at"),
                          confidence=0.8):
            continue
        n["TOMBSTONE"] += 1
        # A dead product is also an occupancy fact: the cell was tried.
        add_product(t.get("name", "?"), one_line=t.get("one_line", ""),
                    audience=t.get("audience", ""),
                    mechanic=t.get("mechanic", "") or _mech_from(t),
                    status="dead", payload=t,
                    source_url=url, dated_at=t.get("dated_at"))

    for p in load_json("products.json"):
        if not p.get("source_url"):
            continue
        if not add_product(p.get("name", "?"), one_line=p.get("one_line", ""),
                           audience=p.get("audience", ""),
                           mechanic=p.get("mechanic", ""),
                           monetization=p.get("monetization", ""),
                           status="shipped", payload=p,
                           source_url=p["source_url"], dated_at=p.get("dated_at")):
            continue
        n["PRODUCT"] += 1

    # PRIOR rows are what a model says cold, with no evidence. They are the
    # obviousness baseline for gate L1, not evidence about the world.
    for pr in load_json("priors.json"):
        if not add_signal("PRIOR", pr if isinstance(pr, str) else pr.get("text", ""),
                          "https://internal/cold-model-prior",
                          source_name="cold_prior", confidence=1.0):
            continue
        n["PRIOR"] += 1

    print("added:", {k: v for k, v in n.items() if v}, f"| already present: {skipped}")
    print("products in corpus:", len(s.products()),
          "(shipped", len(s.products('shipped')),
          ", dead", len(s.products('dead')), ")")
    s.close()


def _mech_from(t: dict) -> str:
    blob = (t.get("one_line", "") + " " + t.get("stated_cause", "")).lower()
    for k, v in (("voice", "voice_conversation"), ("robot", "voice_conversation"),
                 ("track", "passive_tracking"), ("sleep", "passive_tracking"),
                 ("habit", "streak_habit"), ("deliver", "marketplace_match"),
                 ("marketplace", "marketplace_match"), ("video", "async_social"),
                 ("social", "async_social"), ("news", "scheduled_digest"),
                 ("photo", "capture_and_answer"), ("scan", "capture_and_answer")):
        if k in blob:
            return v
    return "unknown"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--reset"]
    main(args[0] if args else None, reset="--reset" in sys.argv)
