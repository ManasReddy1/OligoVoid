#!/usr/bin/env python3
"""End-to-end smoke test. Runs the whole ladder on synthetic model output.

No API key, no network, no third-party packages. Proves the pipeline advances,
that every gate actually kills, and that a report renders.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import report as report_mod
from llm import FileBackend
from orchestrator import CycleConfig, Orchestrator
from store import Store

FAIL = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        FAIL.append(name)


def seed(store: Store) -> None:
    store.add_signal("UNLOCK", "free on-device inference",
                     "https://example.com/unlock1",
                     payload={"key": "free_pcc", "old_cost": "per token",
                              "new_cost": "zero"}, dated_at="2026-06-09")
    store.add_signal("UNLOCK", "real-time voice at under two cents a minute",
                     "https://example.com/unlock2",
                     payload={"key": "voice", "old_cost": "uneconomic",
                              "new_cost": "$0.005/min"}, dated_at="2026-07-01")
    for i, (who, breaks) in enumerate([
        ("night-shift nurses", "cannot log anything during a 12-hour shift"),
        ("adult siblings sharing care of a parent", "lose track of a medication taper"),
        ("parents of a child with a new peanut allergy", "cannot verify trace allergens"),
    ]):
        store.add_signal("PAIN", f"{who}: {breaks}", f"https://example.com/pain{i}",
                         payload={"who": who, "what_breaks": breaks,
                                  "quote": "I gave up and used a notebook",
                                  "workaround": "paper notebook"})
    store.add_product("StreakFit", one_line="daily workout streak tracker",
                      audience="gym regulars", mechanic="streak_habit",
                      source_url="https://example.com/p1")
    store.add_product("NightLog", one_line="voice journal for nurses on night shift",
                      audience="night shift nurses", mechanic="voice_conversation",
                      source_url="https://example.com/p2")
    store.add_signal("PRIOR", "a voice journaling app for nurses",
                     "https://internal/cold-model-prior")
    store.add_signal("PRIOR", "a habit tracker with streaks for gym goers",
                     "https://internal/cold-model-prior")


def answer(backend: FileBackend, make) -> int:
    """Write a synthetic response for every pending prompt."""
    n = 0
    for path in backend.pending():
        d = json.loads(path.read_text())
        body = make(d)
        if body is None:
            continue
        (backend.responses / f"{d['task_id']}.json").write_text(
            json.dumps({"parsed": body, "text": "", "usage": {}}))
        n += 1
    return n


def fake(d: dict):
    label, meta = d["label"], d.get("meta", {})
    ids = [1, 2]

    if label.startswith("gen-island"):
        k = meta.get("island", 0)
        # Distinct audiences and mechanics per island, so descriptors do not
        # collide and the later gates actually get something to work on.
        pool = [
            ("night-shift nurses", "voice_conversation",
             "cannot log anything during a twelve-hour shift"),
            ("adult siblings sharing care of a parent", "shared_ledger",
             "lose track of a medication taper between visits"),
            ("parents of a child with a new peanut allergy", "capture_and_answer",
             "cannot verify trace allergens in a shop aisle"),
            ("rotating-shift firefighters", "passive_tracking",
             "sleep scoring assumes one nocturnal block and reads as zero"),
            ("adults tapering off a prescription", "guided_protocol",
             "no tool represents a dose that steps down on a schedule"),
            ("blind VoiceOver users writing long documents", "annotation_overlay",
             "premium note apps expose controls as unlabelled boxes"),
            ("warehouse forklift drivers", "ambient_capture",
             "continuous movement logs as dozens of unclassified moments"),
            ("women logging a pregnancy loss", "shared_ledger",
             "cycle apps have no state for a pregnancy that ended"),
            ("solo carers of a parent with early dementia", "scheduled_digest",
             "the shared medication view silently desyncs"),
        ]
        out = {"reasoning": "worked through the evidence", "candidates": []}
        for j in range(3):
            aud, mech, breaks = pool[(k * 3 + j) % len(pool)]
            out["candidates"].append({
                "title": f"{mech.replace('_', ' ').title()} for {aud[:28]}",
                "probability": 0.3,
                "unlock": {"value": "free on-device inference", "signal_ids": [1]},
                "pain": {"value": breaks, "signal_ids": [3 + (j % 3)]},
                "audience": {"value": aud},
                "mechanic": {"value": mech},
                "wedge": {"value": f"one narrow first case for {aud[:24]}"},
                "moat": {"value": "switching_cost_of_history"},
                "model": {"value": "subscription"},
                "loop": {"value": "invite_for_function"},
                "kill": ["fewer than 30% return in week two",
                         "under 5% invite a second person"],
                "why_now": "on-device inference removed the cost",
                "why_not_obvious": "nobody targets this population",
            })
        # one deliberately invalid candidate, to prove L0 bites
        out["candidates"].append({
            "title": f"Everything app {k}", "audience": {"value": "everyone"},
            "unlock": {"value": "ai"}, "pain": {"value": "life is hard"},
            "mechanic": {"value": "magic"}, "wedge": {"value": "all of it"},
            "moat": {"value": "vibes"}, "model": {"value": "ads"},
            "loop": {"value": "virality"}, "kill": ["it might not work"]})
        return out

    if label.startswith("build-"):
        iid = meta.get("idea_id", 0)
        # every third idea is priced into a negative margin, to prove L3 bites
        expensive = (iid % 3 == 0)
        return {"stack": "SwiftUI, on-device model, CloudKit",
                "milestones": ["capture loop", "sharing", "paywall"],
                "build_cost_usd": 18000 if not expensive else 47000,
                "weeks_to_v1": 9,
                "inference_cost_user_month": 0.05 if not expensive else 2.40,
                "price_month": 9.99, "expected_conversion": 0.04,
                "riskiest_technical_assumption": "on-device transcription is accurate enough",
                "cheapest_way_to_test_that_assumption": "record ten real shifts"}

    if label.startswith("attack-"):
        surface = meta.get("surface", "?")
        iid = meta.get("idea_id", 0)
        # one surface is fatal for some ideas, to prove L4 bites
        verdict = "fatal" if (surface == "retention_attacker" and iid % 2 == 0) \
            else ("wounded" if iid % 2 else "survived")
        return {"surface": surface, "attack": "a specific concrete objection",
                "strongest_defence": "the best available answer",
                "verdict": verdict, "verdict_reason": "because of the evidence"}

    if label.startswith("judge-"):
        a, b = meta.get("a"), meta.get("b")
        return {"checks": {}, "winner": "A" if (a or 0) < (b or 0) else "B",
                "margin": "narrow", "reason": "lower id wins, deterministically"}
    return None


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="fos-selftest-"))
    db = tmp / "test.db"
    work = tmp / "work"
    store = Store(db)
    seed(store)
    backend = FileBackend(work)
    cfg = CycleConfig(islands=3, per_island=3, panel_size=5,
                      tournament_max_pairs=40, budget_usd=99)
    orch = Orchestrator(store, backend, cfg)

    print("\nadvancing the cycle")
    rounds = 0
    while rounds < 8:
        rounds += 1
        orch.pending = []
        out = orch.run()
        pend = out.get("pending") or []
        if not pend:
            break
        wrote = answer(backend, fake)
        print(f"  round {rounds}: {len(pend)} pending -> answered {wrote}")
        orch = Orchestrator(store, backend, cfg, cycle_id=orch.cycle_id)

    ideas = store.ideas(cycle_id=orch.cycle_id)
    killed = [i for i in ideas if i["status"] == "killed"]
    alive = [i for i in ideas if i["status"] != "killed"]
    by_gate: dict[str, int] = {}
    for k in killed:
        by_gate[k["killed_at_gate"]] = by_gate.get(k["killed_at_gate"], 0) + 1

    print(f"\nresult: {len(ideas)} generated, {len(killed)} killed, {len(alive)} alive")
    print(f"kills by gate: {by_gate}")

    print("\nchecks")
    check("cycle terminated", rounds < 8, f"{rounds} rounds")
    check("ideas were generated", len(ideas) >= 9, f"{len(ideas)}")
    check("L0 killed the invalid candidates", by_gate.get("L0", 0) >= 3)
    check("L1 killed something", by_gate.get("L1", 0) >= 1)
    check("L3 killed a negative margin", by_gate.get("L3", 0) >= 1)
    check("L4 killed on a fatal attack", by_gate.get("L4", 0) >= 1)
    check("something survived", len(alive) >= 1, f"{len(alive)}")

    scored = [store.scores(i["id"]) for i in alive]
    scored = [s for s in scored if s]
    check("survivors were scored", len(scored) == len(alive))
    if scored:
        check("scores are in range",
              all(0 <= (s["founder_score"] or 0) <= 100 for s in scored))
        check("both heads present",
              all(s["novelty"] is not None and s["viability"] is not None
                  for s in scored))
        check("tournament produced ratings",
              all(s["elo_novelty"] is not None for s in scored))

    comps = store.comparisons()
    check("pairs were judged both ways",
          any(c["swapped"] for c in comps) and any(not c["swapped"] for c in comps),
          f"{len(comps)} comparisons")

    out_html = tmp / "report.html"
    report_mod.render(store, orch.cycle_id, out_html, title="Self-test")
    txt = out_html.read_text()
    check("report rendered", out_html.exists() and len(txt) > 4000, f"{len(txt)} bytes")
    check("report shows the kill log", "Kill log" in txt)
    check("report shows both heads", "novelty" in txt and "viability" in txt)

    store.close()
    shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print(f"{len(FAIL)} FAILED: {', '.join(FAIL)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
