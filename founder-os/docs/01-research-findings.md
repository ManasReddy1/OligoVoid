# Evidence base

Every design decision in `02-architecture.md` cites a finding here. Findings are
measured results with sources, not opinions. Where the literature contradicts the
obvious way to build this system, that is called out explicitly.

---

## Part 0 — What actually happened, since the premise matters

### F0. The "10,000 agents / 88-year-old problem" story is two real events and one press error

**"88" is hours, not years.** The figure comes from OpenAI's disclosure that on the
order of **10,000 concurrent agents ran for about 88 hours** (1-5 September 2026) on
the **Navier-Stokes** existence-and-smoothness problem. The problem itself dates to
Leray's 1934 weak-solution paper and has been a Clay Millennium Prize problem since
2000. No credible source says "88 years"; the phrase is a merge of "88 hours" and
"~90-year-old problem".
<https://openai.com/index/navier-stokes-solution/>
<https://www.quantamagazine.org/ai-has-solved-one-of-maths-1-million-millennium-prize-problems-20260908/>

The disclosed numbers: 2.7M messages and ~130B output tokens for Navier-Stokes;
Lean formalisation took a further 17 hours and was done by a *different* model
(GPT-6 Astra); the published proof runs ~166 pages; cost was "several million
dollars" by OpenAI's own account, with outside estimates of $10M-$40M.

Four things about it matter more than the agent count:

1. **It answers a weaker question than the headline implies.** Fefferman's official
   problem statement has four propositions; (A) and (B) assert global regularity
   with zero external forcing, while (C) and (D) permit a **smooth applied forcing
   term**. OpenAI proved a (C)/(D)-type statement. OpenAI itself wrote: *"We do not
   intend to claim the Millennium Prize for this result."* Clay still lists the
   problem as unsolved.
2. **The mathematical idea was not the model's.** The method is the
   **Cordoba-Martinez-Zoroa cascade** (circa 2021-2023, no AI involved). Fefferman's
   assessment: *"The heroes of the story are Cordoba and Martinez-Zoroa."* Terence
   Tao's technical writeup is the best account.
   <https://terrytao.wordpress.com/2026/09/07/finite-time-blowup-with-smooth-forcing-term-for-the-incompressible-porous-medium-boussinesq-and-incompressible-euler-equations/>
3. **Humans with LLM help got there first.** Buckmaster (NYU) and Alpoge had smooth-
   forced blowup for Boussinesq and 3D Euler on **15 August 2026**, Lean-verified on
   **22 August** — before OpenAI's internal model finished training on 28 August.
   Buckmaster's primary statement documents both the priority question and a
   provenance dispute about whether their Codex drafts influenced the model. He is
   careful: *"I have not seen OpenAI's proof. I do not know what their model did, or
   how. I am not accusing anyone of anything."*
   <https://cims.nyu.edu/~tristanb/statement.pdf>
4. **There is no published evidence that 10,000 agents was necessary.** No ablation,
   no reproduction, no orchestration specification. The only comparative datapoint
   OpenAI disclosed is that the **Euler** result needed roughly **100 agents for
   about 50 hours**. A 100x headcount increase for a harder problem, with no
   controlled comparison, is a spend report — not an architectural finding.

The separate genuinely-old result: in **May 2026** an OpenAI internal reasoning model
**disproved Erdos's 1946 planar unit-distance conjecture** (Erdos problem #90). That
one used **one model and one prompt** — no swarm, no Lean. Verification was by human
referees (Gowers, Litt, Sawin, Alon, Matchett Wood, Bloom) on *edited* output; no
external expert has seen the raw generation. Sawin improved on the construction
within days.
<https://www.scientificamerican.com/article/ai-just-solved-an-80-year-old-erdos-problem-and-mathematicians-are-amazed/>

And the cautionary precedent: in October 2025 an OpenAI executive claimed GPT-5 had
solved 10 open Erdos problems. It had rediscovered existing literature; the
mathematician who maintains the problem list called it "a dramatic
misrepresentation" and the post was deleted. Same organisation, same problem family,
seven months earlier.

**Design consequence:** the thing to copy from this story is not the swarm. It is
the machinery underneath — a sound machine verifier, a generator/verifier split
across different models, hypothesis-portfolio decomposition, an archive that
maintains diversity, structured (non-transcript) shared memory, and a staged
evaluation cascade. Agent count is a *dependent variable of oracle quality*.

---

## Part I — What large-scale agent compute actually does

### F1. The skeleton every successful system shares

Compute goes into many independent attempts that are automatically checked and
discarded, never into many agents discussing one attempt:

```
propose  ->  verify (cheap, automatic, adversarial)  ->  keep survivors  ->  mutate survivors
```

The verifier is load-bearing. Where a machine-checkable oracle exists, parallelism
converts directly into discovery because a wrong answer costs nothing to discard.

- **FunSearch** (Nature, 2024) evolved *programs that describe how to solve*, paired
  with a systematic evaluator. Produced the largest improvement in 20 years to the
  cap-set asymptotic lower bound.
  <https://www.nature.com/articles/s41586-023-06924-6>
- **AlphaEvolve** found a 48-multiplication 4x4 complex matrix multiply after
  **15 mutations**, beating the Strassen-derived bound of 49 that had stood 56
  years; improved the 11-dimensional kissing number from 592 to 593; an evolved
  scheduling heuristic recovered **0.7% of Google's worldwide compute**; a 32%
  speedup on the FlashAttention kernel turned "several months of dedicated
  engineering effort" into days. Across 50+ open math problems it matched state of
  the art on ~75% and **beat it on ~20%**. Every one of its five ablations degraded
  results — no single component carries it.
  <https://arxiv.org/abs/2506.13131>
