"""Pairwise ranking. Bradley-Terry by minorisation-maximisation, plus a
bootstrap lower confidence bound.

Absolute 1-10 scoring from a model judge is unstable, and the instability is
worst on subjective dimensions, which is where we live (finding F19). Ranking
by the lower confidence bound stops an under-compared idea topping the board.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any, Sequence


def bradley_terry(items: Sequence[int],
                  comparisons: Sequence[tuple[int, int, int]],
                  iters: int = 200, prior: float = 0.5) -> dict[int, float]:
    """comparisons: (winner_id, loser_id, count). Returns Elo-scaled ratings.

    `prior` adds a symmetric pseudo-comparison between every pair, which keeps
    a lightly-compared item from running off to infinity. Without it the
    bootstrap interval on a sparse item is meaningless.
    """
    idx = {i: k for k, i in enumerate(items)}
    n = len(items)
    if n == 0:
        return {}
    p = [1.0] * n
    wins = [0.0] * n
    pair = defaultdict(float)
    for w, l, c in comparisons:
        if w not in idx or l not in idx:
            continue
        wins[idx[w]] += c
        pair[(idx[w], idx[l])] += c
        pair[(idx[l], idx[w])] += 0.0
    games = defaultdict(float)
    for a in range(n):
        for b in range(n):
            if a == b:
                continue
            games[(a, b)] = pair.get((a, b), 0.0) + pair.get((b, a), 0.0) + 2 * prior
    if prior:
        for a in range(n):
            wins[a] += prior * (n - 1)

    for _ in range(iters):
        new = [0.0] * n
        for a in range(n):
            denom = 0.0
            for b in range(n):
                if a == b:
                    continue
                g = games.get((a, b), 0.0)
                if g:
                    denom += g / (p[a] + p[b])
            new[a] = (wins[a] / denom) if denom > 0 else p[a]
        total = sum(new) or 1.0
        p = [max(1e-9, x * n / total) for x in new]

    return {i: round(400 * math.log10(max(1e-6, p[idx[i]])) + 1500, 1) for i in items}


def bootstrap_lcb(items: Sequence[int],
                  comparisons: Sequence[tuple[int, int, int]],
                  reps: int = 200, z: float = 1.0,
                  seed: int = 7) -> dict[int, dict[str, float]]:
    """Resample comparisons to get a rating interval per item."""
    rng = random.Random(seed)
    flat: list[tuple[int, int]] = []
    for w, l, c in comparisons:
        flat.extend([(w, l)] * int(c))
    if not flat:
        return {i: {"rating": 1500.0, "lcb": 1500.0, "sd": 0.0} for i in items}

    samples: dict[int, list[float]] = {i: [] for i in items}
    for _ in range(reps):
        draw = [flat[rng.randrange(len(flat))] for _ in range(len(flat))]
        counts: dict[tuple[int, int], int] = defaultdict(int)
        for w, l in draw:
            counts[(w, l)] += 1
        r = bradley_terry(items, [(w, l, c) for (w, l), c in counts.items()], iters=60)
        for i in items:
            samples[i].append(r.get(i, 1500.0))

    out = {}
    for i in items:
        xs = samples[i]
        mean = sum(xs) / len(xs)
        var = sum((x - mean) ** 2 for x in xs) / max(1, len(xs) - 1)
        sd = math.sqrt(var)
        out[i] = {"rating": round(mean, 1), "sd": round(sd, 1),
                  "lcb": round(mean - z * sd, 1)}
    return out


def swiss_pairs(items: Sequence[int], ratings: dict[int, float] | None = None,
                rounds: int = 3, seed: int = 11,
                max_pairs: int = 120) -> list[tuple[int, int]]:
    """Pairings for the tournament.

    Small fields get a full round robin, which removes pairing luck entirely.
    Larger fields fall back to Swiss rounds with a rotation offset so later
    rounds produce genuinely new pairs. The caller judges each pair twice with
    the order swapped; that is not this function's job.
    """
    items = list(items)
    n = len(items)
    if n < 2:
        return []
    if n * (n - 1) // 2 <= max_pairs:
        return [(items[i], items[j]) for i in range(n) for j in range(i + 1, n)]

    rng = random.Random(seed)
    pairs: list[tuple[int, int]] = []
    seen: set[frozenset[int]] = set()
    order = list(items)
    rng.shuffle(order)
    for r in range(rounds):
        if ratings and r > 0:
            order.sort(key=lambda i: ratings.get(i, 1500.0), reverse=True)
        offset = 1 + r                      # rotate who meets whom
        for i in range(0, n - offset, 2):
            a, b = order[i], order[i + offset]
            key = frozenset((a, b))
            if a == b or key in seen:
                continue
            seen.add(key)
            pairs.append((a, b))
            if len(pairs) >= max_pairs:
                return pairs
    return pairs
