# Operator and gate specifications

Implementation-ready detail for the two components that do the real work: the
generation operators (L3) and the oracle gates (L4). Written so each can be built
and tested independently.

---

## Part A — Generation operators

Every operator is a function `(evidence_slice, population) -> list[IdeaGenome]`.
Each declares what evidence it requires. **An operator with no evidence to work
from returns nothing rather than inventing input** — this is the mechanism that
enforces finding F12 (novelty comes from grounded structure, not from asking a model
to be creative).

### A0. The generation envelope — applies to every operator call

Four wrappers, each with a measured gain, composed on every call. Implemented once
in `genesis/envelope.py` so no operator can forget one.

| Wrapper | Implementation | Measured effect |
|---|---|---|
| **Verbalized Sampling** | ask for N candidates *with probabilities*, never a single answer | 2-3x diversity, +25.7% human evaluation, free (F13) |
| **Ordinary persona** | seed the voice from a mundane occupation or life situation drawn from a vocabulary; **never** "visionary founder", "genius", "world-class" | 56.97 vs 50.40 unique category combinations (F14) |
| **Reason first** | chain-of-thought about the evidence *before* any idea is emitted | 39.15 -> 55.49 unique combinations, fixation slope cut 35% (F14) |
| **Isolation** | each operator call runs with no visibility of any other operator's output this generation | highest measured initial diversity (F15) |

Temperature is swept per operator during calibration, never maxed: the effect on
novelty is U-shaped, and past the peak, quality collapse takes novelty with it
(F12).

Prompt prefixes are stable and the tool list is fixed for the whole cycle, because
cache hit rate dominates cost at a ~100:1 input-to-output ratio (F30).

### A1. Frontier Cartographer

**Requires:** `UNLOCK` signals with a dated cost crossing in the last 18 months.

**Mechanism.** For each unlock, compute the cost ratio `old/new`. Keep only ratios
above a threshold (default 10x). For each survivor, the prompt asks exactly one
question: *what product was structurally impossible at the old price and is trivial
at the new one?* The operator supplies the two prices, the crossing date, and the
three nearest `PAIN` signals by embedding distance. It never asks for "innovative
ideas".

**Emits:** genomes with `unlock` provenance = `evidence` and a `timing` annotation
recording months since crossing. Recency is the operator's entire edge: an unlock
that crossed 5 years ago is already occupied territory.

### A2. Constraint Archaeologist

**Requires:** `products` rows with `status = shipped` and known category leadership.

**Mechanism.** Two-step, and the first step is the one that matters. Step 1 asks a
strong model to name the constraint the incumbent **structurally cannot remove**,
and forces a choice from a closed list so the answer is checkable:

| Constraint class | Why it cannot be removed |
|---|---|
| `business_model_lock` | the fix destroys the revenue line |
| `platform_dependency` | the fix violates the host platform's rules |
| `brand_promise` | the fix contradicts what the brand means |
| `installed_base_obligation` | the fix breaks existing users |
| `scale_economics` | the fix only works at small scale |
| `data_gravity` | the fix requires data they do not have |

Step 2 generates only in the space that constraint forecloses. An answer that is
merely "they execute badly" is rejected — that is not a structural constraint and
the operator discards it.

**Emits:** genomes whose `wedge` slot is the foreclosed behaviour, and whose
dossier names the incumbent and the constraint class.

### A3. Analogy Transporter

**Requires:** the mechanic vocabulary and the product corpus.

**Mechanism.** Pure void detection, and the cheapest operator in the system. Build
the `mechanic x domain` matrix from the corpus. A cell is occupied if any product
uses that mechanic in that domain. For each **empty** cell where the mechanic has
demonstrated high performance elsewhere, ask whether the mechanic transports, and
require a stated reason the mechanic's psychological driver still applies in the
new domain. Most cells are empty because the transport does not work; the operator
must say why this one does.

**Emits:** genomes with `mechanic` provenance = `evidence` and an explicit
`transport_rationale`. Cells rejected with a reason are recorded so the operator
does not re-propose them next cycle.

### A4. Inversion Engine

**Requires:** `funding_corpus` signals and published investor theses.

