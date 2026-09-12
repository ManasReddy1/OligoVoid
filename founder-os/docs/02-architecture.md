# Founder OS — Architecture v1

> **Purpose.** Continuously generate, attack, and rank consumer app ideas that are
> genuinely non-obvious, buildable for $10k-$50k, plausibly worth millions, and each
> accompanied by the cheapest test that would kill it.
>
> **Status.** Design for review. Nothing is built yet. Every `Fn` reference points
> to a measured result in `01-research-findings.md`.

---

## 0. The one law this architecture obeys

> **Agent count is a dependent variable of oracle quality.**

That is the finding that survives everything else in the research (F3b). Parallel
agent count scales well exactly to the degree that selection is sound and cheap, and
collapses otherwise:

| Oracle available | Viable parallelism | Evidence |
|---|---|---|
| Proof checker, type checker, unit test, numeric objective | thousands | Gauss ran thousands of concurrent Lean runtimes; AlphaEvolve optimises for throughput |
| Code execution plus a second-modality check | dozens | AI Scientist-v2's vision-model figure critique |
| **LLM-as-judge or peer discussion** | **3-4, centralised** | per-agent reasoning "prohibitively thin beyond 3-4 agents"; error amplification 4.4x centralised vs 17.2x independent |
| Human review | one, and it is the bottleneck | — |

Our oracle is the third row, with one rung of the fourth. So the honest design is
**small panels, many independent lineages, many iterations, and relentless
grounding** — not a swarm.

Three numbers make the cost of ignoring this concrete. Coordination cost is
super-linear, `T = 2.72 x (n + 0.5)^1.724` reasoning turns. Returns go **negative**
once single-agent accuracy passes 45% (beta = -0.408, p < 0.001). Message density
saturates at ~0.39 messages per turn, past which **+515% messaging buys 2-3%**.

On the story that prompted this project: the 10,000-agent run was **88 hours**, not
88 years, on Navier-Stokes; it proved the *forced* case that OpenAI explicitly
declined to claim the prize for; the underlying method was Cordoba and
Martinez-Zoroa's; two humans with LLM help had Lean-verified the same class of
result **before OpenAI's model finished training**; and no ablation shows 10,000
agents beat the ~100 that sufficed for the Euler result (F0). What is worth copying
is the machinery underneath, not the headcount.

**So the central engineering problem here is not the agents. It is manufacturing the
best available oracle for a question that has no oracle** (F2), and being explicit
about where the proxy leaks.

Founder OS answers that with an **oracle ladder**: gates of strictly increasing
cost, arranged so that almost everything dies against free deterministic checks and
only a handful of candidates ever reach the one stage that touches reality.

### The second idea: this repository already contains this machine

OligoVoid enumerates a combinatorial design space, maps which regions the published
literature occupies, identifies unoccupied-but-feasible regions, scores them
biophysically, and uses active learning to pick the next wet-lab experiment.
**Founder OS is that machine pointed at consumer software.**

| OligoVoid | Founder OS |
|---|---|
| 21 positions x 8 sugar modifications | Idea genome: 9 slots over grounded vocabularies |
| 60 curated published siRNA patterns | Product corpus: shipped, funded, and dead apps |
| Position x modification coverage matrix | Unlock x pain x audience x mechanic occupancy grid |
| 10 biophysics rules rejecting invalid duplexes | Deterministic invalidity rules (gate L0) |
| Feasibility: RISC, nuclease, thermo, off-target | Feasibility: buildability, margin, distribution, timing |
| Claude-enhanced scoring layer | Adversarial panel plus pairwise tournament |
| DMTL active learning picks the next assay | Probe selector picks the next $50 ad test |
| Hamming distance to nearest known pattern | Originality distance to nearest shipped product |

Void detection is the right abstraction for "what has nobody tried, and would it
work". The continuity is structural, not cosmetic.

---

## 1. Layer map

