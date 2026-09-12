"""Prompt construction. Every generation call wears the same four wrappers.

The wrappers are not style. Each is a measured intervention:

  verbalized sampling  ask for a distribution, not a sample      2-3x diversity
  ordinary persona     a mundane voice, never a visionary one    +13% unique combos
  reason first         think about the evidence before emitting  fixation slope -35%
  isolation            no visibility of any other generator      highest diversity

Implemented once, here, so no operator can forget one.
"""

from __future__ import annotations

import json
import random
from typing import Any, Sequence

from genome import (BUSINESS_MODELS, DISTRIBUTION_LOOPS, MECHANICS, MOATS)

ORDINARY_PERSONAS = [
    "a night-shift hospital porter who fixes things for their family",
    "a primary school teaching assistant who is good with spreadsheets",
    "a self-employed plumber who reads a lot",
    "a supermarket depot scheduler",
    "a retired postal worker who volunteers at a library",
    "a part-time dental receptionist doing an evening course",
    "a warehouse forklift driver who tinkers with electronics",
    "a home carer for an elderly relative",
    "a bus driver who runs a small allotment group",
    "an office cleaner studying for an accountancy qualification",
]

SYSTEM = """You are a working member of a research team that maps which consumer \
software has never been built, and why the unbuilt parts might now be possible.

You are not a visionary and you are not pitching. You are a careful person \
looking at evidence and noticing what it implies. Plain language. No hype words, \
no "revolutionary", no "game-changing", no "imagine a world".

Absolute rules:
- Every claim about a human problem must point at a supplied evidence id. If no \
evidence supports a claim, do not make the claim.
- Name a specific population. Never "users", "people", "everyone", "consumers".
- Controlled vocabularies are closed sets. Use the exact keys given.
- Output valid JSON only, inside a single ```json fence. No prose outside it."""


def vocab_block() -> str:
    def fmt(d: dict[str, str]) -> str:
        return "\n".join(f"  {k}: {v}" for k, v in d.items())
    return (f"MECHANIC (pick one key):\n{fmt(MECHANICS)}\n\n"
            f"MOAT (pick one key):\n{fmt(MOATS)}\n\n"
            f"MODEL (pick one key):\n{fmt(BUSINESS_MODELS)}\n\n"
            f"LOOP (pick one key):\n{fmt(DISTRIBUTION_LOOPS)}")


def evidence_block(signals: Sequence[dict], limit: int = 48) -> str:
    """Render evidence for a prompt, with every kind guaranteed a share.

    This was a flat truncation of the caller's list. In cycle 1 the caller
    passed unlocks, then tombstones, then pains; 9 unlocks plus 31 tombstones
    filled the limit exactly, so all 49 harvested pains were cut off and no
    generator ever saw one. Every idea in that cycle cited tombstones for its
    problem slot, because a tombstone was the only evidence of a problem it had.

    Round-robin across kinds instead, so a long list of one kind can never
    crowd out another.
    """
    from collections import OrderedDict
    by_kind: "OrderedDict[str, list[dict]]" = OrderedDict()
    for sig in signals:
        by_kind.setdefault(sig.get("kind", "?"), []).append(sig)

    picked: list[dict] = []
    idx = 0
    while len(picked) < limit and any(idx < len(v) for v in by_kind.values()):
        for group in by_kind.values():
            if idx < len(group) and len(picked) < limit:
                picked.append(group[idx])
        idx += 1

    lines = []
    for s in picked:
        p = s.get("payload") or {}
        bits = [f"[{s['id']}] {s['kind']}"]
        if s["kind"] == "PAIN":
            bits.append(f"who={p.get('who', '?')}")
            bits.append(f"breaks={p.get('what_breaks', s.get('title', ''))}")
            if p.get("quote"):
                bits.append(f'quote="{p["quote"][:140]}"')
            if p.get("workaround"):
                bits.append(f"workaround={p['workaround'][:110]}")
        elif s["kind"] == "UNLOCK":
            bits.append(f"{s.get('title', '')}")
            bits.append(f"was={p.get('old_cost', '?')} now={p.get('new_cost', '?')}")
            bits.append(f"crossed={s.get('dated_at', '?')}")
        elif s["kind"] == "TOMBSTONE":
            bits.append(f"{s.get('title', '')} died={p.get('died', '?')}")
            bits.append(f"cause={p.get('stated_cause', '')[:140]}")
        else:
            bits.append(s.get("title", ""))
        lines.append(" | ".join(str(b) for b in bits))
    return "\n".join(lines)


