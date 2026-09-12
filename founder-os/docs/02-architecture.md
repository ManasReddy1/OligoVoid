# Founder OS — Architecture v1

> **Purpose.** Continuously generate, attack, and rank consumer app ideas that are
> (a) genuinely non-obvious, (b) buildable for $10k-$50k, (c) plausibly worth
> millions, and (d) accompanied by the single cheapest test that would kill them.
>
> **Status.** Design for review. Nothing is built yet.

---

## 0. The one idea this architecture is built around

The systems that produce real discoveries at scale are not committees. They are
**search loops with a verifier**. Compute is spent on many independent attempts that
are automatically checked and killed, not on many agents discussing one attempt
(finding F1).

Startup ideas have no proof checker. So the central engineering problem of Founder
OS is not the agents — it is **building the best available oracle for a question
that has no oracle**, and being explicit about where the proxy leaks.

Founder OS answers that with an **oracle ladder**: seven verification stages, each
cheaper and less true than the next, arranged so that 99% of candidates die against
free deterministic checks and only a handful ever reach the one stage that touches
reality.

The second idea: this repository already contains a working instance of exactly
this pattern. OligoVoid enumerates a combinatorial design space, maps which regions
the published literature has already occupied, identifies the unoccupied but
feasible regions ("voids"), scores them biophysically, and uses active learning to
pick the next experiment. **Founder OS is that same machine pointed at consumer
software.**

| OligoVoid | Founder OS |
|---|---|
| 21 positions x 8 sugar modifications | Idea genome: 9 slots over grounded vocabularies |
| 60 curated published siRNA patterns | Product corpus: shipped apps, funded startups, dead startups |
| Position x modification coverage matrix | Unlock x pain x audience occupancy matrix |
| 10 biophysics rules that reject invalid duplexes | Deterministic invalidity rules (L0) |
| Feasibility score: RISC, nuclease, thermo, off-target | Feasibility score: buildability, unit economics, distribution, timing |
| Claude-enhanced scoring layer | Adversarial panel + Elo tournament |
| DMTL active learning picks the next wet-lab experiment | Probe selector picks the next $50 ad test |
| Hamming distance to nearest known pattern | Originality distance to nearest shipped product |

The intellectual continuity is real, not cosmetic. Void detection is the right
abstraction for "what has nobody tried yet, and would it work".

---

## 1. Layer map

```
                          YOU
                           │
        "Find me opportunities today"   ·   "Kill this one"   ·   "Probe #3"
                           │
┌──────────────────────────▼───────────────────────────────────────────────┐
│  L6  FOUNDER CONSOLE                                                     │
│      Morning Brief │ Idea Dossiers │ Kill Log │ Probe Queue │ Ask        │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────────────┐
│  L5  ORCHESTRATOR  (chief of staff — owns ALL state, no agent-to-agent)  │
│      run ledger · context contracts · cost governor · scheduler          │
└───┬──────────────┬──────────────┬──────────────┬──────────────┬──────────┘
    │              │              │              │              │
┌───▼────┐  ┌──────▼──────┐  ┌────▼─────┐  ┌─────▼──────┐  ┌────▼───────┐
│ L1     │  │ L2          │  │ L3       │  │ L4         │  │ L4b        │
│EVIDENCE│─▶│ VOID MAP    │─▶│ GENESIS  │─▶│ ORACLE     │─▶│ PROBE      │
│harvest │  │ occupancy + │  │ evolution│  │ LADDER     │  │ real-world │
│ground  │  │ void finder │  │ operators│  │ L0→L5 kill │  │ $50 tests  │
└────────┘  └─────────────┘  └──────────┘  └────────────┘  └────────────┘
                                    ▲              │
                                    └──────────────┘
                                   survivors mutate
```

Data flows one way. Agents never call agents. The orchestrator owns every write.

---

## 2. L1 — Evidence layer (the novelty engine)

Finding F4 is unambiguous: **grounding produces novelty, agents produce quality.**
So the evidence layer is not plumbing, it is the most important component in the
system. An idea slot that is not traceable to a harvested signal is treated as a
hallucination risk (F7).