```
                          YOU
                           │
        "Find me opportunities today"  ·  "Kill #7"  ·  "Approve probe #3"
                           │
┌──────────────────────────▼───────────────────────────────────────────────┐
│  FOUNDER CONSOLE                                                         │
│  Morning Brief │ Dossiers │ Kill Log │ Probe Queue │ Diversity Monitor   │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────────────┐
│  ORCHESTRATOR — sole writer of the World Model                           │
│  Task Ledger · Progress Ledger · stall counter · cost governor · resume  │
└───┬──────────────┬──────────────┬──────────────┬──────────────┬──────────┘
    │              │              │              │              │
┌───▼────┐  ┌──────▼──────┐  ┌────▼─────┐  ┌─────▼──────┐  ┌────▼───────┐
│EVIDENCE│─▶│  VOID MAP   │─▶│ GENESIS  │─▶│  ORACLE    │─▶│  PROBE     │
│harvest │  │ occupancy + │  │ islands  │  │  LADDER    │  │  real $50  │
│cite    │  │ voids       │  │ archive  │  │  L0 → L5   │  │  tests     │
└────────┘  └─────────────┘  └──────────┘  └────────────┘  └────────────┘
                                    ▲              │              │
                                    └──────────────┘              │
                                   survivors mutate               │
                                    ▲                             │
                                    └─────────────────────────────┘
                                     probe results reweight scorer
```

Agents never call agents. Every arrow is mediated by the orchestrator.

---

## 2. State: a world model, not a conversation

The three systems that hold coherence over long horizons all refuse to pass
transcripts around. Kosmos threads everything through a structured world model
`W_t = f(W_{t-1}, A_data, A_lit, O)`; Aristotle keeps a proved/unproved lemma
ledger; Trinity refactors proofs into a reusable library (F2b, F1). OpenAI's
Navier-Stokes run instead used a model to "consolidate the most useful insights from
each agent group" — prose consolidation, lossy by construction.

Founder OS uses a **blackboard**: one structured store, written only by the
orchestrator, read by everyone. Adapting Magentic-One's dual ledger (F9):

**Task Ledger** (outer loop) — archive coverage, open frontiers, verified facts,
facts still to harvest, explicit educated guesses held separately from facts, and
the current cycle plan.

**Progress Ledger** (inner loop, per stage) — did this stage produce a new archive
elite? Is the search looping? Which gate is killing everything? A stage that
produces no new elite increments a **stall counter**; exceeding the maximum forces a
replan rather than another identical cycle. This is a deterministic fix for the two
largest measured failure modes, step repetition at 15.7% and unawareness of
termination conditions at 12.4% (F7).

**Context discipline.** The idea pool never enters a prompt. Thousands of
near-duplicate app ideas are a maximally adversarial distractor set for exactly the
degradation Chroma measured across all 18 frontier models (F10). Agents receive
identifiers and retrieve at most 10 records just in time; every comparison happens
in a small fixed-size set.

---

## 3. Evidence layer — the novelty engine

Finding F5 is unambiguous: **grounding produces novelty, agents produce quality.**
In the one clean ablation available, a single agent with a retrieval layer beat a
full multi-agent system on novelty and diversity. So the evidence layer is the most
important component in the system, and it is built first.

### Harvesters

Independent, scheduled, idempotent jobs writing normalised `Signal` rows. All
read-only; anything needing paid access degrades to manual import.

| Harvester | Extracts | Cadence |
|---|---|---|
| `capability_curve` | cost-per-unit over time for inference, voice, video, on-device | weekly |
| `platform_shift` | store policy changes, OS releases, regulatory effective dates | weekly |
| `pain_miner` | recurring unmet needs from low-star reviews of category leaders, with verbatim quotes | daily |
| `desire_miner` | explicit unserved wants from public forum threads | daily |
| `demand_signal` | whether anyone is actually searching for this | weekly |
| `product_corpus` | what already ships — the occupancy map | weekly |
| `funding_corpus` | where money goes; published investor theses; accelerator batches | weekly |
| `graveyard` | shutdowns and postmortems, with stated cause of death | monthly |
| `econ_benchmarks` | conversion, retention, ARPU, CAC by category | quarterly |

### Normalisation into five typed primitives

Every harvested item is reduced by a cheap model to one primitive and **discarded if
it cannot be**:

| Primitive | Required fields |
|---|---|
| `UNLOCK` | capability, old cost, new cost, date crossed |
| `PAIN` | who, what breaks, verbatim quote, volume estimate |
| `DEMAND` | query or topic, magnitude, trend direction |
| `SHIFT` | what changed, effective date, who it affects |
| `TOMBSTONE` | product, dates, stated cause of death |

