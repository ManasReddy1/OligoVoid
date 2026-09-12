"""The cycle driver. Sole writer of the world model.

Stages run in order and each one is resumable: when a stage needs model output
it writes every prompt it needs at once, then stops. Re-running picks up where
it left off as soon as the answers exist. That batching is deliberate — it is
what lets the expensive stages fan out instead of trickling.

Islands are assigned opposing theses about the market, not slices of a task.
Hypothesis portfolios need almost no inter-agent coherence, so they escape the
coordination cost that makes large agent groups misbehave (finding F2c/F3b).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import gates
import prompts as P
import scoring
import tournament
from genome import IdeaGenome, check_validity
from llm import Budget, BudgetExceeded, FileBackend, PendingResponse
from store import Store
from voidmap import VoidMap

# --------------------------------------------------------------------------
# Islands: opposing beliefs about the same market
# --------------------------------------------------------------------------

ISLANDS = [
    {"id": 0,
     "thesis": "Habit beats magic. The winner is a dull thing someone opens at "
               "the same moment every day, not an impressive one-shot result. "
               "The one-and-done problem kills everything else.",
     "operator": "first_principles_reducer",
     "brief": "Take a job someone already does badly by hand, strip it to its "
              "irreducible steps, and delete every step that only exists because "
              "of an old technical limitation. Name the removed steps."},
    {"id": 1,
     "thesis": "Magic beats habit. People pay for a result they could not get at "
               "all before, and retention follows from the result being worth "
               "repeating, not from streak mechanics.",
     "operator": "frontier_cartographer",
     "brief": "Find the capability whose cost crossed a threshold in the last 18 "
              "months and ask only this: what was structurally impossible at the "
              "old price and is trivial at the new one."},
    {"id": 2,
     "thesis": "The opportunity is in the tombstones. Everything worth building "
               "was tried and died of a constraint that has since dissolved.",
     "operator": "tombstone_reviver",
     "brief": "Pair a dead product with a specific new unlock and show that the "
              "stated cause of death is gone. You must name the unlock. A revival "
              "with no named unlock is just re-proposing a failure."},
    {"id": 3,
     "thesis": "The incumbents are structurally blind. Every category leader has "
               "a constraint it cannot remove without destroying itself, and the "
               "product lives in that blind spot.",
     "operator": "constraint_archaeologist",
     "brief": "For a category leader, name the constraint it structurally cannot "
              "remove: business model lock, platform dependency, brand promise, "
              "obligation to existing users, or data it does not have. Then build "
              "only in what that constraint forecloses. 'They execute badly' is "
              "not a structural constraint and will be rejected."},
    {"id": 4,
     "thesis": "The mechanics are all invented already. Nothing new needs to be "
               "designed; a loop proven in one domain simply has not been carried "
               "into the domain where it would matter most.",
     "operator": "analogy_transporter",
     "brief": "Take a mechanic that demonstrably works in one domain and carry it "
              "into a domain where nobody has applied it. State why the "
              "psychological driver still holds after the transfer. Most transfers "
              "fail; say why this one does not."},
    {"id": 5,
     "thesis": "The consensus is wrong. What everyone believes about this market "
               "is weakly supported, and the opportunity sits behind the belief.",
     "operator": "inversion_engine",
     "brief": "Take a belief the market treats as settled, check it against the "
              "evidence supplied, and build from the inversion only where the "
              "evidence fails to support the consensus. An inversion the evidence "
              "contradicts is just contrarianism and will be rejected."},
]

# Order matters: panel_size truncates this list, so whatever sits at the end is
# what gets dropped when the panel is cut for cost. In cycle 1 that silently
# removed graveyard_attacker, which then killed three more ideas once it was
# actually run. Anything cut must be reported, never dropped quietly.
PANEL = ["demand_skeptic", "incumbent_response", "economics_attacker",
         "distribution_attacker", "retention_attacker", "graveyard_attacker",
         "taste_attacker"]


@dataclass
class CycleConfig:
    islands: int = 6
    per_island: int = 6
    obviousness_kill_rate: float = 0.30
    panel_size: int = 6
    tournament_max_pairs: int = 90
    budget_usd: float = 6.0
    cost_ceiling: float = 50_000
    week_ceiling: float = 12

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class Orchestrator:
    def __init__(self, store: Store, backend, config: CycleConfig | None = None,
                 cycle_id: int | None = None):
        self.s = store
        self.b = backend
        self.cfg = config or CycleConfig()
        self.budget = Budget(limit_usd=self.cfg.budget_usd)
        self.pending: list[str] = []
        self.progress: list[dict[str, Any]] = []
        self.stalls = 0
        self.cycle_id = cycle_id or self.s.start_cycle(
            self.cfg.to_dict(), self.cfg.budget_usd)

    # -- ledgers ----------------------------------------------------------

    def note(self, stage: str, **kw) -> None:
        entry = {"stage": stage, **kw}
        self.progress.append(entry)
        self.s.update_cycle(self.cycle_id, progress_ledger=self.progress)

    def _judged(self, gate: str) -> set[int]:
        """Ideas that already carry a verdict for this gate.

        Gates are recorded once per idea. Without this a resumed cycle re-runs
        the deterministic screen every round, and because the obviousness
        threshold is recalibrated against whoever is left, each pass eats
        another slice of the population until nothing survives.
        """
        rows = self.s.db.execute(
            "SELECT DISTINCT idea_id FROM verdicts WHERE gate=?", (gate,))
        return {int(r["idea_id"]) for r in rows}

    def _collect(self, fn: Callable[[], Any], label: str) -> Any | None:
        """Run a model-dependent call, recording the prompt if it is not ready."""
        try:
            return fn()
        except PendingResponse as e:
            self.pending.append(e.task_id)
            return None

    # -- stage 1: generation ---------------------------------------------

    def stage_generate(self) -> int:
        # Track ingestion PER ISLAND. An all-or-nothing guard would drop any
        # island whose answer arrived after the first ingest, which is the
        # normal case when the islands are answered in parallel.
        already = {r["island"] for r in self.s.ideas(cycle_id=self.cycle_id)}
        sigs = self.s.signals()
        if not sigs:
            raise RuntimeError("no evidence in the store; grounding is the novelty engine")
        pains = [s for s in sigs if s["kind"] == "PAIN"]
        unlocks = [s for s in sigs if s["kind"] == "UNLOCK"]
        tombs = [s for s in sigs if s["kind"] == "TOMBSTONE"]

        ingested = 0
        for isl in ISLANDS[: self.cfg.islands]:
            # Each island sees a different evidence slice, which is the cheapest
            # real source of divergence between lineages.
            k = isl["id"]
            if k in already:
                continue
            slice_ = (unlocks + tombs +
                      pains[k::max(1, self.cfg.islands)] + pains[:6])
            sys_p, user_p = P.generation_prompt(
                thesis=isl["thesis"], operator=isl["operator"],
                operator_brief=isl["brief"], signals=slice_,
                n=self.cfg.per_island, seed=k * 17 + 3)
            out = self._collect(
                lambda: self.b.request(f"gen-island{k}", sys_p, user_p,
                                       tier="strong",
                                       meta={"island": k,
                                             "operator": isl["operator"]}),
                f"gen-island{k}")
            if out is None:
                continue
            ingested += self._ingest_generation(out, isl)

        self.note("generate", ingested=ingested, pending=len(self.pending))
        return ingested

    def _ingest_generation(self, out: Any, isl: dict) -> int:
        data = out.get("parsed") if isinstance(out, dict) else out
        if isinstance(data, dict):
            cands = data.get("candidates") or []
        elif isinstance(data, list):
            cands = data
        else:
            return 0
        n = 0
        for c in cands:
            if not isinstance(c, dict):
                continue
            c.setdefault("island", isl["id"])
            c.setdefault("operator", isl["operator"])
            g = IdeaGenome.from_dict(c)
            g.island = isl["id"]
            g.operator = isl["operator"]
            g.notes.update({k: c[k] for k in
                            ("why_now", "why_not_obvious", "probability")
                            if k in c})
            if not g.title:
                continue
            self.s.add_idea(g, self.cycle_id)
            n += 1
        return n

    # -- stage 2: deterministic screen (L0, L1, L2) ------------------------

    def stage_screen(self) -> dict[str, int]:
        done = self._judged("L0")
        rows = [r for r in self.s.ideas(status="alive", cycle_id=self.cycle_id)
                if r["id"] not in done]
        genomes = {r["id"]: IdeaGenome.from_dict(json.loads(r["genome"])) for r in rows}
        sig_by_id = {s["id"]: s for s in self.s.signals()}
        counts = {"seen": len(rows), "l0": 0, "l1": 0, "l2": 0, "alive": 0}
        if not rows:
            counts["alive"] = len(self.s.ideas(status="alive", cycle_id=self.cycle_id))
            self.note("screen", **counts, skipped=True)
            return counts

        # L0 — validity
        # Descriptors already occupied by surviving ideas OUTSIDE this batch.
        # Including the batch itself would make every idea collide with its own
        # row, which is already in the store by the time the screen runs.
        batch_ids = {r["id"] for r in rows}
        living: set[str] = {r["descriptor"] for r in self.s.ideas()
                            if r["status"] != "killed" and r["id"] not in batch_ids}
        for iid, g in list(genomes.items()):
            r = check_validity(g, self.cfg.cost_ceiling, living)
            self.s.add_verdict(iid, "L0", r.passed, detail=r.to_dict())
            if not r.passed:
                self.s.kill_idea(iid, "L0", "; ".join(r.reasons[:3]))
                genomes.pop(iid)
                counts["l0"] += 1
            else:
                living.add(g.descriptor)

        # L1 — obviousness, threshold calibrated to the designed kill rate
        gate = self._obviousness_gate()
        if genomes:
            gate.calibrate(list(genomes.values()), self.cfg.obviousness_kill_rate)
        for iid, g in list(genomes.items()):
            r = gate(g)
            self.s.add_verdict(iid, "L1", r.passed, score=r.detail["originality"],
                               detail=r.to_dict())
            if not r.passed:
                self.s.kill_idea(iid, "L1", "; ".join(r.reasons[:2]))
                genomes.pop(iid)
                counts["l1"] += 1

        # L2 — grounding
        for iid, g in list(genomes.items()):
            r = gates.check_grounding(g, sig_by_id)
            self.s.add_verdict(iid, "L2", r.passed, detail=r.to_dict())
            if not r.passed:
                self.s.kill_idea(iid, "L2", "; ".join(r.reasons[:2]))
                genomes.pop(iid)
                counts["l2"] += 1

        counts["alive"] = len(genomes)
        self.note("screen", **counts, threshold=gate.threshold)
        if counts["alive"] == 0:
            self.stalls += 1
        return counts

    def _obviousness_gate(self) -> gates.ObviousnessGate:
        priors = [s["title"] + " " + (s.get("body") or "")
                  for s in self.s.signals("PRIOR")]
        corpus = self.s.products()
        return gates.ObviousnessGate(priors or ["a habit tracker with streaks"],
                                     corpus)

    # -- stage 3: buildability --------------------------------------------

    def stage_build(self) -> dict[str, int]:
        done = self._judged("L3")
        rows = [r for r in self.s.ideas(status="alive", cycle_id=self.cycle_id)
                if r["id"] not in done]
        counts = {"seen": len(rows), "killed": 0, "priced": 0}
        for r in rows:
            idea = _brief(r)
            sys_p, user_p = P.build_prompt(idea)
            out = self._collect(
                lambda i=r["id"]: self.b.request(f"build-{i}", sys_p, user_p,
                                                 tier="strong",
                                                 meta={"idea_id": i}),
                f"build-{r['id']}")
            if out is None:
                continue
            plan = out.get("parsed") if isinstance(out, dict) else out
            if not isinstance(plan, dict):
                continue
            v = gates.check_buildability(plan, self.cfg.cost_ceiling,
                                         self.cfg.week_ceiling)
            self.s.add_verdict(r["id"], "L3", v.passed,
                               score=v.detail.get("buildability"),
                               detail=v.to_dict())
            if not v.passed:
                self.s.kill_idea(r["id"], "L3", "; ".join(v.reasons[:2]))
                counts["killed"] += 1
            else:
                counts["priced"] += 1
        self.note("build", **counts, pending=len(self.pending))
        return counts

    # -- stage 4: adversarial panel ---------------------------------------

    def stage_attack(self) -> dict[str, int]:
        dropped = PANEL[self.cfg.panel_size:]
        if dropped:
            self.note("attack", warning="attack surfaces not run",
                      dropped=dropped)
        done = self._judged("L4")
        rows = [r for r in self.s.ideas(status="alive", cycle_id=self.cycle_id)
                if r["id"] not in done]
        counts = {"seen": len(rows), "killed": 0, "survived": 0}
        for r in rows:
            idea = _brief(r)
            attacks, waiting = [], False
            for surface in PANEL[: self.cfg.panel_size]:
                sys_p, user_p = P.attack_prompt(idea, surface)
                out = self._collect(
                    lambda i=r["id"], s=surface: self.b.request(
                        f"attack-{i}-{s}", sys_p, user_p, tier="strong",
                        meta={"idea_id": i, "surface": s}),
                    f"attack-{r['id']}-{surface}")
                if out is None:
                    waiting = True
                    continue
                a = out.get("parsed") if isinstance(out, dict) else out
                if isinstance(a, dict):
                    a.setdefault("surface", surface)
                    attacks.append(a)
            if waiting or not attacks:
                continue
            v = gates.score_panel(attacks)
            self.s.add_verdict(r["id"], "L4", v.passed,
                               score=v.detail.get("survival"), detail=v.to_dict())
            if not v.passed:
                self.s.kill_idea(r["id"], "L4", "; ".join(v.reasons[:2]))
                counts["killed"] += 1
            else:
                counts["survived"] += 1
        self.note("attack", **counts, pending=len(self.pending))
        return counts

    # -- stage 5: tournament ----------------------------------------------

    def stage_rank(self) -> dict[str, Any]:
        rows = self.s.ideas(status="alive", cycle_id=self.cycle_id)
        ids = [r["id"] for r in rows]
        briefs = {r["id"]: P.render_for_judging(_brief(r)) for r in rows}
        result: dict[str, Any] = {"ideas": len(ids)}

        for head in ("novelty", "viability"):
            seen = {(c["a_id"], c["b_id"], bool(c["swapped"]))
                    for c in self.s.comparisons(head)}
            pairs = tournament.swiss_pairs(
                ids, max_pairs=self.cfg.tournament_max_pairs)
            for a, bb in pairs:
                for swapped in (False, True):
                    x, y = (bb, a) if swapped else (a, bb)
                    if (x, y, swapped) in seen:
                        continue
                    sys_p, user_p = P.judge_prompt(head, briefs[x], briefs[y])
                    out = self._collect(
                        lambda h=head, xx=x, yy=y, sw=swapped: self.b.request(
                            f"judge-{h}-{xx}-{yy}", sys_p, user_p, tier="strong",
                            meta={"head": h, "a": xx, "b": yy, "swapped": sw}),
                        f"judge-{head}-{x}-{y}")
                    if out is None:
                        continue
                    d = out.get("parsed") if isinstance(out, dict) else out
                    if not isinstance(d, dict) or d.get("winner") not in ("A", "B"):
                        continue
                    winner = x if d["winner"] == "A" else y
                    self.s.add_comparison(head, x, y, winner, swapped,
                                          str(d.get("reason", ""))[:300])
            result[head] = len(self.s.comparisons(head))
        self.note("rank", **result, pending=len(self.pending))
        return result

    # -- stage 6: scoring --------------------------------------------------

    def stage_score(self) -> list[dict[str, Any]]:
        rows = self.s.ideas(status="alive", cycle_id=self.cycle_id)
        ids = [r["id"] for r in rows]
        if not ids:
            return []

        ratings, lcbs = {}, {}
        for head in ("novelty", "viability"):
            comps = _tally(self.s.comparisons(head))
            ratings[head] = tournament.bradley_terry(ids, comps)
            lcbs[head] = tournament.bootstrap_lcb(ids, comps, reps=120)

        checks = self._checklist_scores()

        out = []
        for r in rows:
            v = {x["gate"]: x for x in self.s.verdicts(r["id"])}
            l1 = (v.get("L1", {}).get("detail") or {}).get("detail", {})
            l3 = (v.get("L3", {}).get("detail") or {}).get("detail", {})
            l4 = (v.get("L4", {}).get("detail") or {}).get("detail", {})

            originality = float(l1.get("originality", 0.5))
            build = float(l3.get("buildability", 0.5))
            econ = float(l3.get("unit_economics", 0.5))
            survival = float(l4.get("survival", 0.5))

            # Quality and distribution come from the judges' BINARY CHECKLIST,
            # not from the pairwise ratings.
            #
            # An earlier version fed the novelty tournament rating in as
            # "quality", which made the novelty head harmonic(originality,
            # judged-novelty) — novelty counted twice and quality never
            # measured at all. The checklist is independent of who won the
            # pair, and binary items are auditable and do not drift.
            ck = checks.get(r["id"], {})
            quality = ck.get("quality", 0.5)
            distribution = ck.get("distribution", 0.5)
            timing = scoring.timing_score(self._months_since_unlock(r["id"]))

            sc = scoring.assemble(originality, quality, build, econ,
                                  distribution, timing, survival)
            sc["elo_novelty"] = ratings["novelty"].get(r["id"])
            sc["elo_viability"] = ratings["viability"].get(r["id"])
            sc["lcb"] = min(lcbs["novelty"][r["id"]]["lcb"],
                            lcbs["viability"][r["id"]]["lcb"])
            sc["detail"] = {"l1": l1, "l3": l3, "checks": ck,
                            "lcb_novelty": lcbs["novelty"][r["id"]],
                            "lcb_viability": lcbs["viability"][r["id"]]}
            self.s.set_scores(r["id"], **sc)
            out.append({"idea_id": r["id"], "title": r["title"], **sc})

        out.sort(key=lambda x: x["founder_score"], reverse=True)
        self.note("score", scored=len(out))
        return out

    def _months_since_unlock(self, idea_id: int) -> float | None:
        """How long ago the cited capability actually crossed its threshold.

        This was previously read from the build plan, where it never appears, so
        every idea scored the same default and timing contributed nothing to the
        composite. The real answer is already in the store: the UNLOCK signal
        the idea cites carries the date the cost curve crossed.
        """
        row = self.s.idea(idea_id)
        if not row:
            return None
        try:
            genome = json.loads(row["genome"])
        except (ValueError, TypeError):
            return None
        ids = ((genome.get("unlock") or {}).get("signal_ids")) or []
        dates = []
        for sid in ids:
            sig = next((x for x in self.s.signals("UNLOCK") if x["id"] == sid), None)
            if sig and sig.get("dated_at"):
                dates.append(str(sig["dated_at"])[:10])
        if not dates:
            return None
        newest = max(dates)                       # the most recent crossing
        try:
            y, m, d = (int(x) for x in newest.split("-"))
        except ValueError:
            return None
        now = time.localtime()
        return (now.tm_year - y) * 12 + (now.tm_mon - m) + (now.tm_mday - d) / 30.0

    def _checklist_scores(self) -> dict[int, dict[str, Any]]:
        """Per-idea scores from the judges' yes/no checks.

        The checks each comparison asks of both entries:
          q1 names a specific population with a specific trigger moment
          q2 the enabling capability genuinely changed recently
          q3 something very close already ships          (a NO is good)
          q4 the distribution loop turns without ad spend
          q5 there is a reason to open it again in week two

        Every idea appears in several comparisons, so each check is averaged
        over its appearances. That averaging is also a free reliability signal:
        a check that flips between appearances of the same idea is a judge
        being inconsistent, not a property of the idea.
        """
        out: dict[int, dict[str, list[float]]] = {}
        prompts_dir = getattr(self.b, "prompts", None)
        responses_dir = getattr(self.b, "responses", None)
        if prompts_dir is None or responses_dir is None:
            return {}
        for pf in sorted(prompts_dir.glob("judge-*.json")):
            rf = responses_dir / pf.name
            if not rf.exists():
                continue
            try:
                meta = json.loads(pf.read_text()).get("meta", {})
                data = json.loads(rf.read_text()).get("parsed") or {}
            except (ValueError, OSError):
                continue
            checks = data.get("checks") or {}
            for slot, idea_id in (("A", meta.get("a")), ("B", meta.get("b"))):
                c = checks.get(slot)
                if not isinstance(c, dict) or idea_id is None:
                    continue
                d = out.setdefault(int(idea_id), {})
                for q in ("q1", "q2", "q3", "q4", "q5"):
                    if q in c:
                        d.setdefault(q, []).append(1.0 if c[q] else 0.0)

        scores: dict[int, dict[str, Any]] = {}
        for idea_id, d in out.items():
            def mean(q, invert=False):
                vals = d.get(q) or []
                if not vals:
                    return 0.5
                m = sum(vals) / len(vals)
                return 1.0 - m if invert else m

            def flip(q):
                vals = d.get(q) or []
                return len(set(vals)) > 1 if len(vals) > 1 else False

            q1, q2, q3n, q4, q5 = (mean("q1"), mean("q2"), mean("q3", invert=True),
                                   mean("q4"), mean("q5"))
            scores[idea_id] = {
                "quality": round((q1 + q2 + q3n + q5) / 4, 3),
                "distribution": round(q4, 3),
                "specific_audience": q1, "recent_unlock": q2,
                "not_already_shipping": q3n, "loop_turns": q4, "week_two_reason": q5,
                "n_appearances": len(d.get("q1") or []),
                "inconsistent_checks": [q for q in ("q1", "q2", "q3", "q4", "q5")
                                        if flip(q)],
            }
        return scores

    # -- stage 7: probe design --------------------------------------------

    def stage_probe(self, top_n: int = 3) -> dict[str, Any]:
        """Design one cheap real-world test for the top survivors.

        This is the only stage that touches ground truth, and it is the only
        stage that spends the founder's money, so nothing here executes. It
        writes a probe the human approves or ignores.
        """
        rows = self.s.ideas(status="alive", cycle_id=self.cycle_id)
        scored = []
        for r in rows:
            sc = self.s.scores(r["id"]) or {}
            scored.append((sc.get("founder_score") or 0, r, sc))
        scored.sort(key=lambda x: x[0], reverse=True)

        existing = {p["idea_id"] for p in self.s.probes()}
        made = 0
        for _, r, sc in scored[:top_n]:
            if r["id"] in existing:
                continue
            sys_p, user_p = P.probe_prompt(_brief(r), {
                k: sc.get(k) for k in
                ("novelty", "viability", "originality", "survival", "founder_score")})
            out = self._collect(
                lambda i=r["id"]: self.b.request(f"probe-{i}", sys_p, user_p,
                                                 tier="strong",
                                                 meta={"idea_id": i}),
                f"probe-{r['id']}")
            if out is None:
                continue
            d = out.get("parsed") if isinstance(out, dict) else out
            if not isinstance(d, dict):
                continue
            self.s.add_probe(r["id"], d.get("kind", "landing_page"),
                             d.get("hypothesis", ""), d.get("falsifier", ""),
                             float(d.get("budget_usd", 0) or 0))
            self.s.db.execute("UPDATE probes SET result=? WHERE idea_id=? AND result IS NULL",
                              (json.dumps(d), r["id"]))
            self.s.db.commit()
            made += 1
        self.note("probe", designed=made, pending=len(self.pending))
        return {"designed": made}

    # -- driver -----------------------------------------------------------

    def run(self, upto: str = "probe") -> dict[str, Any]:
        order = ["generate", "screen", "build", "attack", "rank", "score", "probe"]
        done: dict[str, Any] = {}
        try:
            for stage in order:
                done[stage] = getattr(self, f"stage_{stage}")()
                if self.pending:
                    done["halted"] = f"awaiting {len(self.pending)} responses at {stage}"
                    break
                if stage == upto:
                    break
        except BudgetExceeded as e:
            done["halted"] = str(e)
            self.s.update_cycle(self.cycle_id, halted_reason=str(e))

        alive = len(self.s.ideas(status="alive", cycle_id=self.cycle_id))
        self.s.update_cycle(self.cycle_id,
                            survived=alive,
                            generated=len(self.s.ideas(cycle_id=self.cycle_id)),
                            spent_usd=self.budget.spent_usd,
                            progress_ledger=self.progress)
        done["pending"] = list(self.pending)
        done["alive"] = alive
        # Stall counter: a stage that produced nothing new forces a replan
        # rather than another identical cycle.
        done["stalls"] = self.stalls
        return done


def _brief(row: dict) -> dict[str, Any]:
    g = json.loads(row["genome"])
    flat = {"id": row["id"], "title": g.get("title", "")}
    for k in ("unlock", "pain", "audience", "mechanic", "wedge", "moat",
              "model", "loop"):
        v = g.get(k)
        flat[k] = v.get("value") if isinstance(v, dict) else v
    flat["kill"] = g.get("kill", [])
    flat.update({k: v for k, v in (g.get("notes") or {}).items()
                 if k in ("why_now", "why_not_obvious")})
    return flat


def _tally(comparisons: list[dict]) -> list[tuple[int, int, int]]:
    counts: dict[tuple[int, int], int] = {}
    for c in comparisons:
        if c.get("winner") is None:
            continue
        w = c["winner"]
        l = c["b_id"] if w == c["a_id"] else c["a_id"]
        counts[(w, l)] = counts.get((w, l), 0) + 1
    return [(w, l, n) for (w, l), n in counts.items()]


def _norm_rating(ratings: dict[int, float], idea_id: int,
                 ids: list[int]) -> float:
    vals = [ratings.get(i, 1500.0) for i in ids]
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-6:
        return 0.5
    return round((ratings.get(idea_id, 1500.0) - lo) / (hi - lo), 3)
