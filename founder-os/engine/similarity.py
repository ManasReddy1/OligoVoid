"""Lexical similarity, used for the originality distances in gate L1.

This is deliberately dependency-free: an IDF-weighted token overlap plus a
slot-level exact-match distance, which is the direct analogue of OligoVoid's
Hamming-distance-to-nearest-known-pattern.

It is a lexical proxy, not a semantic embedding. It over-rewards ideas that
say the same thing in different words, so the threshold is set conservatively
and the gate reports both distances separately for audit. Swapping in a real
embedding model later is a one-function change: replace `vec()`.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, Sequence

STOP = set("""
a an the and or but if then than that this these those is are was were be been being
of in on at to for with from by as into over under about across after before during
it its it's their there here we you your our they them he she his her i me my
app apps use uses used using user users make makes making get gets getting
one two three new best top good great really very just more most much many
can could would should will shall may might do does did done have has had
who what when where why how which whom
""".split())

TOKEN = re.compile(r"[a-z][a-z0-9'\-]+")

# Light suffix stripping so "counter", "counting" and "counts" collide. This is
# crude on purpose: a real stemmer is a dependency, and the failure mode we care
# about is an obvious idea slipping through because it used a different verb
# form from the product it duplicates.
_SUFFIXES = ("ational", "ization", "iveness", "fulness", "ousness", "ation",
             "ement", "ingly", "edly", "ings", "ing", "ers", "er", "est",
             "ed", "ly", "ies", "es", "s")


def stem(t: str) -> str:
    for suf in _SUFFIXES:
        if len(t) - len(suf) >= 4 and t.endswith(suf):
            base = t[: -len(suf)]
            if suf == "ies":
                return base + "y"
            if base.endswith(("ss", "us")):
                return t
            # collapse a doubled final consonant: "logging" -> "log"
            if len(base) > 3 and base[-1] == base[-2] and base[-1] not in "aeiou":
                base = base[:-1]
            return base
    return t


def tokens(text: str) -> list[str]:
    out = []
    for t in TOKEN.findall((text or "").lower()):
        t = t.strip("'-")
        if len(t) > 2 and t not in STOP:
            st = stem(t)
            if len(st) > 2 and st not in STOP:
                out.append(st)
    return out


class Index:
    """Holds the IDF weights for a reference corpus."""

    def __init__(self, documents: Sequence[str]):
        self.n = max(1, len(documents))
        df: Counter[str] = Counter()
        self.docs: list[Counter[str]] = []
        for d in documents:
            tf = Counter(tokens(d))
            self.docs.append(tf)
            df.update(tf.keys())
        self.df = df

    def idf(self, term: str) -> float:
        return math.log((self.n + 1) / (self.df.get(term, 0) + 1)) + 1.0

    def vec(self, text: str) -> dict[str, float]:
        tf = Counter(tokens(text))
        if not tf:
            return {}
        v = {t: (1 + math.log(c)) * self.idf(t) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(w * b.get(t, 0.0) for t, w in a.items())


def max_similarity(index: Index, text: str,
                   corpus: Sequence[str]) -> tuple[float, int]:
    """Highest cosine against any corpus document. Returns (score, index)."""
    v = index.vec(text)
    best, best_i = 0.0, -1
    for i, c in enumerate(corpus):
        s = cosine(v, index.vec(c))
        if s > best:
            best, best_i = s, i
    return best, best_i


def slot_distance(a_slots: dict[str, str], b_slots: dict[str, str]) -> float:
    """Fraction of slots whose normalised values differ. The Hamming analogue."""
    keys = set(a_slots) | set(b_slots)
    if not keys:
        return 1.0
    diff = 0
    for k in keys:
        av = _norm(a_slots.get(k, ""))
        bv = _norm(b_slots.get(k, ""))
        if av != bv:
            diff += 1
    return diff / len(keys)


def _norm(s: str) -> str:
    return " ".join(sorted(tokens(s)))[:200]