- **AlphaProof** reached IMO 2024 silver (28/42) with a **3B-parameter** proof
  network doing AlphaZero-style tree search over Lean states, trained on 80M+
  auto-formalised Lean statements with a binary compile-or-not reward. Problem 6,
  solved by only 5 of 609 human contestants, took roughly **3 days** of test-time
  search — test-time compute per problem varied by three orders of magnitude.
  <https://www.nature.com/articles/s41586-025-09833-y>
- **Goedel-Prover-V2**: an **8B** open model at 84.6% pass@32 on miniF2F beat a
  671B model at the same metric — **80x smaller**. Loop quality and data curriculum
  dominate parameter count. <https://arxiv.org/abs/2508.03613>
- **Gauss / Trinity** formalised the strong Prime Number Theorem — ~25,000 lines of
  Lean, 1,100+ theorems — in **three weeks**, after 18+ months of stalled human
  effort, running **thousands of concurrent agents each with its own Lean runtime**.
  <https://www.math.inc/gauss>

Every one of those wins had a cheap, exact, automated verifier.

### F2. Verifier's Law, and why a startup idea is the hard case

Jason Wei's **Verifier's Law**: the ease of training AI to solve a task is
proportional to how verifiable the task is. He also names the **reverse asymmetry** —
tasks that take longer to verify than to propose.

A consumer app idea is the canonical reverse-asymmetric artifact. Generating a
thousand costs dollars. Verifying one costs a market experiment.
<https://www.jasonwei.net/blog/asymmetry-of-verification-and-verifiers-law>

**Design consequence:** the hard part of this system is not the agents. It is
manufacturing the best available proxy oracle and being honest about where it leaks.
Take the island model, the archive, and the novelty-rejection filter from the
evolutionary systems; leave behind the promise of superhuman discovery.

### F2b. Where soft oracles break, measured

**Kosmos** (Edison Scientific) is the closest published analogue to what we are
building: a structured **world model as the sole inter-agent channel** —
`W_t = f(W_{t-1}, A_data, A_lit, O)` — with data-analysis and literature agents
reading and writing one shared state rather than passing transcripts. Per 12-hour
run: ~200 agent rollouts, ~42,000 lines of code executed, ~1,500 papers read.
Collaborating scientists audited the output.
<https://www.alphaxiv.org/abs/2511.02824>

| Statement type | Accuracy |
|---|---|
| Data-analysis claims | 85.5% |
| Literature statements | 82.1% |
| **Interpretation statements** | **57.9%** |
| Overall | 79.4% |

Retrieval and computation hold up. **Synthesis is where it breaks.** Collaborators
judged a single 20-cycle run worth roughly six months of their own research time,
with valuable findings scaling **linearly** in cycles.