Each carries `source_url`, `observed_at`, `dated_at` (the date the *fact* belongs
to, which is what makes clock-freezing possible) and `confidence`. **Uncited signals
never enter the store** (F36).

`docs/05-seed-evidence.md` contains the day-one load: the real 2026 figures the
harvesters would pull first, with sources.

---

## 4. Void map — the search space

### The idea genome

A typed slot vector, exactly analogous to `SiRNAModificationPattern`:

| # | Slot | Drawn from | Role |
|---|---|---|---|
| 1 | `unlock` | UNLOCK signals | what just became possible |
| 2 | `pain` | PAIN / DESIRE signals | the evidenced problem |
| 3 | `audience` | segment vocabulary | a named population, never "everyone" |
| 4 | `mechanic` | mechanic vocabulary | the core loop |
| 5 | `wedge` | derived | the narrowest first use case |
| 6 | `moat` | moat vocabulary | what accumulates |
| 7 | `model` | monetisation vocabulary | how money is made |
| 8 | `loop` | distribution vocabulary | how one user produces the next |
| 9 | `kill` | pre-registered | the conditions that would prove this wrong |

Slots 1-4 form the **behaviour descriptor**, the archive coordinate. Slot 9 is
mandatory: an idea with no stated way to be wrong dies at L0.

Every slot carries `provenance` — `evidence`, `inherited`, or `model` — because
novelty is atypical recombination of *grounded* entities and model-invented slots
are the hallucination surface (F17, F36).

The descriptor deliberately mirrors the categorical diversity scheme that measured
best on idea generation — industry context x psychological need x product form (F14)
— rather than raw embedding cosine.

### Occupancy and voids

The product corpus projects into the same genome space. A cell is **occupied** if a
shipped product maps to it, **tombstoned** if only dead products do, and a **void**
if neither. Voids adjacent to occupied cells are conservative variants; voids with
no occupied neighbour and a fresh UNLOCK are the frontier.

Tombstoned cells are the highest-value region *when paired with a new UNLOCK*,
because "right idea, wrong decade" is the most reliable opportunity source. Every
revisit must name the specific unlock that dissolves the original cause of death.

---

## 5. Genesis layer — generation

### Archive and islands

A **MAP-Elites archive** keyed by the behaviour descriptor, one elite per cell. This
is the structural fix for diversity collapse (F3): diversity is enforced by archive
geometry rather than hoped for from personas. A thousand variations on one theme
cannot crowd out a sparse promising region, "we already have that" becomes a
structural fact rather than a judgment, and archive coverage becomes a monotone
progress metric (F18).

**Islands assigned to opposing theses, not task slices** (F2c). This is the one
genuinely transferable structural choice from the Navier-Stokes run, where groups
were seeded with contradictory conjectures. Example island theses: *consumer
subscription is saturated* versus *consumer subscription is underpriced*;
*on-device inference wins* versus *frontier-model quality wins*; *habit products
win* versus *one-shot magic wins*. Each island generates under its thesis, and the
tournament settles which thesis produced better ideas. Hypothesis portfolios need
almost no inter-agent coherence, so they escape the coordination cost law entirely.

**Novelty-rejection before evaluation** (F18, ShinkaEvolve): candidates too similar
to an existing archive member are rejected *before* any expensive gate runs. This is
simultaneously the diversity mechanism and the largest single cost saving.

**Adaptive parent sampling** over the archive balances explore and exploit; operator
weights adapt to which operators produced L4 survivors last cycle, floor-clamped so
no operator starves to zero. Starvation is how a search collapses onto one mode.

### Every generation call, without exception

Four interventions with measured gains, composed. None of them is a persona.

1. **Verbalized Sampling** — ask for a distribution, not a sample: "generate 8
   candidates with their probabilities". Measured 2-3x diversity, +25.7% on human
   evaluation, free (F13). Default, not an option.
2. **Ordinary personas, never visionary ones.** Measured: "creative entrepreneur"
   personas produced 50.40 unique category combinations against 56.97 for ordinary
   personas — the celebrity-founder voice is *worse than a random normal person*
   (F14).
3. **Chain-of-thought before the idea** — 39.15 to 55.49 unique combinations, and it
   cuts the fixation slope 35%. Ordinary persona plus CoT reaches 65.42, beating the
   human baseline of 59.66 (F14).