### Harvesters

Each harvester is an independent, scheduled, idempotent job writing normalised
`Signal` rows. All are read-only and respect robots/ToS; anything requiring paid
access degrades gracefully to manual CSV import.

| Harvester | Source | Extracts | Cadence |
|---|---|---|---|
| `capability_curve` | model pricing pages, release notes, benchmark posts | cost-per-unit over time for inference, voice, video, on-device | weekly |
| `platform_shift` | App Store / Play policy changelogs, OS release notes, regulatory feeds | newly permitted or newly forbidden behaviour | weekly |
| `pain_miner` | app store reviews (1-3 star) for category leaders | recurring unmet need, with verbatim quotes | daily |
| `desire_miner` | public forum threads of the "I wish an app existed" shape | explicit unserved wants | daily |
| `demand_signal` | search-trend and autocomplete surfaces | whether anyone is actually looking | weekly |
| `product_corpus` | shipped-app directories, launch boards | what already exists (the occupancy map) | weekly |
| `funding_corpus` | funding announcements, accelerator batch lists, published RFS theses | where money is going | weekly |
| `graveyard` | shutdown notices, postmortems | what has already been tried and died, and why | monthly |
| `econ_benchmarks` | subscription-app benchmark reports | conversion, retention, ARPU, CAC by category | quarterly |

### Signal normalisation

Every harvested item is reduced by a cheap model to one of five typed primitives,
and **discarded if it cannot be**:

| Primitive | Meaning | Required fields |
|---|---|---|
| `UNLOCK` | something became possible or 10x cheaper | capability, old cost, new cost, date crossed |
| `PAIN` | an evidenced human problem | who, what breaks, verbatim quote, volume estimate |
| `DEMAND` | measurable pull | query/topic, magnitude, trend direction |
| `SHIFT` | platform, regulatory, or cultural change | what changed, effective date, who it affects |
| `TOMBSTONE` | a prior attempt and its cause of death | product, dates, stated cause |

Each carries `source_url`, `observed_at`, and a `confidence`. Uncited signals never
enter the store. This is what makes downstream originality claims checkable rather
than rhetorical.

---

## 3. L2 — Void map (the search space)

### The idea genome

An idea is a typed slot vector, exactly analogous to `SiRNAModificationPattern`:

| # | Slot | Drawn from | Example |
|---|---|---|---|
| 1 | `unlock` | UNLOCK signals | realtime speech at negligible cost per minute |
| 2 | `pain` | PAIN / DESIRE signals | the specific evidenced problem |
| 3 | `audience` | segment vocabulary | a named population, never "everyone" |
| 4 | `mechanic` | mechanic vocabulary | the core loop: capture, streak, async-social, ambient |
| 5 | `wedge` | derived | the narrowest possible first use case |
| 6 | `moat` | moat vocabulary | accumulating data, habit, network, taste, library |
| 7 | `model` | monetisation vocabulary | subscription, consumable, marketplace take, ads |
| 8 | `loop` | distribution vocabulary | how one user produces the next, with no ad spend |
| 9 | `kill` | generated, pre-registered | the conditions that would prove this wrong |

Slots 1-4 define the **behaviour descriptor** — the archive coordinate used to force
diversity. Slots 5-8 are the strategy. Slot 9 is what makes the idea falsifiable
and is mandatory: an idea with no stated way to be wrong is rejected at L0.

Every slot instance stores `provenance`: `evidence` (traceable to a Signal),
`inherited` (from a parent idea), or `model` (invented). Ideas whose load-bearing
slots are all `model`-provenance are flagged as unsupported (F7).

### Occupancy and voids

The product corpus is projected into the same genome space. A cell of the
`unlock x pain x audience` matrix is **occupied** if a shipped product maps to it,
**tombstoned** if only dead products map to it, and a **void** if neither. Voids
adjacent to occupied cells are conservative variants; voids with no occupied
neighbour and a fresh `UNLOCK` are the interesting frontier — the same
classification OligoVoid already does for modification patterns.

