#!/usr/bin/env python3
"""Command line for a Founder OS cycle.

    python3 run.py load                 load harvested evidence into the store
    python3 run.py cycle [--budget 6]   advance the cycle as far as it can go
    python3 run.py pending              list prompts waiting for an answer
    python3 run.py report [out.html]    render the current cycle

A cycle is resumable by design. When a stage needs model output it writes every
prompt it needs at once and stops; running `cycle` again picks up as soon as the
answers exist in work/responses/. With ANTHROPIC_API_KEY set the same pipeline
runs end to end without stopping.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import load_evidence
import report as report_mod
from llm import FileBackend, make_backend
from orchestrator import CycleConfig, Orchestrator
from store import Store

HERE = Path(__file__).parent
STATE = HERE / "work" / "cycle.json"


def _current_cycle(store: Store) -> int | None:
    if STATE.exists():
        try:
            return int(json.loads(STATE.read_text())["cycle_id"])
        except (ValueError, KeyError):
            pass
    row = store.db.execute("SELECT id FROM cycles ORDER BY id DESC LIMIT 1").fetchone()
    return int(row["id"]) if row else None


def cmd_load(args) -> None:
    load_evidence.main(args.db, reset=args.reset)


def cmd_cycle(args) -> None:
    store = Store(args.db) if args.db else Store()
    backend = make_backend(prefer_api=not args.files_only)
    cid = _current_cycle(store) if args.resume else None

    cfg = CycleConfig(theme=args.theme, budget_usd=args.budget, islands=args.islands,
                      per_island=args.per_island, panel_size=args.panel,
                      tournament_max_pairs=args.pairs)
    orch = Orchestrator(store, backend, cfg, cycle_id=cid)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"cycle_id": orch.cycle_id}))

    print(f"backend: {type(backend).__name__}   cycle: {orch.cycle_id}")
    out = orch.run()

    for stage, v in out.items():
        if stage in ("pending", "alive", "stalls", "halted"):
            continue
        print(f"  {stage:9s} {v}")
    print(f"  alive     {out.get('alive')}")
    if out.get("halted"):
        print(f"  HALTED    {out['halted']}")
    pend = out.get("pending") or []
    if pend:
        print(f"\n{len(pend)} prompts awaiting answers. Write each answer to")
        print(f"  {HERE / 'work' / 'responses'}/<task_id>.json")
        print("as {\"parsed\": <the JSON the prompt asked for>}")
        for t in pend[:8]:
            print("   -", t)
        if len(pend) > 8:
            print(f"   ... and {len(pend) - 8} more (see `run.py pending`)")
    store.close()


def cmd_pending(args) -> None:
    b = FileBackend()
    files = b.pending()
    print(f"{len(files)} pending")
    for f in files:
        d = json.loads(f.read_text())
        print(f"  {d['task_id']:46s} {d['label']:22s} tier={d['tier']}")


def cmd_report(args) -> None:
    store = Store(args.db) if args.db else Store()
    cid = _current_cycle(store)
    if cid is None:
        sys.exit("no cycle found; run `cycle` first")
    out = args.out or (HERE.parent / "web" / "report.html")
    p = report_mod.render(store, cid, out, title=args.title)
    print("wrote", p)
    store.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    lo = sub.add_parser("load")
    lo.add_argument("--reset", action="store_true",
                    help="wipe the store first. Reassigns signal ids, which "
                         "orphans citations in existing cycles")
    lo.set_defaults(fn=cmd_load)

    c = sub.add_parser("cycle")
    c.add_argument("--budget", type=float, default=6.0)
    c.add_argument("--islands", type=int, default=6)
    c.add_argument("--per-island", type=int, default=6)
    c.add_argument("--panel", type=int, default=6,
                   help="how many of the 7 attack surfaces to run. Surfaces beyond this are dropped from the END of the panel list and reported in the progress ledger")
    c.add_argument("--theme", default=None,
                   help="point the cycle at a problem space defined in "
                        "data/themes/<name>.json instead of the generic theses")
    c.add_argument("--pairs", type=int, default=90,
                   help="cap on tournament pairs per head; each pair is judged "
                        "twice, with the order swapped")
    c.add_argument("--files-only", action="store_true",
                   help="never call the API; always write prompts to disk")
    c.add_argument("--resume", action="store_true", default=True)
    c.add_argument("--new", dest="resume", action="store_false")
    c.set_defaults(fn=cmd_cycle)

    sub.add_parser("pending").set_defaults(fn=cmd_pending)

    r = sub.add_parser("report")
    r.add_argument("out", nargs="?", default=None)
    r.add_argument("--title", default="Founder OS Report")
    r.set_defaults(fn=cmd_report)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