def evidence_kinds(signals: Sequence[dict], limit: int = 48) -> dict[str, int]:
    """What the rendered block actually contains, for the caller to check."""
    from collections import Counter
    block = evidence_block(signals, limit)
    return dict(Counter(line.split("]")[-1].split("|")[0].strip()
                        for line in block.splitlines() if "]" in line))


GENOME_SCHEMA = {
    "type": "array",
    "items": {
        "title": "short concrete name, not a slogan",
        "probability": "0.0-1.0, your honest odds this is the strongest of the set",
        "unlock": {"value": "which capability change makes this possible now",
                   "signal_ids": "[ids of UNLOCK evidence]"},
        "pain": {"value": "the evidenced problem in one sentence",
                 "signal_ids": "[ids of PAIN evidence]"},
        "audience": {"value": "a named specific population"},
        "mechanic": {"value": "exact key from the MECHANIC vocabulary"},
        "wedge": {"value": "the narrowest possible first use case"},
        "moat": {"value": "exact key from the MOAT vocabulary"},
        "model": {"value": "exact key from the MODEL vocabulary"},
        "loop": {"value": "exact key from the LOOP vocabulary"},
        "kill": ["2-4 conditions that would prove this wrong, each naming a "
                 "number or an observable outcome"],
        "why_now": "one sentence tying the unlock to the pain",
        "why_not_obvious": "one sentence on why this is not the first thing "
                           "anyone would suggest for this audience",
    },
}


def generation_prompt(*, thesis: str, operator: str, operator_brief: str,
                      signals: Sequence[dict], n: int = 6,
                      seed: int = 0) -> tuple[str, str]:
    rng = random.Random(seed)
    persona = rng.choice(ORDINARY_PERSONAS)

    user = f"""ISLAND THESIS (argue from inside this belief, do not hedge it):
{thesis}

YOUR METHOD — {operator}:
{operator_brief}

WHO YOU ARE: {persona}. Write like that person thinks: concrete, unshowy,
grounded in how life actually works.

EVIDENCE AVAILABLE (cite ids; anything not here you may not claim):
{evidence_block(signals)}

{vocab_block()}

CONSTRAINTS THAT KILL AN IDEA OUTRIGHT:
- buildable by one person for under $50,000 and under 12 weeks
- consumer only, never business software
- no medical diagnosis, lending, insurance, legal advice, crypto, custom hardware
- must work at roughly 3% paid conversion with blended model cost under
  $0.30 per active user per month, or be free to run on-device
- must have a distribution loop that works with zero advertising budget,
  because cost per paying user runs $20-$80 and revenue per payer is $8-$24

DO THIS IN ORDER:
1. First, in a "reasoning" string, work through the evidence out loud. Which
   pains have a manual workaround, which unlock actually dissolves the reason
   nobody built this, and which populations are specific enough to reach. Do
   not name any product idea yet.
2. Then produce EXACTLY {n} candidates, each with an honest `probability` that
   it is the strongest of your set. Spread them: they must differ in audience
   and mechanic, not be one idea in {n} costumes.

Return one JSON object: {{"reasoning": "...", "candidates": [ ... ]}}
where each candidate follows:
{json.dumps(GENOME_SCHEMA["items"], indent=2)}"""
    return SYSTEM, user


BUILD_SYSTEM = """You are a pragmatic solo developer who has shipped consumer \
apps and been burned by inference bills. You cost things honestly and you have \
no stake in whether this idea is good. Output JSON only."""


