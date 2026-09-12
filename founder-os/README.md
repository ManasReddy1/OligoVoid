# Founder OS

A search engine for consumer app ideas that do not exist yet.

Founder OS maps the design space of consumer software, marks which regions shipped
products already occupy, finds the unoccupied regions a recent capability change
just made viable, and then tries very hard to kill everything it finds. What
survives arrives with a build cost, a margin check, a distribution loop, the
conditions that would prove it wrong, and the cheapest test that would settle it.

It is the same machine as OligoVoid, pointed at a different space. OligoVoid
enumerates siRNA modification patterns, maps literature coverage, scores untested
regions for biophysical feasibility, and uses active learning to pick the next
wet-lab experiment. Founder OS enumerates idea genomes, maps product-corpus
coverage, scores untested regions for buildability and economics, and uses active
learning to pick the next $50 ad test.

## Status

Architecture under review. No implementation yet.

## Read in this order

1. **[docs/01-research-findings.md](docs/01-research-findings.md)** — the evidence
   base: 37 measured results with sources. Read this first; several of them
   contradict the obvious way to build this system.
2. **[docs/02-architecture.md](docs/02-architecture.md)** — the layers, the idea
   genome, the six generation operators, the oracle ladder, the two-headed score.
3. **[docs/03-schema-and-contracts.md](docs/03-schema-and-contracts.md)** — tables,
   agent call envelope, module layout.
4. **[docs/04-operator-specs.md](docs/04-operator-specs.md)** — implementation-ready
   detail for each operator and each gate.
5. **[docs/05-seed-evidence.md](docs/05-seed-evidence.md)** — the real 2026 market
   data the harvesters would load on day one, with sources and an explicit list of
   what could not be verified.

## The five claims worth arguing with

**Agent count is a dependent variable of oracle quality.** Parallel agents scale
well exactly as far as selection is sound and cheap. With a proof checker, you can
run thousands. With another model's opinion as the selector, the measured ceiling is
three or four, coordination cost is super-linear in headcount, and returns go
negative once single-agent accuracy passes 45%. Our oracle is the weak kind, so the
design spends compute on lineages, iterations and grounding instead of seats.

**The famous 10,000-agent result was 88 hours, not 88 years.** It proved the forced
case of Navier-Stokes, which its authors explicitly declined to claim the prize for;
the mathematical method was not the model's; two humans with model assistance had
formally verified the same class of result before the model finished training; and no
published ablation shows that 10,000 agents beat the hundred that sufficed for an
easier problem in the same effort. What is worth copying is the verifier, not the
headcount.

**Grounding produces novelty; agents produce quality.** In the one clean ablation
available, a single agent with a retrieval layer beat a full multi-agent system on
novelty and diversity, while the multi-agent system won on quality. An evidence
layer is not plumbing around the clever part. It *is* the clever part.

**A "think like a genius" prompt makes output worse.** Measured: visionary-founder
personas produced fewer unique idea categories than ordinary personas, and asking
for novelty buys originality by spending quality. Genius has to be a mechanism with
external inputs — a cost-curve tracker, a constraint analyser, a forced far-domain
analogy — wrapped in an ordinary voice.

**The score must gate, not average.** Novelty is the harmonic mean of originality
and quality; viability is harmonic across buildability, margin, distribution and
timing; and the two heads are never collapsed into one number, because that is
exactly where the ideation-execution gap hides.

## The honest limit

Published benchmarks on venture-outcome prediction top out near a 4.7x lift over a
sub-1% base rate, with frontier models beating human baselines. That is what this
system aims at: better-than-chance ranking, explicit kill conditions, and a cheap
decisive test. Not verdicts.