**Design consequence:** the interpretation layer needs the most adversarial
scrutiny, because it is empirically the weakest. In our system that is exactly the
judge and the composite score. Also: copy the world model. A structured blackboard
beats prose consolidation, and prose consolidation is what OpenAI used ("we
cross-pollinated the agent groups by using Codex to consolidate the most useful
insights from each agent group") — lossy by construction.

### F2c. Hypothesis-portfolio decomposition

The one genuinely transferable structural choice from the Navier-Stokes run:
groups were seeded with **contradictory conjectures** — some assigned to prove
regularity, others to construct blowup. Decomposition was by *hypothesis*, not by
subtask.

This matters because subtask decomposition requires knowing the shape of the answer
in advance, which is precisely what you lack on an open problem, and it is the
target of Cognition's critique (F8). Hypothesis portfolios are embarrassingly
parallel and need almost no inter-agent coherence, so they survive the coordination
cost law (F3b).

**Design consequence:** islands are assigned **opposing theses about the market**,
not different task slices.

---

## Part II — Why more agents makes things worse

### F3. Diversity falls as the group grows

**Diversity Collapse in Multi-Agent LLM Systems** names the cause **structural
coupling**: interaction *synchronises* agents rather than broadening exploration.
<https://arxiv.org/html/2604.18005v2>

- **Diversity Utilisation Ratio** (Vendi score per agent) falls **1.03 -> 0.47** as
  the group grows. Dense communication topologies accelerate premature convergence.
- **Echo-chamber effect:** authority hierarchies make junior agents defer. "Agents
  prioritize agreement over independent critique."
- **Compute efficiency paradox:** stronger, better-aligned models converge on *more*
  similar semantics despite higher per-sample quality.
- Horizontal / junior-led collaboration reached Vendi **8.08** versus **4.65** for
  interdisciplinary expert teams, with quality essentially flat (7.88-8.50 of 10).
  **There was no quality-diversity tradeoff** — the diversity was free.

Corroborated independently on research-idea generation by Chen & Zhang (2026),
*Enhancing Research Idea Generation through Combinatorial Innovation and
Multi-Agent Iterative Search Strategies*: uniqueness declines monotonically as team
size grows 2 -> 8 ("generating more content increases the likelihood of
similarity"), novelty shows **no trend at all** with team size ("the proposed method
cannot improve novelty by scaling up the number of agents"), and high-quality share
peaks at 5-7 members then drops at 8.
<https://arxiv.org/pdf/2604.20548>

**Design consequence:** panels capped at 5-7. Extra compute buys independent
lineages and iterations, never a bigger committee. Strip all seniority and authority
language from agent definitions.

### F3b. The scaling law: coordination cost is super-linear, and returns go negative

*Towards a Science of Scaling Agent Systems* is the most quantitative source
available on whether adding agents helps.
<https://arxiv.org/abs/2512.08296>

| Measurement | Result |
|---|---|
| Coordination cost in reasoning turns | `T = 2.72 x (n + 0.5)^1.724` — **super-linear** in agent count |
| Turns vs single-agent | hybrid topologies 6.2x (44.3 vs 7.2), centralised 3.8x, decentralised 3.6x |
| Practical agent ceiling | "per-agent reasoning capacity becomes prohibitively thin beyond **3-4 agents**" under a fixed budget |
| Capability saturation | tasks where single-agent accuracy already exceeds **45%** see **negative returns** from more agents (beta = -0.408, p < 0.001) |
| Error amplification vs single-agent | centralised **4.4x**, decentralised **7.8x**, independent **17.2x** |
| Communication saturation | `S = 0.73 + 0.28 x ln(c)`, saturating at ~**0.39 messages/turn**; beyond that **+515% messaging buys 2-3%** |
| Domain dependence | Finance Agent **+80.9%** (parallelisable), BrowseComp-Plus **+9.2%** (exploratory), PlanCraft **-39% to -70%** (sequential dependencies) |

Their mixed-effects model predicts the correct architecture in 87% of held-out
configurations.

Alongside it, the **verification gap**: "self-choice performance consistently lags
behind the pass@K upper bound regardless of the strategy", sometimes *degrading* as
K grows, and in one measurement GPT-5 as an external verifier **underperformed the
models' own judgment at K=1**. Breadth without a sound oracle converts into
unusable breadth.
<https://arxiv.org/html/2602.18998v1>

**The synthesis that governs this whole architecture:** parallel agent count scales
well exactly to the degree that selection is sound and cheap, and collapses
otherwise.

| Oracle | Viable parallelism |
|---|---|
| Lean, type checker, unit tests, numeric objective | thousands |
| Code execution plus a second-modality check | dozens |
| LLM-as-judge or peer discussion | **3-4, centralised** |
| Human review | one, and it is the bottleneck |

Our oracle is mostly the third row, with one rung of the fourth. That fixes panel
sizes at 3-7 and puts every spare dollar into independent lineages, iterations, and
grounding.

### F4. Iterations beat headcount

Same study, varying iterations instead of team size: diversity peaks at iteration 2,
novelty jumps sharply at iteration 2, and high-quality share rises with every
iteration. Where team size was flat, iteration count moved every metric.

**Design consequence:** the unit of spend is a generation of the loop, not an agent
seat.

### F5. Grounding produces novelty; agents produce quality

The cleanest ablation available. Chen & Zhang set agent count to 1 while keeping the
knowledge-planning-and-retrieval module:

- Single agent **+ retrieval beat the full multi-agent system on novelty and
  diversity.** The retrieval layer is the novelty engine.
- The single agent **plateaued** across iterations; the multi-agent system kept
  improving.
- Multi-agent's real contribution is **quality**.

**Design consequence:** build the evidence layer before any generator. A "think like
a genius" system prompt is not a substitute for it.

### F6. Multi-agent debate does not work the way everyone assumes

The original Society-of-Minds result showed gains (ICML 2024,
<https://arxiv.org/abs/2305.14325>). The re-evaluations do not hold up:

- Across **36 configurations, none of 5 debate methods exceeded a 20% win rate
  against plain chain-of-thought**, at far higher token cost.
  <https://arxiv.org/abs/2502.08788>
- **Self-consistency** (majority vote over N samples) consistently beat both CoT and
  debate at equal sample budget.
- "The Cost of Consensus": isolated self-correction beat unguided homogeneous
  debate, which degraded or stagnated accuracy while burning tokens.
  <https://arxiv.org/pdf/2605.00914>
- The one robust positive: **model heterogeneity among debaters consistently
  improves debate.** <https://arxiv.org/html/2510.20963v2>
- Debate's measured value is as **oversight**, not generation: it helps weak judges
  supervise stronger models. <https://arxiv.org/pdf/2605.27483>

**Design consequence:** no homogeneous round-robin debate. Independent generation
first, then heterogeneous critics from **different model families**, then pairwise
comparison rather than consensus-seeking discussion.

### F7. Naive multi-agent systems fail in measured, avoidable ways

**MAST**, the empirical failure taxonomy: 1,600+ annotated traces across 7
frameworks, inter-annotator kappa 0.88.
<https://arxiv.org/abs/2503.13657>

| Category | Share | Top modes |
|---|---|---|
| Specification issues | **41.8%** | step repetition 17.1%, unaware of termination 9.8%, disobey task spec 11.0% |
| Inter-agent misalignment | **36.9%** | reasoning-action mismatch 14.0%, fail to ask for clarification 11.7%, task derailment 7.2% |
| Task verification | **21.3%** | premature termination 7.8%, no/incomplete verification 6.8%, incorrect verification 6.7% |

Prompt-level fixes gave only +15.6% (ChatDev) and +9.4% (AG2 MathChat); the authors
conclude **architectural change is required**. Related work in this line reports
uncoordinated topologies amplifying errors up to **17x**, versus ~**4.4x** for
centralised architectures with a validation bottleneck.

**Design consequence:** centralised orchestrator with a mandatory verification gate.
Deduplication before any commit (step repetition). Claim and evidence in *separate*
schema fields so they can be cross-checked (reasoning-action mismatch). An explicit
"insufficient information -> abstain" branch in every critic (clarification failure).

### F8. Single writer, many readers

Three independent teams converged on the same rule: parallel agents are safe for
read and explore work, dangerous for write and synthesise work.

- **Anthropic's multi-agent research system**: orchestrator-worker, lead plans and
  writes the plan to external memory *before* work, 3-5 parallel subagents that
  cannot talk to each other and return 1-2K token condensed findings. **+90.2% over
  single-agent** on their internal research eval, at ~**15x** chat token usage.
  **Token usage alone explains 80% of variance** on BrowseComp. The explicit rule:
  *"Work should only be split when context can be truly isolated"* — decompose by
  context boundary, not by task type.
  <https://www.anthropic.com/engineering/multi-agent-research-system>
  <https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them>
- **Cognition**, who wrote the original argument against multi-agent systems, now
  report three shapes that work. The one that matters here: a **review loop** where
  the reviewer has **completely clean context** — measured ~2 bugs caught per pull
  request, **58% severe**. Clean context beats shared context because it avoids
  context rot. Their invariant: *"one main loop carries state; subagents are
  stateless workers with narrow scope"* and *"writes stay single-threaded;
  additional agents contribute intelligence rather than actions."* Unstructured
  swarms are "mostly a distraction".
  <https://cognition.com/blog/dont-build-multi-agents>
  <https://cognition.com/blog/multi-agents-working>
- **LangChain** state the same position: reads parallelise, writes do not.
  <https://www.langchain.com/blog/how-and-when-to-build-multi-agent-systems>

**Design consequence:** blackboard plus supervisor. The orchestrator is the only
writer. Every other agent is a stateless reader returning structured summaries.
Critics get clean context, not the generator's history.

### F9. Explicit state with a stall counter

**Magentic-One** is the best-documented explicit-state orchestrator: a dual-ledger,
two-loop design.
<https://arxiv.org/html/2411.04468v1>

- **Outer loop / Task Ledger:** verified facts, facts to look up, derived facts,
  educated guesses, and the plan.
- **Inner loop / Progress Ledger:** per-step self-reflection — is the request
  satisfied, is the team looping, are we making progress, who acts next.
  Non-progressing rounds increment a **stall counter**; exceeding the maximum
  triggers automatic reset and replan.

The stall counter is a cheap, direct fix for MAST's premature-termination and
step-repetition modes.

### F10. Context rot, and why this system is the adversarial case

Chroma tested 18 frontier models. **All 18 degrade monotonically with input
length**, even on trivial retrieval tasks, with the steepest decline in the
100K-500K band. Degradation is non-uniform: distractor presence matters, and
**semantically similar-but-wrong content actively misleads**.
<https://research.trychroma.com/context-rot>

A corpus of thousands of near-duplicate app ideas is a maximally adversarial
distractor set.

**Design consequence:** never put the idea pool in context. Keep identifiers, not
payloads; retrieve k <= 10 by ID just in time; force every comparison into a small
fixed-size set. Anthropic's context-engineering guidance (attention budget as a
first-class resource, compaction, structured note-taking, just-in-time retrieval) is
the reference implementation.
<https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>

---

## Part III — How to actually get novel output

### F11. Novelty must be scored as originality AND quality, joined harmonically

Padmakumar, Chen, Pan, Chen & He, ICLR 2026, *Measuring LLM Novelty as the Frontier
of Original and High-Quality Output*.
<https://proceedings.iclr.cc/paper_files/paper/2026/file/a361b72fbd3e6bc97de95aacad13a6df-Paper-Conference.pdf>

- Novelty is the **harmonic mean** of originality (fraction of n-grams unseen in the
  training corpus) and a task-specific quality score. The harmonic mean is chosen
  "to penalize either originality or quality being low."
- Originality alone rewards rare garbage; prior single-dimension metrics "would
  incorrectly rank rare but poor-quality output highly." Quality alone, judged by
  non-experts, rewards memorised text.
- Their LLM-judge quality scores were validated against three human annotators per
  item; inter-annotator agreement was Krippendorff's alpha **0.59-0.68**, the normal
  ceiling for creative judgment.

### F12. Prompting for novelty does not push the frontier outward

Same paper, Section 4:

- Sampling temperature has a **U-shaped** effect: originality rises, then quality
  collapses and takes novelty with it.
- Asking for novelty, denial prompting, and novel in-context examples "have a much
  smaller effect on novelty, often increasing originality at the expense of
  quality."
- What moves the frontier is base model quality, scale, and post-training — none of
  which we control at inference time.

**Design consequence:** the only inference-time levers that genuinely push outward
are **external**: retrieval of real-world signal the model did not memorise, forced
far-domain analogy, and a structural archive that forbids re-occupying filled cells.
Budget accordingly. Spend on grounding and archive structure, not on cleverer
creativity prompts.

### F13. Verbalized Sampling — the one free 2-3x

Mode collapse is driven by **typicality bias in preference data**: annotators
systematically prefer familiar text. The fix is to ask the model for a
*distribution* rather than a sample: "generate 5 X and their corresponding
probabilities." Training-free, model-agnostic.
<https://arxiv.org/abs/2510.01171> · <https://github.com/CHATS-lab/verbalized-sampling>

Measured: **2-3x diversity**, creative-writing diversity **1.6-2.1x** over direct
prompting, human evaluation **+25.7%**, no loss of factual accuracy or safety.
ICML 2026.

This is the highest measured gain per line of code in the entire evidence base, and
it is consistent with F12: it recovers diversity that alignment suppressed, moving
*along* the frontier rather than expanding it.

**Design consequence:** every generation call is a Verbalized Sampling call. Default,
not an option.

### F14. Ordinary personas beat visionary personas

**Barriers to Diversity in LLM-Generated Ideas** identifies two barriers: **fixation**
(autoregressive — early ideas disproportionately activate related representations,
constraining what follows) and **knowledge aggregation** (human creativity benefits
from knowledge partitioned across billions of minds; an LLM collapses it into one
representation).
<https://arxiv.org/html/2602.20408>

Measured on **unique category combinations**:

| Condition | Unique combinations |
|---|---|
| "Creative entrepreneur" persona | 50.40 |
| Ordinary persona | **56.97** (+13%) |
| Direct prompting | 39.15 |
| Chain-of-thought | **55.49** (fixation slope cut 35%) |
| Ordinary persona + CoT | **65.42** |
| Human baseline | 59.66 |

The celebrity-founder persona is **worse than a random normal person**. Ordinary
personas plus chain-of-thought beat humans by 26%. Human seeding had negligible
effect: *the problem is how ideas unfold, not where they start.*

Their diversity measure is **categorical, not embedding-based** — industry context
(9) x psychological need (9) x product form (10), scored by unique categories and
unique category *combinations*. That is a better fit for consumer app ideas than
cosine similarity, and it is directly reusable as an archive coordinate.

**Design consequence, and it contradicts the intuitive design:** a "think like a
genius" agent is measurably counterproductive. Genius must be a *mechanism* with
external inputs, wrapped in an ordinary voice, with chain-of-thought before the
idea. This is the single most important correction in this document.

### F15. Independent generation before any discussion

Same diversity-collapse study, measuring interventions:

- **Nominal Group Technique** — every agent generates independently *before* any
  discussion — gave the **highest initial diversity** (decaying over rounds).
- **Subgroup topology** — partition critics into separate discussion groups —
  sustained the **highest constructive-conflict density** (critique score >= 7) and
  showed a mid-debate diversity resilience spike.
- Robust across DeepSeek-V3, GPT-5.1, and o1-mini.

**Design consequence:** the "agents argue with each other" stage will silently kill
the novelty the generators produced unless generation is isolated first and critics
are sharded into subgroups.

### F16. Forced far-domain analogy is the measured novelty mechanism

**Unlocking LLM Creativity in Science through Analogical Reasoning**: a two-stage
mechanism — first generate cross-domain analogies, then search for solutions within
them. Measured on generation diversity (Vendi), solution novelty, and analogy
quality: analogical reasoning sourced analogies from domains with **more than 3x
higher domain distance** than a no-domain baseline and scored **highest on novelty
across models**.
<https://arxiv.org/html/2605.11258v1>

Implementation: do not prompt "give me a novel app idea". Prompt (1) sample a far
domain, (2) extract its *relational structure*, (3) map that structure onto a
consumer need. The forced far-domain sample is what defeats fixation.

By contrast, no controlled measurement of novelty gains from TRIZ, SCAMPER, or Six
Thinking Hats in an LLM context could be found. Treat those as folklore.

### F17. Novelty is atypical recombination, and provenance is traceable

Chen & Zhang's entity-recombination analysis treats methods, tasks, datasets and
metrics as typed knowledge units, extracts them per iteration, and traces every
entity to one of three sources: the previous idea, the retrieved literature, or the
model itself. Creative ideas "rarely emerge from entirely new inventions; instead,
they arise through atypical recombination of existing elements."

**Design consequence:** represent an idea as a typed slot vector over grounded
vocabularies and record provenance per slot. Slots sourced from evidence are real;
slots the model invented unprompted are the hallucination surface.

### F18. Quality-diversity machinery transfers even when the fitness signal is weak

- **MAP-Elites** discretises a behaviour-descriptor space into a grid and keeps the
  best individual per cell, producing a collection that is simultaneously
  high-performing and maximally different.
  <https://www.emergentmind.com/topics/map-elites-algorithm>
- **Rainbow Teaming** and successors showed quality-diversity works on LLM prompt
  generation at scale. <https://arxiv.org/pdf/2504.15047>
- **OpenEvolve** combines MAP-Elites with an **island model**: islands evolve
  semi-independently, each with its own feature grid and cell-elitist replacement.
  <https://pypi.org/project/openevolve/>
- **ShinkaEvolve** (Sakana, ICLR 2026) contributes the three mechanisms worth
  copying: **adaptive parent sampling** over the archive, **novelty-based rejection
  filtering** that rejects candidates too similar to existing archive members
  *before* paying to evaluate them, and a **bandit-based model ensemble** that learns
  which model suits which mutation. Framed explicitly as fixing AlphaEvolve's
  brute-force sample inefficiency.
  <https://arxiv.org/pdf/2509.19349> · <https://github.com/SakanaAI/shinkaevolve>

This is diversity machinery rather than optimisation machinery, so it works on weak
fitness signals — which is exactly our situation (F2).

**Design consequence:** archive coverage becomes a monotone progress metric, and
"we already have an idea like that" becomes a *structural fact* rather than a
judgment call. Novelty-rejection before evaluation is also the largest single cost
saving in the system.

---

## Part IV — Judging, and the limits of judging

### F19. Pairwise beats absolute scoring, especially here

- Pairwise verdicts agree with human preference more reliably than absolute scores,
  and **the gap widens on subjective dimensions** — maximally in our domain. In the
  weak-judge regime, pairwise-derived rankings substantially outperform direct
  scoring. <https://arxiv.org/pdf/2411.14483> · <https://arxiv.org/html/2606.09409v1>
- The choice of rating algorithm barely matters: Bradley-Terry, Elo, Glicko and
  win-rate agree at Spearman rho 0.944-0.953, Kendall tau 0.820-0.852. **Choosing
  pairwise at all is what matters.**
- **Conformal Elo** yields calibrated intervals, so a 12-point gap is not presented
  as a real ranking. <https://arxiv.org/pdf/2606.13221>

**Design consequence:** never ask for "rate this idea 1-10". Swiss-style pairwise
tournament, randomised pairings, Bradley-Terry fit, rank by **lower confidence
bound** so under-compared ideas do not top the board.

### F20. Judge biases are large enough to become the ranking

- **Self-preference bias ~10-25%.** Never let the same model judge and generate.
  <https://arxiv.org/pdf/2410.21819>
- **Verbosity bias: 15-30 points** of inflated preference for longer answers, across
  GPT-4, Claude and PaLM-2. Unless ideas are length-normalised to a fixed template,
  **verbosity is the ranking.**
- **Position bias** is real and partially fixable by content swapping and averaging.
  <https://aclanthology.org/2025.ijcnlp-long.18.pdf>
- A 2026 RAND study found no judge uniformly reliable across benchmarks; frontier
  models exceeded 50% error on hard bias benchmarks.
- *"When the Judge Changes, So Does the Measurement"* (2026): scores move when only
  the evaluator changes. Judge upgrades are **not interchangeable**. Stronger judges
  reduce but do not remove position and verbosity bias. Critically, **repeated
  samples from one judge add little when errors are correlated.**
  <https://arxiv.org/abs/2607.08535>
- *"Who Drifted: the System or the Judge?"* gives anytime-valid attribution —
  essential for an always-on system, where you otherwise cannot tell whether the
  ideas got worse or the judge shifted. <https://arxiv.org/pdf/2606.15474>

### F21. Juries help only when errors are uncorrelated

Cohere's **Panel of LLM Evaluators**: several *smaller* models from **disjoint model
families** outperformed a single large judge across 3 judge settings and 6 datasets,
with less intra-model bias at **more than 7x lower cost**.
<https://arxiv.org/abs/2404.18796>

Held against F20: a "jury" of five personas of one model is one judge wearing hats.
Diversity must be across model families.

### F22. Rubrics: binary checklists, decomposed, form-filling order

Decomposition into explicit dimensions measurably improves agreement. Recursive
rubric decomposition splits coarse rubrics into finer ones while filtering redundant
criteria; G-Eval-style form-filling forces the judge to reason through each
dimension before emitting a score.
<https://arxiv.org/pdf/2603.25133> · <https://arxiv.org/html/2606.00093>

Prefer **binary** items: "does this name a specific user with a specific trigger
moment? Y/N" beats "rate specificity 1-5", because binary items are auditable and
do not drift.

### F23. Prover-Verifier Games — how to harden the rubric against persuasion

Alternate **helpful** provers (correct and convincing) with **sneaky** provers
(incorrect and convincing) against a weaker verifier. Measured: verifiers become
more robust to sneaky solutions over rounds, helpful outputs become more legible,
and **legibility to small models transfers to legibility to humans**.
<https://arxiv.org/html/2407.13692v1>

**Design consequence:** run a **sneaky advocate** agent whose job is the most
compelling possible pitch for a deliberately bad idea. Its successes become hard
negatives that harden the rubric. This is the best available defence against the
ranker being gamed by persuasive prose.

### F24. Reward hacking is the failure mode of a closed loop

Agents learn to trigger false positives via deceptive formatting and misleading
calculations; models satisfy proxy criteria while evading intent. **Smaller judge
models are highly vulnerable to systematic manipulation.** The **sycophancy
bottleneck** arises whenever a weaker model evaluates a stronger one.
<https://arxiv.org/html/2604.13602v1> · <https://arxiv.org/pdf/2604.15149> · <https://arxiv.org/html/2605.02964v1>

**Design consequence, stated as a hard rule:** any agent whose output is scored must
never influence the scorer, and the scorer must be at least as strong as the
generator. Closing the loop — letting generators learn from scores — without
external grounding and a human gate builds a reward-hacking machine.

Related: meta-optimising the pipeline against an LLM judge (ADAS-style scaffold
search, <https://openreview.net/pdf?id=D01WR1yVW2>) is textbook reward hacking. Use
it only against objectively verifiable components: dedup precision, retrieval
recall, cost per idea, archive coverage. Never against "idea quality".

### F25. The ideation-execution gap — the result that should shape the whole scorer

- Si, Yang & Hashimoto: 49 expert idea writers, 79 blind reviewers. LLM ideas were
  rated **more novel than experts' ideas**. <https://arxiv.org/abs/2409.04109>
- The follow-up executed those ideas: 43 experts, **100+ hours each**, turning
  randomly assigned ideas into 4-page papers. After execution, **LLM ideas' scores
  dropped significantly more than human ideas on every metric** — novelty,
  excitement, effectiveness, overall (p < 0.05) — closing and on several metrics
  **flipping** the ranking. Execution reviewers weighted empirical performance,
  rigour, feasibility and resource requirements; ideation reviewers did not.
  <https://arxiv.org/abs/2506.20803>

**Design consequence:** "novel-sounding" is a cheap, measurable property that LLMs
are already superhuman at. "Actually good" is not measurable at ideation time. The
scorer must therefore be **two-headed** — grounded novelty and grounded
feasibility/value — and the two heads must never be collapsed into one number,
because the gap lives exactly in that collapse.

### F26. Grounded novelty assessment has a working recipe

The **Idea Novelty Checker** pipeline: broad retrieval (keyword + snippet +
similar-to-seed) -> embedding similarity filter -> **facet-based re-ranker**
comparing *(purpose, mechanism, evaluation, application)* against retrieved prior
work -> expert-annotated in-context examples anchoring novel vs not-novel ->
literature-grounded rationale. Measured **~13% higher agreement** with expert
novelty judgments than prior approaches.
<https://arxiv.org/abs/2506.22026>

Ported to consumer apps, the facets become *(who / trigger moment / mechanism /
distribution / monetisation)* and the corpus becomes app stores, launch boards,
funding records and complaint threads. A novelty claim with no retrieved
counterexamples is auditable; a model asserting "this is novel" is not.

### F27. There is real signal in model judgment of ventures, and a hard ceiling on it

- **VCBench**: 9,000 anonymised founder profiles, 810 labelled successful. Of nine
  frontier models, the best delivered **over 6x baseline precision**, and most models
  **beat the human benchmark**. <https://arxiv.org/abs/2509.14448>
- **PHBench**: 67,292 featured Product Hunt posts (2019-2025) domain-matched to
  funding records — 47,071 train / 6,753 validation / 13,468 test (test labels
  private) — yielding 528 verified Series A raises within 18 months. Base rate
  **0.78%**. Best ensemble: F0.5 = 0.097, average precision 0.037, a **4.7x lift
  over random**. Train and validation labels are publicly available, CC BY 4.0.
  <https://arxiv.org/abs/2605.02974> · <https://github.com/ihlamury/phbench>
  (Licence restriction to respect: the dataset may not be used to target or solicit
  specific companies or individuals.)
- **SSFF** and **R.A.I.S.E.** are multi-agent VC-analyst frameworks; SSFF reports
  founder-level effects. <https://arxiv.org/abs/2405.19456> · <https://arxiv.org/pdf/2504.12090>

Read together: the signal is real and beats humans, *and* a 4.7x lift on a 0.78%
base rate is still roughly a 4% hit rate.

**Design consequence:** the honest deliverable is **lift over base rate** plus the
cheapest decisive test — never a verdict. And because labelled historical splits
exist publicly, the scoring function can be **backtested rather than vibed**.

### F28. Forecast the idea, then score the forecaster

- An ensemble of **12 models** on 31 binary questions beat a no-information
  benchmark and was **statistically indistinguishable from 925 human forecasters**
  over a three-month tournament.
  <https://www.science.org/doi/full/10.1126/sciadv.adp1528>
- Elite humans still win: superforecaster Brier **0.096**, general public **0.121**,
  best model **0.122**.
- Model predictions improve **17-28%** when shown the median human prediction;
  simple human-plus-machine averaging beats either alone.
- On prediction markets, models profit largely by **losing less when wrong**, and
  **within-crowd agreement works as a confidence filter**.

**Design consequence:** convert each surviving idea into 3-5 falsifiable binary
forecasts with resolution dates, forecast them with a heterogeneous ensemble, and
**track the system's own Brier score over time**. That yields the one thing no
rubric can: a scoring function that is eventually scored itself. Use within-crowd
agreement as the confidence gate.

### F29. The closest existing system, and its flaw

Google's **AI co-scientist** runs generate -> reflect -> rank -> evolve with
specialist agents: generation (literature exploration plus simulated debate),
reflection (peer reviewer: correctness, quality, novelty), **ranking via Elo
tournament**, **proximity** (finds similar hypotheses to avoid redundancy),
evolution (refines survivors), and meta-review (synthesises cross-agent feedback
back into generation).
<https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/>
<https://www.nature.com/articles/s41586-026-10644-y>

Two skeptical flags. Its "quality improves with more compute" curve is largely
**self-rated Elo** — the system grading its own homework, exactly the F24 setup. And
its Nature-published wins are in wet-lab domains where hypotheses were
**externally validated**.

**Design consequence:** copy the org chart; do not copy the self-rated progress
metric. Our equivalent of the wet lab is a landing-page test. Without it, rising
internal Elo means only that the ranker has learned to like the generator.

---

## Part V — Cost and operations

### F30. You are paying to read, not to write

- Manus report a ~**100:1 input-to-output ratio**, making **KV-cache hit rate the
  single most important production metric**. Consequences: never mutate the prompt
  prefix, **never dynamically add or remove tools** mid-run (mask logits instead),
  keep context append-only, use the filesystem as unlimited context, and
  deliberately keep failures in context so the model does not repeat them.
  <https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus>
- **Prompt caching**: cache reads at ~0.1x base input price. Break-even after 1 hit
  on the 5-minute TTL, 2 hits on the 1-hour TTL.
- **Batch API**: flat 50% off, results within 24 hours. **Stacks with caching for up
  to ~95% off input.** Generation and first-pass scoring are not latency-sensitive
  and belong in batch. This is the largest single lever for an always-on system.
- **Model routing**: production reports 40-70% savings; ICLR 2025 work cut cost 85%
  while retaining 95% of strong-model quality with only 14% of queries escalated.
  But the same sources note that below roughly $200/month of spend the routing layer
  costs more engineering time than it saves. **Do not build the router first.**
- Anthropic's own most actionable line: *"upgrading to Sonnet 4 is a larger gain
  than doubling the token budget on Sonnet 3.7"* — **spend on model quality before
  spending on more agents.**

Note the tension with F20/F24: route generation aggressively, never route judging.

### F31. Durability for an always-on system

Checkpoint and resume, graceful tool-failure degradation (tell the agent the tool
failed and let it adapt, wrapped in deterministic retries), and **rainbow
deployments** so prompt changes do not kill in-flight runs. Durable-execution
options: LangGraph checkpointers inside the framework; Temporal, Inngest, DBOS or
Restate around it. The always-on agent survey catalogues the failure modes to expect:
catastrophic forgetting, context degradation, and **memory poisoning**.
<https://arxiv.org/pdf/2606.30306>

---

---

## Part VI — Mechanisms to copy verbatim

### F32. Evaluation cascade: never pay full price for a bad candidate

AlphaEvolve's stated rule: "new solutions are evaluated on the next stage only if
they achieve sufficiently promising results in all earlier stages. Moreover, new
solutions are initially evaluated on a small scale before being subjected to the
main test cases, to filter out faulty programs early." Top-of-cascade evaluation can
cost on the order of 100 compute-hours per candidate — affordable only because
almost nothing reaches it. Model ensemble by role: a fast cheap model for breadth, a
strong model for occasional depth. The pipeline is "optimized for throughput (rather
than the speed of any one particular computation)".

This is the direct justification for the oracle ladder's cost-monotonicity
invariant.

### F33. Bounded mutation operators

AlphaEvolve mutates by emitting **diff blocks** (search/replace), not whole
rewrites. This bounds edit size, keeps output parseable, and — the part that matters
for us — keeps offspring near their parents so archive coordinates stay meaningful.
Unbounded rewrites destroy lineage.

**Design consequence:** variation operators change one slot at a time and must
return a structured slot delta, never a fresh idea.

### F34. Heterogeneous model pools measurably beat single-model pools

A mixed rollout pool across four model families reached **74.55 pass@4** against
single-model baselines on the same budget.
<https://arxiv.org/pdf/2506.12928>

Combined with F6 (heterogeneity is the only debate intervention that reliably
helps) and F21 (juries need uncorrelated errors), this is now three independent
lines of evidence for the same rule: **mix model families wherever selection or
critique happens.** Where only one family is available, say so and treat the jury as
a single judge with variance, not as independent votes.

### F35. Entropy collapse is a real cost of optimising against a verifier

Goedel-Prover-V2 lists **model averaging** as one of three core ingredients,
specifically "to mitigate the decrease in model output diversity in later stages of
training". Optimising against a verifier collapses output diversity, and collapsed
diversity destroys pass@k.

**Design consequence:** any component we tune against our own scorer — operator
weights, prompt templates, archive pressure — needs an explicit diversity floor and
a monitored diversity metric, or the search will quietly converge on whatever the
scorer likes. This is the same hazard as F24 from a different direction.

### F36. Provenance is an engineering requirement, not a courtesy

Three separate incidents in the current record: the October 2025 Erdos
rediscovery misrepresentation; the criticism of the Erdos #90 proof for failing to
credit prior work (called "professional malpractice" if a human had done it); and
the unresolved question of whether private Codex drafts influenced the
Navier-Stokes model. Kosmos's 82.1% literature-statement accuracy with full
citations is the standard to beat.

**Design consequence:** log retrieval provenance per claim, and be able to answer
"where did this idea enter the system". This is already why every Signal requires a
`source_url` and every genome slot carries provenance (F17), but it is worth stating
as its own requirement: the system must be auditable about origin, not just about
score.

### F37. Long runs need resumption, not restarts

Anthropic's production notes: resume from where the agent was when errors occurred;
persist the plan to external memory because context truncates; full tracing of
decision patterns; **rainbow deployments** so prompt changes do not kill in-flight
runs; surface tool errors to the agent so it can adapt, wrapped in deterministic
retries. Their evaluation guidance is equally practical: a **single LLM judge call
outputting a 0.0-1.0 score plus a pass/fail grade** was the most consistent and
human-aligned, and "start with small-scale testing right away with a few examples" —
around 20 cases.

At 88-hour run lengths, restart-from-scratch is not a recovery strategy.

## What this evidence rules out

| Tempting design | Why the evidence rejects it |
|---|---|
| Thousands of agents deliberating | F3 (diversity falls 1.03 -> 0.47), F7 (17x error amplification), F8 ("mostly a distraction") |
| "Think like a genius" personas | F14 (visionary personas score 50.40 vs ordinary 56.97) |
| Agents arguing to refine ideas | F6 (0/5 debate methods beat CoT in 36 configs), F15 (generate independently first) |
| Persona diversity as diversity | F21 (juries help only with uncorrelated errors), F3 (echo chamber) |
| Clever creativity prompting | F12 (barely shifts the frontier), F13 (the one exception, and it only undoes collapse) |
| Weighted-sum 0-100 score | F11 (harmonic gating), F25 (two heads must not be collapsed) |
| Rating ideas 1-10 | F19 (pairwise wins, and wins by more on subjective dimensions) |
| Self-rated Elo as progress | F24 (reward hacking), F29 (the co-scientist's own weak spot) |
| Tree-of-thought as default | Diminishing returns past 2-3 branches; an archive gives the same breadth with reusable state |
| TRIZ / SCAMPER prompting | F16 (no controlled measurement; analogical transfer has numbers) |
| AlphaEvolve-grade results on ideas | F1, F2 (every evolutionary win had a cheap exact verifier) |