4. **Nominal Group Technique** — every generator runs in complete isolation before
   anything is shared. Highest measured initial diversity, and non-negotiable
   (F15).

### The six genius operators, as mechanisms

F12 is the reason these cannot be personas: asking for novelty, denial prompting and
high temperature all trade quality for originality and barely move the frontier. The
only inference-time levers that push outward are external — real-world signal the
model did not memorise, forced far-domain analogy, and an archive that forbids
re-occupying filled cells.

So each operator takes **evidence rows as input** and returns nothing when it has no
evidence to work from, rather than inventing input.

1. **Frontier Cartographer** — reads capability curves, finds cost thresholds
   crossed in the last 18 months, and asks one question: what was structurally
   impossible at the old price and is trivial at the new one?
2. **Constraint Archaeologist** — for each category leader, identifies the
   constraint it *structurally cannot* remove, chosen from a closed list so the
   answer is checkable, then generates in exactly that blind spot.
3. **Analogy Transporter** — a mechanic proven in domain A and never applied in
   domain B is literally an empty matrix cell. Forced far-domain sampling is the
   measured novelty mechanism: analogies from domains at more than 3x the baseline
   domain distance scored highest on novelty across models (F16).
4. **Inversion Engine** — extracts consensus beliefs from the funding corpus and
   keeps only the inversions the evidence fails to contradict. An inversion the
   evidence refutes is just contrarianism.
5. **Tombstone Reviver** — pairs dead products with new unlocks and asks whether the
   stated cause of death has dissolved. Must name the unlock.
6. **First-Principles Reducer** — decomposes a job-to-be-done into irreducible
   steps, then removes the steps that exist only because of an obsolete technical
   limitation.

Plus three **variation operators** on survivors only: single-slot mutation,
crossover, and constraint-injection. All three return a **structured slot delta**,
never a fresh idea — bounded mutation keeps offspring near parents so archive
coordinates stay meaningful (F33).

### Diversity as a monitored invariant

Because optimising against any scorer collapses diversity (F35), the following are
logged every cycle and alarm on decline: Vendi score, mean pairwise cosine
distance, structural disorder (1 minus mean cosine to centroid), **unique category
combinations**, archive coverage, and the diversity utilisation ratio that fell from
1.03 to 0.47 as group size grew in the source study (F3).

---

## 6. The oracle ladder

Cost per candidate increases strictly down the ladder, and **every gate must kill**.
A gate that passes almost everything is decoration and gets removed (F32).

| Gate | Name | Cost | Target kill | Mechanism |
|---|---|---|---|---|
| **L0** | Validity | free, deterministic | ~40% | All nine slots filled; kill conditions present and falsifiable; audience not generic; no denied category; build estimate under ceiling; descriptor not duplicating a living elite |
| **L1** | Obviousness | 1 cheap call + embeddings | ~30% | The novelty measurement. Below. |
| **L2** | Grounding | retrieval only | ~15% | Every `pain` and `unlock` slot must resolve to a real Signal with a live URL |
| **L3** | Buildability | 1 strong call | ~20% | Build plan, cost, weeks, and **gross margin**. Negative margin is an automatic kill |
| **L4** | Adversarial panel | 5-7 calls, clean context | ~50% | Red team argues to kill. Below. |
| **L5** | Tournament | pairwise, batched | ranks | Bradley-Terry over pairwise comparisons, ranked by lower confidence bound |
| **L6** | Calibration | offline, periodic | tunes weights | Backtest against labelled historical outcomes |
| **L7** | Reality probe | $20-$200 plus human consent | truth | The only real oracle |

### L1 — the obviousness gate

Novelty is measured, not requested. Two distances, both external to the generating
model, following the facet-based recipe that measured ~13% better agreement with
expert novelty judgments (F26) with facets ported to *(who / trigger moment /
mechanism / distribution / monetisation)*:

1. **Prior distance** — ask three cheap models, cold, with no evidence context, for
   the most likely consumer apps for this audience and pain. If the candidate sits
   inside that set's similarity radius, it is what any language model would say.
   Cached per (audience, pain) key, so the cost is paid once per region.
2. **Corpus distance** — nearest-neighbour distance to shipped and funded products.
   The direct analogue of OligoVoid's Hamming distance to nearest known pattern.

```
originality = min(prior_distance, corpus_distance)
```

The **minimum** is deliberate: an idea must be far from both what ships and what a
model would immediately say.

