# Research findings: how frontier systems actually do open-ended discovery

> Evidence base for the Founder OS architecture. Every design decision in
> `02-architecture.md` traces back to a numbered finding here.

## F1. "10,000 agents" is the wrong mental model — and the right one is cheap

The headline framing (thousands of agents collaborating to crack an open problem)
describes **parallel search under a verifier**, not a large committee. The compute
goes into *many independent attempts that are automatically checked*, not into many
agents arguing about one attempt. Every system that has produced a genuinely new
result at scale shares the same skeleton:

```
propose  ->  verify (cheap, automatic, adversarial)  ->  keep survivors  ->  mutate survivors
```

The verifier is the load-bearing component. Where a machine-checkable oracle exists
(a proof checker, a unit test, a numeric evaluation), massive parallelism converts
directly into discovery, because a wrong answer costs nothing to discard. Where no
oracle exists, parallelism amplifies noise and cost instead of insight.

**Design consequence:** the hardest part of this system is not the agents. It is
manufacturing the best available oracle for "is this a good consumer app idea",
and being honest that it is a proxy.

## F2. Adding agents does not add novelty — it subtracts diversity

Chen & Zhang (2026), *Enhancing Research Idea Generation through Combinatorial
Innovation and Multi-Agent Iterative Search Strategies*, measured this directly
on research-idea generation:

| Team size | Uniqueness ratio | High-quality idea share |
|---|---|---|
| 2-3 | highest | ~0.20 |
| 4-7 | declining | ~0.25 (peak, stable) |
| 8 | lowest | ~0.20 (drops back) |

- Uniqueness **declines monotonically** as team size grows from 2 to 8, because all
  agents share one base model's priors. "Generating more content increases the
  likelihood of similarity."
- Novelty showed **no trend at all** with team size: "the proposed method cannot
  improve novelty by scaling up the number of agents."
- Quality peaks at 5-7 members and degrades at 8.

**Design consequence:** panels are capped at 5-7 agents. Extra compute buys more
*independent lineages* and more *iterations*, never a bigger committee.

## F3. Iterations beat headcount

Same study, varying iteration count instead of team size: diversity peaks at
iteration 2, novelty jumps sharply at iteration 2 with marginal gain at 3, and
high-quality share rises with every iteration. Where team size was flat, iteration
count moved every metric.

**Design consequence:** the unit of spend is a generation of the evolutionary loop,
not an agent seat. Budget is expressed in generations x population, not in agents.

## F4. Novelty comes from grounding, not from personas

The ablation in the same paper is the single most useful result for us. Setting the
agent count to 1 while keeping the knowledge-planning-and-retrieval module:

- Single agent **+ retrieval beat the full multi-agent system on diversity and novelty.**
  The retrieval/grounding module is what produces novelty, not the agent chorus.
- But the single agent **plateaued** over iterations, matching the earlier NOVA
  result, while the multi-agent system kept improving on every metric.
- Multi-agent's real contribution is **quality**, not novelty.

**Design consequence:** grounding is the novelty engine; the multi-agent panel is
the quality engine. Build both, and never expect a "think like a genius" system
prompt to do the work of an evidence layer.

## F5. Novelty must be scored as originality AND quality, joined harmonically

Padmakumar, Chen, Pan, Chen & He (ICLR 2026), *Measuring LLM Novelty as the
Frontier of Original and High-Quality Output*:

- Novelty is defined as the **harmonic mean** of originality (fraction of n-grams
  unseen in the training corpus) and a task-specific quality score. The harmonic
  mean is chosen deliberately "to penalize either originality or quality being low."
- Originality alone rewards rare garbage. Quality alone, judged by non-experts,
  rewards memorized text. Prior metrics that score only one dimension "would
  incorrectly rank rare but poor-quality output highly."
- LLM-as-judge quality was validated against three human annotators per item;
  inter-annotator agreement was Krippendorff's alpha 0.59-0.68 on creative tasks,
  which is the normal ceiling for creative judgment.

**Design consequence:** the final score is a harmonic/gated composite, not the
weighted sum the first-draft architecture implies. An idea that is wildly original
and unbuildable must score near zero, not 50.

## F6. Prompting for novelty does not work

Same paper, Section 4. Inference-time elicitation was tested directly:

- Raising sampling temperature has a **U-shaped** effect: originality rises, then
  quality collapses and takes novelty with it.
- Asking the model for novelty, denial prompting, and novel in-context examples
  "have a much smaller effect on novelty, often increasing originality at the
  expense of quality."
- What actually moves the novelty frontier is a better base model, scale, and
  post-training — none of which we control at inference time.

**Design consequence:** the "genius" agents cannot be personas. They must be
*mechanisms* with external inputs: a cost-curve tracker, a constraint analyser, an
analogy matrix over a real product corpus. Persona text is decoration on top of
the mechanism, not the source of the idea.

## F7. Novelty is atypical recombination of grounded entities, and provenance is measurable

The entity-recombination analysis in Chen & Zhang treats methods, tasks, datasets
and metrics as typed knowledge units, extracts them from each iteration, and traces
every entity to one of three sources: the previous idea, the retrieved literature,
or the model itself. Creative ideas "rarely emerge from entirely new inventions;
instead, they arise through atypical recombination of existing elements."

**Design consequence:** represent an idea as a typed slot vector over a grounded
vocabulary, and track the provenance of every slot. Slots sourced from evidence are
real; slots the model invented unprompted are the hallucination risk surface and
are penalised unless a harvester can later cite them.

## F8. There is real, measured signal in LLM judgment of ventures — and a hard ceiling on it

- **VCBench** (arXiv 2509.14448): 9,000 anonymised founder profiles, 810 labelled
  successful. Of nine frontier models evaluated, the best delivered **over 6x
  baseline precision**, and most models **beat the human benchmark** on
  founder-success prediction.
- **PHBench** (arXiv 2605.02974): 67,292 featured Product Hunt posts, 2019-2025,
  domain-matched to Crunchbase, yielding 528 verified Series A raises within 18
  months of launch. Base rate **0.78%**. The best ensemble reached F0.5 = 0.097 and
  average precision 0.037, a **4.7x lift over random**. Public train/val/blind-test
  splits, 61 engineered features, and a leaderboard exist.
- **SSFF** (arXiv 2405.19456) and **R.A.I.S.E.** (arXiv 2504.12090) are multi-agent
  VC-analyst frameworks; SSFF reports founder-level effects (L5 founders 3.79x more
  likely to succeed than L1).

Read these together: the signal is real and beats humans, *and* the absolute
numbers are brutal. A 4.7x lift on a 0.78% base rate is still a ~4% hit rate.

**Design consequence:** the system's honest job is **lift over the base rate**, not
certainty. Its output is a ranked shortlist with explicit kill conditions and a
cheap next test — never a verdict. And because PHBench ships labelled historical
splits, the scoring function can be **backtested instead of vibed**.

## F9. Naive multi-agent systems fail in characterised, avoidable ways

The practitioner literature converges on the same failure set: context loss between
agents, conflicting implicit assumptions, judges drifting toward agreement,
self-evaluation reward hacking, and unbounded cost. The recurring fix is not more
agents but: a single owner of shared state, explicit hand-off contracts, adversarial
rather than cooperative evaluation, and external grounding at every hop.

**Design consequence:** one orchestrator owns all state; agents are pure functions
over an explicit context object; every scoring step has an adversary; every claim
carries a citation; a cost governor can halt the run.
