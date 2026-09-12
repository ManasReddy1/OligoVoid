# Founder OS

A search engine for consumer app ideas that do not exist yet.

Founder OS maps the design space of consumer software, marks which regions shipped
products already occupy, finds the unoccupied regions that a recent capability
change just made viable, and then tries very hard to kill everything it finds. What
survives comes with a build cost, a unit-economics check, a distribution loop, a
list of conditions that would prove it wrong, and the cheapest test that would
settle it.

It is the same machine as OligoVoid, pointed at a different space. OligoVoid
enumerates siRNA modification patterns, maps literature coverage, scores the
untested regions for biophysical feasibility, and uses active learning to pick the
next wet-lab experiment. Founder OS enumerates idea genomes, maps product-corpus
coverage, scores the untested regions for buildability and economics, and uses
active learning to pick the next $50 ad test.

## Status

Architecture under review. No implementation yet.

## Read in this order

1. **[docs/01-research-findings.md](docs/01-research-findings.md)** — the measured
   results the design is built on. Read this first; several findings contradict the
   obvious way to build this kind of system.
2. **[docs/02-architecture.md](docs/02-architecture.md)** — the seven layers, the
   idea genome, the six generation operators, and the oracle ladder.
3. **[docs/03-schema-and-contracts.md](docs/03-schema-and-contracts.md)** — tables,
   agent call envelope, module layout.

## The three claims worth arguing with

**Parallel search beats a big committee.** Every system that has produced a real
discovery with large-scale agent compute is a generate-verify-select loop, not a
conference. The verifier is what converts compute into discovery.

**Grounding produces novelty; agents produce quality.** In the one study that
ablated this cleanly, a single agent with a retrieval layer beat a full multi-agent
system on novelty and diversity, while the multi-agent system won on quality and
kept improving over iterations. A "think like a genius" system prompt is not a
substitute for an evidence layer.

**The score must gate, not average.** Novelty is the harmonic mean of originality
and quality; the composite is harmonic throughout. An idea that is brilliant and
unbuildable has to score near zero, not land in the middle.

## The honest limit

Published benchmarks on venture-outcome prediction top out around a 4.7x lift over
a sub-1% base rate, with frontier models beating human baselines. That is the
ceiling this system aims at: better-than-chance ranking plus a cheap decisive test.
Not verdicts.