Tombstoned cells are not skipped. They are the highest-value region *when paired
with a new UNLOCK*, because "right idea, wrong decade" is the most reliable source
of real opportunity. Every tombstone revisit must state which specific UNLOCK
invalidates the original cause of death.

---

## 4. L3 — Genesis layer (evolutionary generation)

Population-based search over the genome, with a **MAP-Elites archive** keyed by the
behaviour descriptor. This is the structural fix for F2: diversity is enforced by
the archive geometry, not hoped for from agent personas. Each archive cell retains
only its single best occupant, so a thousand variations on one theme cannot crowd
out a sparse but promising region.

**Island model.** Six to eight isolated sub-populations evolve in parallel with
different operator weights and different seed signals; migration between islands
every N generations. Islands prevent a single early winner from dominating the
whole run.

### The six genius operators (mechanisms, not personas — F6)

Each takes concrete evidence rows as input and emits genome candidates. None of
them works by asking a model to "be creative".

1. **Frontier Cartographer** — reads `capability_curve` signals, finds curves that
   crossed a threshold in the last 18 months, and asks only: what was structurally
   impossible at 10x this price and is now trivial? Timing is the input, not a
   guess.
2. **Constraint Archaeologist** — for each category leader in the product corpus,
   identifies the constraint it *structurally cannot* remove (business-model
   lock-in, platform dependency, brand promise, existing-user obligation) and
   generates in exactly that blind spot. Incumbent weakness as a search direction.
3. **Analogy Transporter** — a mechanic proven in domain A and never applied in
   domain B is literally an empty matrix cell. Enumerates high-performing
   mechanic x domain pairs and transports them. Pure void detection.
4. **Inversion Engine** — extracts consensus beliefs from the funding corpus and
   inverts them, keeping only inversions that survive the evidence layer. What does
   everyone believe that the data does not support?
5. **Tombstone Reviver** — pairs `TOMBSTONE` rows with `UNLOCK` rows and asks
   whether the stated cause of death has been dissolved. Must name the specific
   unlock.
6. **First-Principles Reducer** — strips a job-to-be-done to its irreducible steps
   and asks what the shortest possible path is, ignoring how anyone does it today.

Plus three **variation operators** applied to survivors: single-slot mutation,
crossover between two parents, and constraint-injection (force a slot to an unusual
value and repair the rest).

### Pacing

Per F3, spend goes into generations, not seats. A default cycle is
**8 islands x 24 population x 4 generations**, with panels capped at 5-7 agents
anywhere deliberation happens (F2). Model routing: the cheapest capable model
generates breadth, the strongest model runs only the genius operators and the final
judge.

---

## 5. L4 — The oracle ladder (the part that matters)

Candidates descend through seven gates. Each gate is strictly cheaper than the one
below it and kills aggressively, so the expensive stages see very few survivors.

| Gate | Name | Cost per idea | Kills | Mechanism |
|---|---|---|---|---|
| **L0** | Validity | ~free, deterministic code | ~40% | Schema complete, all nine slots filled, kill conditions present and falsifiable, audience not "everyone", no forbidden category (regulated, hardware-heavy, >$50k build) |
| **L1** | Obviousness | 1 cheap call + embedding | ~30% of survivors | The measurable novelty test. See below. |
| **L2** | Grounding | retrieval, no generation | ~15% | Every `pain` and `unlock` slot must resolve to a real Signal with a live URL. Uncited load-bearing slots are stripped; the idea dies if nothing load-bearing remains (F7) |
| **L3** | Buildability | 1 strong call | ~20% | An engineer agent writes the actual build plan, names the stack, estimates weeks and dollars against the $10k-$50k ceiling, and computes **inference cost per active user per month** against the intended price. Negative gross margin is an automatic kill |
| **L4** | Adversarial panel | 5-7 calls | ~50% | Red team argues to kill, using the idea's own pre-registered kill conditions plus graveyard evidence. Survival requires a defence the panel cannot break |
| **L5** | Elo tournament | pairwise, batched | ranks | Bradley-Terry pairwise comparison among survivors rather than absolute 0-100 scoring, which is far more stable under LLM judges (F8) |
| **L6** | Backtest calibration | offline, periodic | tunes | Scoring weights are fit against labelled historical outcomes, not chosen by taste. See §7 |
| **L7** | Reality probe | $20-$200 and human consent | truth | The only real oracle. See §8 |

