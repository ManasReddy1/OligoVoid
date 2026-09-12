"""The oracle ladder. Cost per candidate rises strictly down the ladder and
every gate must kill; a gate that passes almost everything is decoration.

L0 validity        deterministic code, free          -> genome.check_validity
L1 obviousness     embeddings / lexical, ~free       -> here
L2 grounding       retrieval only, no generation     -> here
L3 buildability    one strong model call             -> here (scores its output)
L4 adversarial     5-7 clean-context attackers       -> here (scores its output)
L5 tournament      pairwise, batched                 -> tournament.py
"""

from __future__ import annotations

from typing import Any, Sequence

import scoring
from genome import GateResult, IdeaGenome, LOAD_BEARING
from similarity import Index, cosine, slot_distance

# --------------------------------------------------------------------------
# L1 — obviousness. The novelty measurement, and the system's sharpest tool.
# --------------------------------------------------------------------------

class ObviousnessGate:
    """Two distances, both external to the generating model.

    prior_distance  : how far from what any model would say, cold, unprompted
    corpus_distance : how far from what already ships

    originality is the MINIMUM of the two, deliberately: an idea must be far
    from both. Being novel against only one of them is not enough.
    """

    def __init__(self, prior_texts: Sequence[str], corpus: Sequence[dict],
                 threshold: float = 0.55):
        self.prior_texts = list(prior_texts)
        self.corpus = list(corpus)
        self.corpus_texts = [_product_text(p) for p in self.corpus]
        self.threshold = threshold
        self.index = Index(self.prior_texts + self.corpus_texts)

        self._prior_vecs = [self.index.vec(t) for t in self.prior_texts]
        self._corpus_vecs = [self.index.vec(t) for t in self.corpus_texts]

    def __call__(self, g: IdeaGenome) -> GateResult:
        v = self.index.vec(comparison_text(g))

        p_sim, p_i = _best(v, self._prior_vecs)
        c_sim, c_i = _best(v, self._corpus_vecs)

        # Slot-level distance to the nearest product, the Hamming analogue.
        slot_d = 1.0
        nearest_product = None
        if c_i >= 0:
            nearest_product = self.corpus[c_i]
            slot_d = slot_distance(
                {"audience": g.audience.value, "mechanic": g.mechanic.value},
                {"audience": nearest_product.get("audience", ""),
                 "mechanic": nearest_product.get("mechanic", "")})

        prior_distance = 1.0 - p_sim
        corpus_distance = 1.0 - c_sim
        originality = min(prior_distance, corpus_distance)

        reasons = []
        if originality < self.threshold:
            which = "a cold model would suggest this" \
                if prior_distance <= corpus_distance else "this already ships"
            reasons.append(f"originality {originality:.2f} below {self.threshold:.2f} — {which}")

        return GateResult(
            passed=not reasons, reasons=reasons,
            detail={"originality": round(originality, 3),
                    "prior_distance": round(prior_distance, 3),
                    "corpus_distance": round(corpus_distance, 3),
                    "slot_distance_to_nearest": round(slot_d, 3),
                    "nearest_prior": self.prior_texts[p_i][:160] if p_i >= 0 else None,
                    "nearest_product": (nearest_product or {}).get("name"),
                    "nearest_product_line": (nearest_product or {}).get("one_line", "")[:160]})


    def originality_of(self, g: IdeaGenome) -> float:
        return self(g).detail["originality"]

    def calibrate(self, sample: Sequence[IdeaGenome],
                  target_kill_rate: float = 0.30) -> float:
        """Set the threshold so the gate kills its designed share of a batch.

        The absolute scale of a lexical similarity depends entirely on corpus
        size and vocabulary, so a hand-picked constant is meaningless across
        runs. The design target is the invariant: this gate exists to kill
        roughly 30%, and a gate that kills nothing is decoration.
        """
        if not sample:
            return self.threshold
        vals = sorted(self.originality_of(g) for g in sample)
        k = max(0, min(len(vals) - 1, int(round(target_kill_rate * len(vals))) - 1))
        self.threshold = round(vals[k] + 1e-4, 4) if k >= 0 else self.threshold
        return self.threshold


def _best(v: dict[str, float], vecs: Sequence[dict[str, float]]) -> tuple[float, int]:
    best, bi = 0.0, -1
    for i, w in enumerate(vecs):
        s = cosine(v, w)
        if s > best:
            best, bi = s, i
    return best, bi


def _product_text(p: dict) -> str:
    return " ".join(str(p.get(k, "")) for k in
                    ("name", "one_line", "audience", "mechanic"))


def comparison_text(g: IdeaGenome) -> str:
    """What the idea actually *is*, for similarity purposes.

    Deliberately excludes moat, business model and distribution loop. Those come
    from small controlled vocabularies, so including them makes every idea look
    alike and buries the signal that two ideas are genuinely the same product.
    """
    return " ".join(x for x in (g.title, g.pain.value, g.audience.value,
                                g.mechanic.value, g.wedge.value) if x)