### L3 — buildability, where most consumer AI apps actually die

Returns a structured plan and two numbers that kill outright:

```
build_cost_usd       <= 50_000
weeks_to_v1          <= 12
inference_cost_user  : monthly cost per active user
gross_margin         : (price x conversion - inference_cost) / (price x conversion)
```

`gross_margin <= 0` is an automatic kill that no enthusiasm elsewhere can override.
The seed evidence puts real numbers behind this: conversational consumer AI apps pay
between $0.09 and $18.24 per daily active user per month depending almost entirely
on model choice, a 200x spread. Model choice *is* the business model.

### L4 — the adversarial panel

Five to seven attackers, each confined to one surface, each with **completely clean
context** — the measured reason Cognition's reviewer loop works, at ~2 bugs caught
per pull request with 58% severe (F8). Critics are **sharded into isolated
subgroups**, which sustained the highest constructive-conflict density (F15), and
all seniority language is stripped to avoid the echo-chamber effect (F3).

| Attacker | Must argue |
|---|---|
| `demand_skeptic` | the pain is stated, not felt |
| `incumbent_response` | the category leader ships this as a feature in a quarter |
| `economics_attacker` | the margin or the acquisition cost never works |
| `distribution_attacker` | there is no loop; growth requires paid acquisition |
| `retention_attacker` | it is a one-shot novelty; usage collapses after week two |
| `graveyard_attacker` | this already died, here is the tombstone |
| `taste_attacker` | nobody would show this to a friend |

`survival_multiplier` is the fraction of attacks survived. **Any single unanswerable
attack is a hard kill** that the judge cannot overrule.

Plus the **sneaky advocate** (F23): an agent whose job is the most compelling
possible pitch for a deliberately bad idea. Every time it gets one past the panel,
that becomes a hard negative that hardens the rubric. This is the best available
defence against the ranker being gamed by persuasive prose.

Attackers and judges must come from **different model families** wherever available.
Heterogeneity is the only debate intervention that reliably helps (F6), juries only
help when errors are uncorrelated (F21), and mixed pools measurably beat
single-family pools (F34). Where only one family is available, the panel is
documented as one judge with variance, not as independent votes.

### L5 — ranking

Absolute scores from LLM judges are unstable, and the gap widens precisely on
subjective dimensions (F19). So: Swiss-style pairwise tournament, Bradley-Terry fit,
**mandatory position swap with averaging**, small fixed comparison sets to defeat the
first-proposal bias that gave a 10-30x advantage to presentation order in the
marketplace study, and ranking by **lower confidence bound** so under-compared ideas
cannot top the board.

**Ideas are rendered into a fixed-length template before judging.** Verbosity bias
runs 15-30 points across frontier judges (F20) — without normalisation, length is
the ranking.

Rubrics are binary checklist items in form-filling order: "does this name a specific
user with a specific trigger moment? Y/N" beats "rate specificity 1-5" (F22).

---

## 7. Scoring: two heads, never collapsed

The ideation-execution gap is the result that shapes this most (F25). LLM ideas were
rated *more novel than expert ideas* by blind reviewers — and when 43 experts spent
100+ hours each actually executing them, LLM ideas' scores **dropped more than human
ideas on every metric**, closing and in places flipping the ranking.

"Novel-sounding" is cheap and measurable, and models are already superhuman at it.
"Actually good" is not measurable at ideation time. Collapsing both into one number
is where the gap hides. So:

```
HEAD 1 — grounded novelty
  novelty   = harmonic_mean(originality, quality)

HEAD 2 — grounded viability
  viability = harmonic_mean(buildability, unit_economics, distribution_loop, timing)

Reported together, always. Ranked by pairwise Elo within each head.
Shortlisting composite, used only to select what reaches L7:
  founder_score = 100 * harmonic_mean(novelty, viability) * survival_multiplier
```

Harmonic means throughout, because the harmonic mean is chosen specifically to
penalise either term being low (F11). A weighted sum — the shape of the original
0-100 sketch — is rejected: it lets a fatal weakness hide behind strong unrelated
dimensions. An idea that is brilliant and unbuildable must score near zero, not
average out to the middle.

### The forecast head

