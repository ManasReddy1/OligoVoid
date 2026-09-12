"""Idea genome, slot vocabularies, and the L0 validity rules.

The genome is the direct analogue of SiRNAModificationPattern in the OligoVoid
backend: a typed slot vector over controlled vocabularies, where slots 1-4 form
the behaviour descriptor used as the archive coordinate.

No third-party dependencies. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any

# --------------------------------------------------------------------------
# Provenance — every slot records where its value came from (finding F17/F36)
# --------------------------------------------------------------------------

EVIDENCE = "evidence"      # traceable to a harvested Signal with a live URL
INHERITED = "inherited"    # carried from a parent genome
MODEL = "model"            # invented by the generator, unsupported until cited

PROVENANCE = (EVIDENCE, INHERITED, MODEL)

# Slots that must be evidence-backed or the idea dies at L2.
LOAD_BEARING = ("unlock", "pain")

SLOTS = ("unlock", "pain", "audience", "mechanic",
         "wedge", "moat", "model", "loop", "kill")

DESCRIPTOR_SLOTS = ("unlock", "pain", "audience", "mechanic")


# --------------------------------------------------------------------------
# Controlled vocabularies
# --------------------------------------------------------------------------

MECHANICS = {
    "capture_and_answer": "point a camera or mic at something, get an answer back",
    "passive_tracking": "runs in the background and surfaces a pattern later",
    "streak_habit": "a daily act with visible continuity pressure",
    "voice_conversation": "a spoken back-and-forth as the primary interface",
    "scheduled_digest": "a recurring prepared briefing at a chosen moment",
    "async_social": "small group exchange that does not need to be simultaneous",
    "shared_ledger": "several people writing to one authoritative record",
    "guided_protocol": "a structured multi-session programme with checkpoints",
    "ambient_capture": "always-on collection the user rarely touches",
    "spaced_repetition": "scheduled resurfacing tuned to forgetting",
    "simulation_rehearsal": "practise a real encounter before it happens",
    "annotation_overlay": "a layer of notes on top of something external",
    "delegation_handoff": "hand a task off and receive a finished result",
    "marketplace_match": "match two sides of a transaction",
}

MOATS = {
    "accumulated_personal_corpus": "the user's own history becomes irreplaceable",
    "habit_lock": "embedded in a daily routine at a fixed trigger",
    "two_sided_network": "value rises with participants on both sides",
    "proprietary_taste": "curation quality that is hard to copy",
    "content_library": "an accumulating body of produced material",
    "social_graph": "the people, not the software, are the lock-in",
    "integration_depth": "wired into enough of the user's stack to hurt to leave",
    "switching_cost_of_history": "leaving means abandoning a long record",
}

BUSINESS_MODELS = {
    "subscription": "recurring fee, no free tier",
    "freemium_subscription": "useful free tier, paid upgrade",
    "consumable_credits": "pay per unit of work",
    "one_time_purchase": "buy once, own it",
    "hybrid_sub_credits": "subscription plus usage packs",
    "marketplace_take": "a cut of transactions",
}

DISTRIBUTION_LOOPS = {
    "shareable_artifact": "the output is worth posting, and it carries the source",
    "invite_for_function": "the product does not work until you add someone",
    "public_profile": "a durable public page that pulls search traffic",
    "referral_two_sided": "both inviter and invitee gain something",
    "content_seo": "generated pages that rank for long-tail intent",
    "community_embed": "lives inside an existing community's rituals",
    "gift_to_recipient": "one user buys, a second user receives and adopts",
    "professional_recommendation": "a practitioner prescribes it to clients",
}

# Business models that cannot carry a $10k-$50k consumer build.
DENIED_MODELS = {"ads"}

# Category patterns that are rejected outright at L0, never left to judgment.
DENY_PATTERNS = [
    (r"\b(diagnos(e|is|ing)|prescrib(e|ing)|treat(ment)? plan|medical advice)\b",
     "regulated: medical diagnosis or treatment"),
    (r"\b(lend(ing)?|loan|credit score|underwrit|insurance|mortgage)\b",
     "regulated: lending or insurance"),
    (r"\b(legal advice|represent(ation)? in court|tax filing)\b",
     "regulated: legal or tax practice"),
    (r"\b(custom hardware|proprietary device|we manufacture|our wearable|build a device)\b",
     "hardware-dependent build"),
    # Bare "token" is not a crypto signal: the first cycle killed seven sound
    # candidates because their evidence cited a "million-token context".
    (r"\b(cryptocurrency|crypto ?(wallet|exchange|trading|token|coin))\b|"
     r"\bweb3\b|\bNFTs?\b|\bblockchain\b|\btokenomics\b|"
     r"\b(governance|utility|security) token\b|\btoken sale\b",
     "regulated: crypto"),
]

BANNED_AUDIENCES = {
    "everyone", "everybody", "people", "users", "consumers", "anyone",
    "all users", "general public", "the public", "humans", "individuals",
    "professionals", "adults", "students",
}

# A kill condition is falsifiable only if it names something observable.
FALSIFIABLE_HINTS = re.compile(
    r"(\d|\bpercent\b|%|\bfewer\b|\bless than\b|\bmore than\b|\bunder\b|\bover\b|"
    r"\bbelow\b|\babove\b|\bat least\b|\bwithin\b|\bfails? to\b|\bno (one|body)\b|"
    r"\bcannot\b|\bdoes not\b|\bnone of\b)", re.I)


# --------------------------------------------------------------------------
# Slot
# --------------------------------------------------------------------------

@dataclass
class Slot:
    value: str
    provenance: str = MODEL
    signal_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value,
                "provenance": self.provenance,
                "signal_ids": list(self.signal_ids)}

    @classmethod
    def parse(cls, raw: Any) -> "Slot":
        if isinstance(raw, Slot):
            return raw
        if isinstance(raw, str):
            return cls(value=raw.strip())
        if isinstance(raw, dict):
            return cls(value=str(raw.get("value", "")).strip(),
                       provenance=raw.get("provenance", MODEL),
                       signal_ids=list(raw.get("signal_ids", []) or []))
        return cls(value="")


# --------------------------------------------------------------------------
# Genome
# --------------------------------------------------------------------------

@dataclass
class IdeaGenome:
    """One point in consumer-app design space."""

    title: str = ""
    unlock: Slot = field(default_factory=lambda: Slot(""))
    pain: Slot = field(default_factory=lambda: Slot(""))
    audience: Slot = field(default_factory=lambda: Slot(""))
    mechanic: Slot = field(default_factory=lambda: Slot(""))
    wedge: Slot = field(default_factory=lambda: Slot(""))
    moat: Slot = field(default_factory=lambda: Slot(""))
    model: Slot = field(default_factory=lambda: Slot(""))
    loop: Slot = field(default_factory=lambda: Slot(""))
    kill: list[str] = field(default_factory=list)

    # lineage / bookkeeping
    island: int = 0
    generation: int = 0
    operator: str = ""
    parent_ids: list[int] = field(default_factory=list)
    notes: dict[str, Any] = field(default_factory=dict)

    # ---- accessors -------------------------------------------------------

    def slot(self, name: str) -> Slot:
        return getattr(self, name)

    def slots(self) -> dict[str, Slot]:
        return {n: getattr(self, n) for n in SLOTS if n != "kill"}

    @property
    def descriptor(self) -> str:
        """Archive coordinate. Mirrors the categorical diversity scheme in F14."""
        parts = [_norm_key(getattr(self, n).value) for n in DESCRIPTOR_SLOTS]
        return "|".join(parts)

    @property
    def descriptor_hash(self) -> str:
        return hashlib.sha1(self.descriptor.encode()).hexdigest()[:12]

    def text(self) -> str:
        """Flat text used for similarity comparisons."""
        bits = [self.title] + [s.value for s in self.slots().values()]
        return " ".join(b for b in bits if b)

    def evidence_ids(self) -> list[int]:
        out: list[int] = []
        for s in self.slots().values():
            out.extend(s.signal_ids)
        return sorted(set(out))

    # ---- serialisation ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d = {"title": self.title,
             "kill": list(self.kill),
             "island": self.island,
             "generation": self.generation,
             "operator": self.operator,
             "parent_ids": list(self.parent_ids),
             "notes": dict(self.notes)}
        for n, s in self.slots().items():
            d[n] = s.to_dict()
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IdeaGenome":
        g = cls(title=str(d.get("title", "")).strip())
        for n in SLOTS:
            if n == "kill":
                continue
            setattr(g, n, Slot.parse(d.get(n)))
        kill = d.get("kill") or []
        if isinstance(kill, str):
            kill = [kill]
        g.kill = [str(k).strip() for k in kill if str(k).strip()]
        g.island = int(d.get("island", 0) or 0)
        g.generation = int(d.get("generation", 0) or 0)
        g.operator = str(d.get("operator", "") or "")
        g.parent_ids = list(d.get("parent_ids", []) or [])
        g.notes = dict(d.get("notes", {}) or {})
        return g


def _norm_key(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9_ ]+", " ", s)
    s = re.sub(r"[\s_]+", "_", s).strip("_")
    return s[:48]


# --------------------------------------------------------------------------
# L0 — validity. Deterministic, free, and it must kill roughly 40%.
# --------------------------------------------------------------------------

@dataclass
class GateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed,
                "reasons": list(self.reasons),
                "detail": dict(self.detail)}


def check_validity(g: IdeaGenome,
                   build_cost_ceiling: int = 50_000,
                   living_descriptors: set[str] | None = None) -> GateResult:
    """Gate L0. Pure code, no model call, no network."""
    reasons: list[str] = []

    # 1. every slot filled
    for name, slot in g.slots().items():
        if not slot.value or len(slot.value.strip()) < 3:
            reasons.append(f"slot '{name}' is empty")
    if not g.title.strip():
        reasons.append("no title")

    # 2. audience must name a real population
    aud = g.audience.value.strip().lower()
    if aud:
        if aud in BANNED_AUDIENCES:
            reasons.append(f"audience '{aud}' is generic")
        elif len(aud.split()) < 2:
            reasons.append(f"audience '{aud}' is a single word, too broad")
        elif any(aud == b or aud.startswith(b + " ") for b in BANNED_AUDIENCES):
            reasons.append(f"audience '{aud}' leads with a generic term")

    # 3. kill conditions present and falsifiable
    if len(g.kill) < 2:
        reasons.append("fewer than 2 kill conditions")
    else:
        unfalsifiable = [k for k in g.kill if not FALSIFIABLE_HINTS.search(k)]
        if len(unfalsifiable) > len(g.kill) // 2:
            reasons.append("kill conditions name nothing observable")

    # 4. vocabulary membership for the controlled slots
    if g.mechanic.value and _norm_key(g.mechanic.value) not in MECHANICS:
        reasons.append(f"mechanic '{g.mechanic.value}' outside vocabulary")
    if g.moat.value and _norm_key(g.moat.value) not in MOATS:
        reasons.append(f"moat '{g.moat.value}' outside vocabulary")
    if g.model.value:
        mk = _norm_key(g.model.value)
        if mk in DENIED_MODELS:
            reasons.append(f"business model '{mk}' cannot fund a solo consumer build")
        elif mk not in BUSINESS_MODELS:
            reasons.append(f"business model '{g.model.value}' outside vocabulary")
    if g.loop.value and _norm_key(g.loop.value) not in DISTRIBUTION_LOOPS:
        reasons.append(f"distribution loop '{g.loop.value}' outside vocabulary")

    # 5. denied categories, checked across the whole genome text
    blob = g.text().lower()
    for pattern, label in DENY_PATTERNS:
        if re.search(pattern, blob):
            reasons.append(f"denied category — {label}")
            break

    # 6. self-declared build cost
    est = g.notes.get("build_cost_usd")
    if isinstance(est, (int, float)) and est > build_cost_ceiling:
        reasons.append(f"self-estimated build cost ${int(est):,} over ceiling")

    # 7. archive collision
    if living_descriptors and g.descriptor in living_descriptors:
        reasons.append("descriptor duplicates a living archive elite")

    return GateResult(passed=not reasons, reasons=reasons,
                      detail={"descriptor": g.descriptor})