**Mechanism.** Extract consensus beliefs as falsifiable propositions ("consumer
subscription is saturated", "social is closed"). For each, ask the evidence layer
whether the proposition is actually supported by the harvested data. Beliefs that
are *widely held but weakly supported* are the output; generate against those.
The filter is the point — an inversion that the evidence contradicts is just
contrarianism, and is dropped.

**Emits:** genomes annotated with the inverted belief and the specific evidence rows
that fail to support the consensus.

### A5. Tombstone Reviver

**Requires:** `TOMBSTONE` x `UNLOCK` pairs.

**Mechanism.** The highest-yield operator, because "right idea, wrong decade" is the
most reliable opportunity source. For each dead product, take the stated cause of
death and test it against every unlock: does this capability change dissolve that
specific cause? The operator must name the unlock and explain the dissolution. A
revival with no named unlock is rejected — otherwise the system simply re-proposes
things that already failed.

**Emits:** genomes carrying `revives` (the dead product), `death_cause`, and
`dissolving_unlock`.

### A6. First-Principles Reducer

**Requires:** a `PAIN` signal and the products currently serving it.

**Mechanism.** Decompose the job-to-be-done into irreducible steps, then ask which
steps exist only because of a historical technical limitation rather than because
the user needs them. Remove those. The output is the shortest path from intent to
outcome. This is the operator most likely to produce something that looks too
simple to be valuable, which is usually the signal that it is right.

**Emits:** genomes with a `removed_steps` list, each naming the obsolete limitation
that justified it.

### A7-A9. Variation operators

Applied to L4 survivors only, so compute goes to refining things that already
survived attack:

- **`mutate`** — resample one slot from its vocabulary, keep the rest, repair
  inconsistencies. One slot at a time, mirroring OligoVoid's 1/2/3-position variant
  enumeration.
- **`crossover`** — take slots 1-4 from one parent and 5-8 from another; reject if
  the descriptor collides with an existing archive elite.
- **`constraint_injection`** — force one slot to a deliberately unusual value and
  require the rest of the genome to be repaired around it. The highest-variance
  operator; run at low weight.

### Operator budget allocation

Weights are per-island and adapt: an operator whose output survived to L4 last
cycle gets more of the next cycle's budget, floor-clamped so no operator is ever
starved to zero. Starvation is how a search collapses onto one mode.

---

## Part B — Gate specifications

### L0 — Validity (deterministic, no model call)

Pure code. Rejects on any of:

- any of the nine slots empty
- `audience` matching a banned generic set (everyone, users, people, consumers)
- `kill` conditions absent, or present but not falsifiable (no number, no threshold,
  no observable outcome)
- category on the deny list: regulated (medical diagnosis, lending, insurance),
  hardware-dependent, anything requiring a marketplace cold-start on both sides
  simultaneously
- `build_estimate` already exceeding the $50k ceiling on the operator's own estimate
- descriptor exactly duplicating a living archive elite

**Measured in cycle 1: 0%.** The designed target was ~40%, and that target was
wrong rather than the gate being broken.

The generators receive the controlled vocabularies, the audience rule, the
falsifiability requirement and the category deny list *inside the prompt*. They
comply, so there is little left for a syntactic gate to catch. That is the
system working: it is cheaper to prevent a violation than to detect one.

So L0's real job is not filtering, it is **guaranteeing**. It is the thing that
stays true when a prompt is edited, a model is swapped, or a generator starts
drifting, and its kill rate is a drift alarm rather than a throughput target. A
rising L0 kill rate means the generators have stopped reading the rules.

Two consequences worth stating plainly. Do not tighten L0 to hit a number; that
is gaming the metric and it would kill sound ideas to make a dashboard look
right. And do not delete it because it kills nothing; a guarantee that has never
fired is not the same as a guarantee you do not need.

### L1 — Obviousness (the novelty measurement)

```
prior_distance  = 1 - max_similarity(candidate, cold_model_ideas)
corpus_distance = 1 - max_similarity(candidate, product_corpus)
originality     = min(prior_distance, corpus_distance)
```

`cold_model_ideas`: three cheap models, three different phrasings, no evidence
context, asked for the 20 most likely consumer apps for this audience/pain. Cached
per (audience, pain) key so the cost is paid once per region, not once per idea.

Taking the **minimum** of the two distances is deliberate: an idea must be far from
*both* what already ships and what any model would immediately say. Being novel
relative to only one of them is not enough.

Threshold is set by the calibration run, not by hand.

### L2 — Grounding (retrieval only, no generation)

For each slot with provenance `evidence`, confirm the cited `signal_id` exists, its
`source_url` still resolves, and its content still supports the claim. Strip slots
that fail. Kill the idea if `pain` or `unlock` is left unsupported — those two are
load-bearing; the others are strategy and may be model-authored.

This gate is where finding F7 becomes enforcement rather than aspiration.

### L3 — Buildability (one strong call, structured output)

Returns a structured build plan, and two numbers that can kill outright:

```
build_cost_usd      : must be <= 50_000
weeks_to_v1         : must be <= 12 for a solo build
inference_cost_user : monthly cost per active user
price_point         : intended monthly revenue per paying user
gross_margin        : (price * conversion - inference_cost) / (price * conversion)
```

`gross_margin <= 0` is an automatic kill. This single check removes the most common
way consumer AI apps die, and no amount of enthusiasm elsewhere can override it.

### L4 — Adversarial panel (5-7 calls, capped per F3/F3b)

Panel size is capped because per-agent reasoning capacity becomes "prohibitively
thin beyond 3-4 agents" under a fixed budget, error amplification runs 4.4x for
centralised topologies against 17.2x for independent ones, and quality peaked at
5-7 members before degrading at 8 (F3b, F3).

**Three structural requirements, each from a measured result:**

1. **Clean context.** Every attacker sees the idea and the evidence, never the
   generator's reasoning. This is the specific reason the measured review loop works
   at ~2 bugs per pull request with 58% severe (F8).
2. **Sharded subgroups.** Attackers are partitioned into isolated groups rather than
   one round table; partitioned critique sustained the highest constructive-conflict
   density (F15).
3. **Mixed model families, no seniority.** Heterogeneity is the only debate
   intervention that reliably helps (F6); juries help only when errors are
   uncorrelated (F21); mixed pools measurably beat single-family pools (F34). All
   authority language is stripped, because hierarchy produces deference rather than
   critique (F3). Where only one family is available, the panel is logged as one
   judge with variance, not as independent votes.

Each attacker owns exactly one surface and may not stray:

| Attacker | Must argue |
|---|---|
| `demand_skeptic` | nobody actually wants this; the pain is stated, not felt |
| `incumbent_response` | the category leader ships this as a feature in one quarter |
| `economics_attacker` | the margin or the acquisition cost does not work at any realistic scale |
| `distribution_attacker` | there is no loop; growth requires paid acquisition |
| `retention_attacker` | it is a one-shot novelty; usage collapses after week two |
| `graveyard_attacker` | this already died, here is the tombstone |
| `taste_attacker` | nobody would show this to a friend |

Every attacker has an explicit **"insufficient information -> abstain"** branch, the
direct antidote to the 11.7% of failures that are clarification failures (F7). An
abstention is not a survival.

The author side gets one reply per attack. A neutral adjudicator scores each
exchange; `survival_multiplier` is the fraction survived. **Any single unanswerable
attack is a hard kill the judge cannot overrule.**

### L4b — The sneaky advocate

A standing adversary, run against the panel rather than against ideas (F23). Its job
is the most persuasive possible pitch for a **deliberately bad** idea — one already
killed at L3 for negative margin, or a known tombstone with no dissolving unlock.

Every time it gets one past the panel, the case is recorded as a **hard negative**
and the rubric is amended so that attack surface catches it next time. Alternating
helpful and sneaky provers against a verifier measurably hardens the verifier and
makes honest output more legible, and legibility to small models transfers to
legibility to humans.

Run cadence: one sneaky candidate per cycle, cheap, and its pass rate is a monitored
system-health metric. A rising pass rate means the panel is being gamed by prose.

### L5 — Tournament (pairwise, batched)

Absolute scoring is unstable and the gap widens on subjective dimensions, which is
where we live (F19). So:

- **Swiss-style pairwise** comparison among L4 survivors, Bradley-Terry fit. The
  choice of rating algorithm barely matters (Spearman 0.944-0.953 across
  Bradley-Terry, Elo, Glicko and win-rate); choosing pairwise at all is what matters.
- **Fixed-length rendering.** Every idea is rendered into an identical template
  before judging. Verbosity bias runs 15-30 points across frontier judges (F20) —
  unnormalised, length becomes the ranking.
- **Position swap and average.** Each pair is judged twice with the order reversed;
  disagreements go to a third call. Presentation order carried a 10-30x advantage in
  the marketplace study, so order is randomised and comparison sets are small and
  fixed-size.
- **Rank by lower confidence bound**, not point estimate, so an under-compared idea
  cannot top the board (F19).
- **Separate tournaments per head.** Novelty and viability are ranked
  independently and never collapsed, because the ideation-execution gap lives in
  that collapse (F25).
- **Binary rubric items in form-filling order** — the judge answers each checklist
  question before emitting any comparison (F22).
- **Judge hygiene**: pinned model versions, permanent anchor ideas carried across
  cycles so ratings stay comparable over time, a frozen golden set of 50-100
  human-labelled pairs re-run on every judge or prompt change, and drift attribution
  so a score change can be traced to the system or the judge (F20).

### Gate ordering invariant

Cost per candidate must increase monotonically down the ladder, and every gate must
kill. If any gate kills almost nothing, it is decoration and should be removed or
tightened — a gate that passes everything is pure cost.
