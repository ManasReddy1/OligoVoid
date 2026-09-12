"""Diversity monitoring. An invariant, not a nice-to-have.

Optimising against any scorer collapses output diversity, and collapsed
diversity destroys the whole point of a search. So the metrics that would show
collapse are computed every cycle and reported next to the rankings.

The primary measure is categorical, not embedding-based: unique combinations of
(audience-class x mechanic x unlock). That is the scheme that measured best on
idea generation, and unlike cosine distance it is legible — you can look at the
table and see which cell is over-represented.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any, Sequence

from genome import IdeaGenome, _norm_key
from similarity import Index, cosine


def combination_diversity(genomes: Sequence[IdeaGenome]) -> dict[str, Any]:
    if not genomes:
        return {"n": 0}
    combos = Counter()
    per_slot: dict[str, Counter] = {k: Counter() for k in
                                    ("audience", "mechanic", "unlock", "model", "loop")}
    for g in genomes:
        combos[(_norm_key(g.audience.value), _norm_key(g.mechanic.value),
                _norm_key(g.unlock.value))] += 1
        for k in per_slot:
            per_slot[k][_norm_key(getattr(g, k).value)] += 1
    n = len(genomes)
    return {
        "n": n,
        "unique_combinations": len(combos),
        "combination_ratio": round(len(combos) / n, 3),
        "unique_audiences": len(per_slot["audience"]),
        "unique_mechanics": len(per_slot["mechanic"]),
        "unique_unlocks": len(per_slot["unlock"]),
        "most_crowded_cell": (f"{combos.most_common(1)[0][0]}"
                              if combos else None),
        "most_crowded_count": combos.most_common(1)[0][1] if combos else 0,
        "slot_spread": {k: len(v) for k, v in per_slot.items()},
    }


def semantic_spread(genomes: Sequence[IdeaGenome]) -> dict[str, Any]:
    """Mean pairwise distance and structural disorder (1 - mean cosine to centroid)."""
    if len(genomes) < 2:
        return {"mean_pairwise_distance": None, "structural_disorder": None}
    texts = [g.text() for g in genomes]
    ix = Index(texts)
    vecs = [ix.vec(t) for t in texts]

    total, pairs = 0.0, 0
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            total += 1.0 - cosine(vecs[i], vecs[j])
            pairs += 1
    mean_pd = total / pairs if pairs else None

    centroid: dict[str, float] = {}
    for v in vecs:
        for t, w in v.items():
            centroid[t] = centroid.get(t, 0.0) + w
    norm = math.sqrt(sum(x * x for x in centroid.values())) or 1.0
    centroid = {t: x / norm for t, x in centroid.items()}
    disorder = 1.0 - (sum(cosine(v, centroid) for v in vecs) / len(vecs))

    return {"mean_pairwise_distance": round(mean_pd, 3) if mean_pd else None,
            "structural_disorder": round(disorder, 3)}


def island_spread(genomes: Sequence[IdeaGenome]) -> dict[int, int]:
    """Survivors per island thesis. A single island dominating means the other
    theses are being starved, which is how a search collapses onto one mode."""
    c = Counter(g.island for g in genomes)
    return dict(sorted(c.items()))


def report(store, cycle_id: int) -> dict[str, Any]:
    rows = store.ideas(cycle_id=cycle_id)
    alive = [r for r in rows if r["status"] != "killed"]
    gen_all = [IdeaGenome.from_dict(json.loads(r["genome"])) for r in rows]
    gen_alive = [IdeaGenome.from_dict(json.loads(r["genome"])) for r in alive]
    return {
        "generated": combination_diversity(gen_all),
        "survivors": combination_diversity(gen_alive),
        "spread_generated": semantic_spread(gen_all),
        "spread_survivors": semantic_spread(gen_alive),
        "islands_generated": island_spread(gen_all),
        "islands_surviving": island_spread(gen_alive),
    }