# --------------------------------------------------------------------------
# L2 — grounding. Retrieval only; no generation, so it cannot hallucinate.
# --------------------------------------------------------------------------

def check_grounding(g: IdeaGenome, signals_by_id: dict[int, dict]) -> GateResult:
    """Load-bearing slots must resolve to a real signal with a live URL.

    Slots that fail are stripped rather than trusted. The idea dies only if a
    load-bearing slot is left unsupported; strategy slots may be model-authored.
    """
    reasons, stripped, cited = [], [], []

    for name, slot in g.slots().items():
        ok_ids = []
        for sid in slot.signal_ids:
            sig = signals_by_id.get(sid)
            if sig and sig.get("source_url"):
                ok_ids.append(sid)
        if slot.signal_ids and not ok_ids:
            stripped.append(name)
            slot.signal_ids = []
            slot.provenance = "model"
        elif ok_ids:
            slot.signal_ids = ok_ids
            slot.provenance = "evidence"
            cited.extend(ok_ids)

    for name in LOAD_BEARING:
        slot = g.slot(name)
        if slot.provenance != "evidence" or not slot.signal_ids:
            reasons.append(f"load-bearing slot '{name}' has no live citation")

    return GateResult(passed=not reasons, reasons=reasons,
                      detail={"stripped": stripped,
                              "citations": sorted(set(cited)),
                              "citation_count": len(set(cited))})


# --------------------------------------------------------------------------
# L3 — buildability. Scores a model-produced build plan; two hard kills.
# --------------------------------------------------------------------------

REQUIRED_BUILD_FIELDS = ("build_cost_usd", "weeks_to_v1",
                         "inference_cost_user_month", "price_month",
                         "expected_conversion")


def check_buildability(plan: dict[str, Any],
                       cost_ceiling: float = 50_000,
                       week_ceiling: float = 12) -> GateResult:
    missing = [f for f in REQUIRED_BUILD_FIELDS if plan.get(f) is None]
    if missing:
        return GateResult(False, [f"build plan missing {', '.join(missing)}"], {})

    cost = float(plan["build_cost_usd"])
    weeks = float(plan["weeks_to_v1"])
    infer = float(plan["inference_cost_user_month"])
    price = float(plan["price_month"])
    conv = float(plan["expected_conversion"])

    reasons = []
    if cost > cost_ceiling:
        reasons.append(f"build cost ${cost:,.0f} over the ${cost_ceiling:,.0f} ceiling")
    if weeks > week_ceiling:
        reasons.append(f"{weeks:.0f} weeks to v1, over the {week_ceiling:.0f}-week ceiling")

    econ, econ_detail = scoring.unit_economics_score(price, conv, infer)
    if econ <= 0.0:
        reasons.append(f"gross margin {econ_detail['margin_ratio']:.2f} — "
                       f"an automatic kill, no enthusiasm elsewhere overrides it")

    build = scoring.buildability_score(cost, weeks, cost_ceiling, week_ceiling)

    return GateResult(passed=not reasons, reasons=reasons,
                      detail={"buildability": build,
                              "unit_economics": econ,
                              **econ_detail,
                              "build_cost_usd": cost,
                              "weeks_to_v1": weeks,
                              "inference_cost_user_month": infer,
                              "price_month": price,
                              "expected_conversion": conv,
                              "stack": plan.get("stack", ""),
                              "milestones": plan.get("milestones", [])})


# --------------------------------------------------------------------------
# L4 — adversarial panel. Any single unanswerable attack is a hard kill.
# --------------------------------------------------------------------------

def score_panel(attacks: Sequence[dict[str, Any]]) -> GateResult:
    """attacks: [{surface, verdict, argument, defence}] where verdict is one of
    'survived', 'wounded', 'fatal', 'abstain'. An abstention is not a survival."""
    if not attacks:
        return GateResult(False, ["no attacks recorded"], {"survival": 0.0})

    counted = [a for a in attacks if a.get("verdict") != "abstain"]
    fatal = [a for a in attacks if a.get("verdict") == "fatal"]
    survived = [a for a in counted if a.get("verdict") == "survived"]
    wounded = [a for a in counted if a.get("verdict") == "wounded"]

    survival = (len(survived) + 0.5 * len(wounded)) / max(1, len(counted))

    reasons = []
    if fatal:
        surfaces = ", ".join(a.get("surface", "?") for a in fatal)
        reasons.append(f"unanswerable attack on {surfaces} — hard kill")

    return GateResult(passed=not reasons, reasons=reasons,
                      detail={"survival": round(survival, 3),
                              "attacks": list(attacks),
                              "n_counted": len(counted),
                              "n_abstain": len(attacks) - len(counted),
                              "fatal_surfaces": [a.get("surface") for a in fatal]})