def build_prompt(idea: dict) -> tuple[str, str]:
    user = f"""Cost this consumer app idea as a real build.

IDEA
{json.dumps(idea, indent=2)}

2026 facts you must use:
- Frontier text inference is about $0.10 per million input tokens and $0.40 out.
- Apple's on-device and Private Cloud Compute models cost $0 in cloud API fees
  for Small Business Program members under 2M lifetime downloads.
- Real-time voice runs $0.005 to $0.018 per minute on cheap stacks and up to
  $0.091 on flagship speech-to-speech. Model choice is the business model.
- Median consumer subscription price is about $10 monthly, $35 yearly.
- Typical paid conversion for a freemium consumer app is 2-4%.

Return JSON:
{{
  "stack": "concrete: platform, language, model choice, backend, store",
  "milestones": ["3-6 items, each a shippable week or two of work"],
  "build_cost_usd": <number: real cost to a solo builder using AI assistance>,
  "weeks_to_v1": <number>,
  "inference_cost_user_month": <number: blended cost per ACTIVE user, not per payer>,
  "price_month": <number>,
  "expected_conversion": <number 0-1>,
  "riskiest_technical_assumption": "one sentence",
  "cheapest_way_to_test_that_assumption": "one sentence"
}}

Be honest. If this needs continuous voice or video generation, say what that
actually costs per active user. An idea that cannot clear its own inference bill
should show that in the numbers, not be flattered."""
    return BUILD_SYSTEM, user


ATTACK_SURFACES = {
    "demand_skeptic":
        "Nobody actually wants this. The pain is stated, not felt. People say "
        "they want it and do not change behaviour. Attack the evidence itself.",
    "incumbent_response":
        "The category leader ships this as a feature within one quarter and the "
        "product evaporates. Name the incumbent and the feature.",
    "economics_attacker":
        "The margin or the acquisition cost never works. Use the real numbers: "
        "iOS cost per install $5.84, cost per paying user $20-$80, median "
        "revenue per payer $8-$24 monthly.",
    "distribution_attacker":
        "There is no loop. Growth requires paid acquisition this founder cannot "
        "afford. Attack the specific claimed loop and show where it stalls.",
    "retention_attacker":
        "It is a one-shot novelty. AI apps retain 21.1% at twelve months against "
        "30.7% for non-AI, and low retainers hold 1.4%. The first monthly "
        "renewal is the whole battle. Show why nobody comes back in week two.",
    "graveyard_attacker":
        "This already died. Find the closest dead product and argue the cause of "
        "death has not been dissolved.",
    "taste_attacker":
        "Nobody would show this to a friend. It is worthy, dull, or slightly "
        "embarrassing to be seen using. Attack how it feels, not what it does.",
}

ATTACK_SYSTEM = """You are one member of a red team. You have been given ONE \
attack surface and you may not stray from it. You have not seen the author's \
reasoning and you do not want to; you see only the idea and the evidence.

Your job is to kill the idea on your surface. A weak attack wastes everyone's \
time. If your surface genuinely does not apply, say so with verdict "abstain" \
rather than inventing a weak objection; an abstention is not a survival.

Output JSON only."""


def attack_prompt(idea: dict, surface: str, evidence: str = "") -> tuple[str, str]:
    ev = ("RELEVANT EVIDENCE\n" + evidence) if evidence else ""
    user = f"""YOUR SURFACE — {surface}:
{ATTACK_SURFACES[surface]}

IDEA
{json.dumps(idea, indent=2)}

{ev}

Return JSON:
{{
  "surface": "{surface}",
  "attack": "your strongest specific argument, 2-4 sentences, concrete",
  "strongest_defence": "the best answer the author could give",
  "verdict": "fatal" | "wounded" | "survived" | "abstain",
  "verdict_reason": "one sentence"
}}

Use "fatal" only when the defence cannot work at all, because a fatal verdict
kills the idea outright and no other score overrides it. Use "wounded" when the
idea survives but is materially weaker. Use "survived" when your surface is
genuinely well answered."""
    return ATTACK_SYSTEM, user


JUDGE_SYSTEM = """You compare two consumer app ideas on ONE dimension at a time. \
You are not choosing what you would build; you are judging the dimension asked \
for. Length is not quality: the two entries are rendered in an identical \
template and any difference in wording length is an artefact. Output JSON only."""