Each L4 survivor is converted into 3-5 **falsifiable binary forecasts with
resolution dates** — "will any app in this category exceed 100k downloads within 18
months?" — forecast by a heterogeneous ensemble, aggregated, with **within-crowd
agreement as the confidence gate**. A twelve-model ensemble was statistically
indistinguishable from 925 human forecasters over a three-month tournament, though
elite humans still win on Brier score, 0.096 against 0.122 (F28).

Then the system **tracks its own Brier score over time**. This is the one thing no
rubric can provide: a scoring function that is eventually scored itself.

---

## 8. Calibration — why this is not a vibes machine

Any scorer produces confident numbers. The question is whether they rank real
outcomes correctly.

1. **Freeze the clock.** Restrict evidence to `dated_at` before a cut date.
2. **Run the full pipeline** on the frozen corpus.
3. **Score known outcomes.** Check whether consumer apps that subsequently became
   large rank above a matched set that launched and failed.
4. **Fit the weights** on held-out splits.
5. **Report lift over base rate honestly.**

Labelled historical data is public: PHBench ships 67,292 Product Hunt launches
(2019-2025) in 47,071 train / 6,753 validation / 13,468 blind-test splits, with 528
verified Series A raises, a 0.78% base rate, and train and validation labels
available under CC BY 4.0 (F27). Calibration is a weekend, not a research
programme. The licence forbids using the dataset to target or solicit specific
companies or individuals, which this use does not require.

The published ceiling sets expectations: the best PHBench ensemble reaches a **4.7x
lift over random** on that 0.78% base rate, and on VCBench most frontier models
**beat the human benchmark** with the best at over 6x baseline precision. A ~4% hit
rate, honestly reported, is the target. Any system claiming more is lying.

Two anti-self-delusion rules, because the closest existing system fails exactly
here. Google's AI co-scientist reports quality improving with compute on a curve
that is largely **self-rated Elo** — the system grading its own homework (F29).

- **Judge hygiene** (F20): pinned judge versions, a frozen golden set of 50-100
  human-labelled idea pairs, agreement reported on every judge or prompt change,
  permanent anchor items in the tournament so Elo stays comparable across time, and
  drift attribution so a change in scores can be traced to the system or the judge.
- **No closed loop** (F24): any agent whose output is scored never influences the
  scorer, and the scorer is at least as strong as the generator. Scaffold search is
  permitted only against objectively verifiable targets — dedup precision, retrieval
  recall, cost per idea, archive coverage — never against "idea quality".

---

## 9. Reality probes — the only real oracle

| Probe | Cost | Signal | Decides |
|---|---|---|---|
| Landing page plus paid traffic | $50-$150 | click-through, email conversion | does anyone want it |
| Ad creative A/B on the wedge message | $50 | cost per click by message | which positioning pulls |
| Post in the exact affected community | $0 | unprompted "I need this" replies | is the pain real |
| Concierge delivery to five humans by hand | ~$0 | do they return next week | is the loop real |
| Fake door in an existing surface | ~$0 | tap-through on a feature that does not exist | is intent real |

`probe_designer` writes the probe; **you approve every dollar**. Results return as
the highest-weighted evidence in the store and retroactively correct the scorer —
the same active-learning loop OligoVoid already runs, with ad clicks in place of
wet-lab assays. The probe selector picks the test maximising information per dollar
across the current shortlist.

This is also the human gate. One human decision per cycle — is this shortlist worth
anything — is logged as labels, grows the golden set, and is the only structural
defence against a closed reward-hacking loop (F24).

---

## 10. Cost architecture

Budget is planned around the fact that **you pay to read, not to write**: Manus
report a ~100:1 input-to-output ratio, making cache hit rate the dominant production
metric (F30).

- **Batch plus caching.** Generation and first-pass scoring are not
  latency-sensitive: batch is a flat 50% discount, cache reads are ~0.1x base input
  price, and they stack to roughly **95% off input**. This is the largest single
  lever and the reason "thousands of agent calls" is affordable at all.
- **Stable prefixes, append-only context.** Never mutate the prompt prefix; never
  add or remove tools mid-run. One mid-prompt edit invalidates the cache and
  silently multiplies the bill.
- **Cascade, do not route.** Cheap model for breadth, strong model only for the
  genius operators, the panel, and the judge. Route generation aggressively; **never
  route judging** (F20, F24). And do not build the router first — below roughly
  $200/month the routing layer costs more engineering time than it saves.