### L1, the obviousness gate — the system's sharpest instrument

Novelty is not asked for, it is measured, in the spirit of F5. Two independent
distances, both external to the generating model:

1. **Prior distance.** Ask three cheap models, cold, with no evidence context, for
   the 20 most likely consumer app ideas for the same audience or pain. Embed them.
   If the candidate sits within a tight similarity radius of that set, it is what
   any language model would say — the definition of obvious — and it dies.
2. **Corpus distance.** Nearest-neighbour distance to the product corpus of shipped
   and funded products, the direct analogue of OligoVoid's Hamming-distance-to-
   nearest-known-pattern.

These combine into an `originality` in [0,1]. Per F5, originality is then joined to
quality **harmonically**, never added:

```
novelty      = harmonic_mean(originality, quality)
viability    = harmonic_mean(buildability, unit_economics, distribution_loop)
FounderScore = 100 * harmonic_mean(novelty, viability, timing) * survival_multiplier
```

Harmonic means throughout, because an idea that is brilliant and unbuildable must
score near zero rather than average out to the middle (F5). `survival_multiplier`
is the fraction of adversarial attacks the idea survived at L4. A weighted sum —
the shape of the original draft's 0-100 score — is explicitly rejected: it lets a
fatal weakness hide behind strong unrelated dimensions.

---

## 6. Agent roster

Mapped from the original design, with each agent's job narrowed to something
checkable. Every agent is a pure function of an explicit context object; none of
them can call another agent (F9).

**Research layer (grounded, cheap model, cites or is discarded)**
`pain_miner` · `demand_analyst` · `corpus_cartographer` · `funding_scanner` ·
`capability_curve_analyst` · `graveyard_historian`

**Genesis layer (strong model, the six operators of §4)**
`frontier_cartographer` · `constraint_archaeologist` · `analogy_transporter` ·
`inversion_engine` · `tombstone_reviver` · `first_principles_reducer`

**Evaluation layer (adversarial by construction)**
`red_team` (argues to kill; scored on kills that survive review) ·
`unit_economist` (margin, CAC, retention arithmetic) ·
`build_engineer` (stack, weeks, dollars) ·
`distribution_strategist` (the zero-budget loop, or it dies) ·
`taste_critic` (would a real person screenshot this — the thing consumer systems
usually omit) · `judge` (final synthesis, sees all dissent, cannot overrule a
hard kill)

**Meta**
`orchestrator` (owns state, budget, scheduling) ·
`calibrator` (fits scoring weights to backtest outcomes) ·
`probe_designer` (writes the cheapest decisive real-world test)

---

## 7. L6 — Backtest calibration (why this is not a vibes machine)

Any idea-scoring system can produce confident numbers. The question is whether the
numbers rank real outcomes correctly. Founder OS is calibrated, not tuned by taste:

1. **Freeze the clock.** Restrict the evidence layer to sources dated before a cut
   date, e.g. 2023-01-01.
2. **Run the full pipeline** on the frozen corpus.
3. **Score known outcomes.** Take consumer apps that subsequently became large, and
   a matched set that launched and failed, and check whether the scorer ranks the
   winners above the losers.
4. **Fit the weights** to maximise ranking lift, using held-out splits.
5. **Report lift over base rate honestly.** F8 sets the expectation: the published
   ceiling on this class of prediction is roughly a 4.7x lift on a sub-1% base rate,
   and frontier models beating human benchmarks on founder-success prediction. A
   system claiming more than that is lying.

Labelled historical data for this exists and is public (PHBench's 67k launches with
528 verified Series A outcomes and blind test splits), which means calibration is a
weekend of work rather than a research programme.

The honest deliverable is therefore: **a ranked shortlist with better-than-chance
lift, explicit kill conditions, and the cheapest next test** — not a verdict.

---

## 8. L7 — Reality probes (the only real oracle)

Everything above L7 is a proxy. One stage touches ground truth, and it is the
system's actual output:

| Probe | Cost | Signal | Decides |
|---|---|---|---|
| Landing page + paid traffic | $50-$150 | click-through and email conversion | does anyone want it |
| Ad creative A/B on the wedge message | $50 | cost per click by message | which positioning pulls |
| Community post in the exact affected forum | $0 | unprompted "I need this" replies | is the pain real |
| Concierge delivery to 5 humans by hand | ~$0 | do they come back next week | is the loop real |
| Fake-door in an existing surface | ~$0 | tap-through on a feature that does not exist | is intent real |

`probe_designer` writes the probe. **You** approve the spend. Results return as
`PROBE_RESULT` rows and become the highest-weighted evidence in the store,
retroactively correcting the scorer — this is the active-learning loop OligoVoid
already runs, with ad clicks in place of wet-lab assays. The probe selector picks
the test that maximises information per dollar across the current shortlist.

---

## 9. Control flow, state, and cost

**Single-writer orchestrator.** All state lives in one store; agents receive a
context object and return structured output. No agent-to-agent messaging, no shared
mutable scratchpad. This is the direct answer to the standard multi-agent failure
set (F9).

**Context contracts.** Every agent call declares its input schema, output schema,
token ceiling, and model tier. Outputs failing schema validation are retried once,
then dropped. No free-text hand-offs between stages.

**Cost governor.** A hard per-cycle budget. Every call is metered before dispatch;
when the remaining budget cannot cover the next stage, the cycle halts and reports
partial results rather than overrunning. Cheap model for breadth, strong model only
for the genius operators, the adversarial panel, and the judge. Prompt caching on
the shared evidence context, which is the same across hundreds of calls in a cycle;
batch API for anything not latency-sensitive.

**Scheduling.** A nightly cycle produces the Morning Brief. Harvesters run on their
own cadence. A cycle is resumable: every stage checkpoints, so a halted run
continues rather than restarting.

**Run ledger.** Every idea records its full lineage: parents, operators applied,
every gate verdict with reasons, every citation, and total token cost. The system
must be able to explain exactly why any idea ranked where it did, and to be audited
after a probe proves it wrong.

---

## 10. Build plan

| Phase | Deliverable | Why this order |
|---|---|---|
| **1** | Genome schema, validity rules (L0), store, orchestrator skeleton, cost governor | Nothing works without a typed space and a budget ceiling |
| **2** | Evidence layer: 3 harvesters (capability curves, pain mining, product corpus) + signal normalisation | F4: grounding is the novelty engine; build it before any generation |
| **3** | Void map: occupancy matrix, void classification, originality distances | Makes L1 obviousness measurable instead of rhetorical |
| **4** | Genesis: MAP-Elites archive, island model, the six operators | Search, once there is something to search over |
| **5** | Oracle ladder L2-L5: grounding, buildability, adversarial panel, Elo | The killing machinery |
| **6** | Backtest calibration against labelled historical launches | Turns the score from taste into a measured quantity |
| **7** | Founder Console: Morning Brief, dossiers, kill log, probe queue | The interface, last, once there is something worth reading |
| **8** | Probe loop and active-learning feedback | Closes the loop to reality |

Phases 1-3 are the load-bearing work. A system with phases 1-3 and a single naive
generator will outperform a system with a magnificent agent roster and no evidence
layer, and F4 is the reason.

---

## 11. What this architecture deliberately refuses to do

- **No 10,000-agent committee.** F2 measured diversity *falling* as team size grew
  from 2 to 8. Compute goes to lineages and generations, not seats.
- **No "think like a genius" prompting as the novelty source.** F6 measured that
  inference-time novelty elicitation trades quality for originality and barely
  moves the frontier.
- **No weighted-sum score.** F5 requires harmonic gating so a fatal flaw cannot
  average away.
- **No uncited claims.** A slot without a live source URL is a hallucination until
  proven otherwise.
- **No verdicts.** The output is lift over base rate plus the cheapest decisive
  test, because F8 shows that is the honest ceiling.
- **No enterprise ideas, no regulated categories, no hardware, nothing over $50k
  to build.** Enforced deterministically at L0, not left to agent judgement.