HEAD_CRITERIA = {
    "novelty":
        "Which is less obvious? Score against two things: would a language model "
        "asked cold for consumer app ideas have produced it, and does something "
        "close already ship. An idea that recombines two known things in a way "
        "nobody has tried beats an idea that is merely unusual.",
    "viability":
        "Which is more likely to reach $10,000 monthly revenue within two years "
        "on a budget under $50,000? Weigh the margin at realistic conversion, "
        "whether the distribution loop actually turns, and whether anyone comes "
        "back for the second month.",
}


def judge_prompt(head: str, a: dict, b: dict) -> tuple[str, str]:
    user = f"""DIMENSION — {head}:
{HEAD_CRITERIA[head]}

Answer these checks for EACH entry first, as yes or no:
  q1 names a specific population with a specific trigger moment
  q2 the enabling capability genuinely changed recently
  q3 something very close already ships
  q4 the distribution loop turns without advertising spend
  q5 there is a reason to open it again in week two

ENTRY A
{json.dumps(a, indent=2)}

ENTRY B
{json.dumps(b, indent=2)}

Return JSON:
{{
  "checks": {{"A": {{"q1": true, "q2": true, "q3": false, "q4": true, "q5": true}},
              "B": {{"q1": true, "q2": true, "q3": false, "q4": true, "q5": true}}}},
  "winner": "A" | "B",
  "margin": "clear" | "narrow",
  "reason": "one sentence naming the deciding difference"
}}"""
    return JUDGE_SYSTEM, user


def render_for_judging(idea: dict) -> dict:
    """Fixed-length template. Verbosity bias runs 15-30 points in frontier
    judges, so both entries are cut to the same shape before comparison."""
    def cut(s: Any, n: int) -> str:
        s = str(s or "").strip().replace("\n", " ")
        return s[:n]
    return {"title": cut(idea.get("title"), 70),
            "for_whom": cut(idea.get("audience"), 90),
            "problem": cut(idea.get("pain"), 160),
            "mechanic": cut(idea.get("mechanic"), 40),
            "wedge": cut(idea.get("wedge"), 140),
            "why_now": cut(idea.get("why_now"), 160),
            "money": cut(idea.get("model"), 40),
            "growth": cut(idea.get("loop"), 40),
            "price_month": idea.get("price_month"),
            "build_cost_usd": idea.get("build_cost_usd")}


PROBE_SYSTEM = """You design the cheapest experiment that would settle whether an \
idea is worth building. You are not a marketer. You care about one thing: what is \
the least money and least time that would produce a number capable of changing the \
founder's mind. Output JSON only."""


def probe_prompt(idea: dict, scores: dict) -> tuple[str, str]:
    user = f"""Design ONE real-world probe for this idea.

IDEA
{json.dumps(idea, indent=2)}

WHERE IT STANDS
{json.dumps(scores, indent=2)}

Available probe kinds and their realistic costs:
- landing_page: a page plus $50-$150 of paid traffic. Measures whether anyone
  clicks and leaves an email.
- ad_ab: $50 split across two positioning messages. Measures which message pulls.
- community_post: free. A post in the exact forum where the affected population
  already gathers. Measures whether people reply saying they need this.
- concierge: free. Deliver the outcome by hand to five people for two weeks.
  Measures whether they come back.
- fake_door: free. A control for a feature that does not exist yet, inside
  something you already have. Measures intent.

Pick the ONE that would most change your mind per dollar, given what is already
uncertain about this specific idea. Do not default to a landing page.

Return JSON:
{{
  "kind": "<one of the five>",
  "hypothesis": "the specific belief being tested, stated so it could be false",
  "falsifier": "the number or observation that would kill the idea, with a threshold",
  "budget_usd": <number>,
  "days": <number>,
  "exactly_what_to_do": ["3-6 concrete steps a person could follow on a Saturday"],
  "what_it_cannot_tell_you": "the thing this probe will NOT settle, stated plainly"
}}"""
    return PROBE_SYSTEM, user