- **Model quality before agent count.** Anthropic's most actionable line: upgrading
  the model was a larger gain than doubling the token budget (F30).
- **Hard per-cycle budget.** Every call is metered before dispatch; when the
  remaining budget cannot cover the next stage the cycle halts and reports partial
  results.

A default cycle: 8 island theses x 24 population x 4 generations, panels of 5-7,
expensive models seeing only candidates that already passed two cheap gates. Cost
scales with **survivors**, not with generation volume.

**Durability** (F37): every stage checkpoints and resumes; tool failures are
surfaced to the agent wrapped in deterministic retries; prompt changes deploy without
killing in-flight cycles; the run ledger records every idea's lineage, operator,
gate verdicts with reasons, citations, and token cost, so any ranking can be
explained and any probe that proves the system wrong can be audited backwards.

---

## 11. Agent roster

Every agent is a pure function of an explicit context object. None calls another.

**Research** (cheap model, cites or is discarded)
`pain_miner` · `desire_miner` · `demand_analyst` · `corpus_cartographer` ·
`funding_scanner` · `capability_curve_analyst` · `graveyard_historian`

**Genesis** (strong model, the six operators of §5)
`frontier_cartographer` · `constraint_archaeologist` · `analogy_transporter` ·
`inversion_engine` · `tombstone_reviver` · `first_principles_reducer`

**Evaluation** (adversarial, clean context, mixed families)
`demand_skeptic` · `incumbent_response` · `economics_attacker` ·
`distribution_attacker` · `retention_attacker` · `graveyard_attacker` ·
`taste_critic` · `sneaky_advocate` · `adjudicator`

**Assessment**
`build_engineer` · `unit_economist` · `distribution_strategist` · `forecaster`

**Meta**
`orchestrator` (sole writer) · `calibrator` · `probe_designer`

---

## 12. Build plan

| Phase | Deliverable | Why here |
|---|---|---|
| **1** | Genome schema, L0 validity rules, world-model store, orchestrator with dual ledger and stall counter, cost governor | Nothing works without a typed space, explicit state, and a budget ceiling |
| **2** | Evidence layer: 3 harvesters plus normalisation, all citation-enforced | F5: grounding is the novelty engine. Build it before any generator |
| **3** | Void map: occupancy grid, void classification, originality distances, L1 obviousness gate | Makes novelty measurable instead of rhetorical |
| **4** | Genesis: MAP-Elites archive, island theses, six operators, Verbalized Sampling, diversity monitor | Search, once there is something to search over |
| **5** | Oracle ladder L2-L5: grounding, buildability, panel, sneaky advocate, tournament | The killing machinery |
| **6** | Calibration against PHBench-style labelled launches; golden set; Brier tracking | Turns the score from taste into a measured quantity |
| **7** | Founder Console: brief, dossiers, kill log, probe queue, diversity monitor | The interface, once there is something worth reading |
| **8** | Probe loop and active-learning feedback | Closes the loop to reality |

Phases 1-3 are load-bearing. A system with phases 1-3 and one naive generator will
beat a system with a magnificent agent roster and no evidence layer, and F5 is why.

---

## 13. What this architecture refuses to do

| Refused | Evidence |
|---|---|
| A 10,000-agent committee | F3b: coordination cost super-linear, negative returns past 45%, error amplification 17.2x independent; F0: no ablation supports the headline |
| "Think like a genius" personas | F14: visionary personas measured 50.40 against 56.97 for ordinary ones |
| Agents arguing to refine ideas | F6: 0 of 5 debate methods beat chain-of-thought across 36 configurations; F15: generate in isolation first |
| Persona diversity as diversity | F21, F3: correlated errors and the echo-chamber effect |
| Clever creativity prompting as the lever | F12: barely shifts the frontier |
| A weighted-sum 0-100 score | F11 harmonic gating; F25 two heads must stay separate |
| Rating ideas 1-10 | F19: pairwise wins, and wins by more on subjective dimensions |
| Self-rated progress metrics | F24 reward hacking; F29 the co-scientist's own weak spot |
| Uncited claims | F36: provenance is an engineering requirement |
| Verdicts | F27: a 4.7x lift on a 0.78% base rate is the honest ceiling |
| Enterprise, regulated, hardware, or over-budget ideas | Enforced deterministically at L0, not left to agent judgment |
