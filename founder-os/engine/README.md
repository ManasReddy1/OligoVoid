# Founder OS engine

A working implementation of the oracle ladder in `../docs/02-architecture.md`.

**No third-party dependencies.** Standard library only, SQLite for state. It runs
on any Python 3.11+ with nothing installed, which matters more than elegance for
something meant to run nightly on a cheap box.

## Run a cycle

```bash
python3 run.py load                  # harvested evidence -> world model
python3 run.py cycle                 # advance as far as it can
python3 run.py pending               # prompts waiting on an answer
python3 run.py report out.html       # render the current cycle
```

With `ANTHROPIC_API_KEY` set, `cycle` runs end to end. Without it, the file
backend writes every prompt to `work/prompts/` and stops; write the answers to
`work/responses/<task_id>.json` as `{"parsed": <json>}` and run `cycle` again.
That is not a fallback, it is the design: any agent can serve as the model layer,
and a cycle is resumable at every stage.

## Verify it works

```bash
python3 selftest.py
```

Runs the whole ladder on synthetic model output with no network and no key, and
asserts that each gate actually kills something, that both score heads are
produced, that pairs are judged in both orders, and that a report renders.

## Modules

| File | Does |
|---|---|
| `genome.py` | Idea genome, slot vocabularies, gate L0 validity rules |
| `store.py` | The world model. One SQLite file, written only by the orchestrator |
| `similarity.py` | IDF-weighted lexical distance and the slot-level Hamming analogue |
| `voidmap.py` | Occupancy grid, void classification, revival candidates |
| `gates.py` | L1 obviousness, L2 grounding, L3 buildability, L4 panel scoring |
| `scoring.py` | Harmonic composites. The score gates, it does not average |
| `tournament.py` | Bradley-Terry with a bootstrap lower confidence bound |
| `prompts.py` | The generation envelope and every prompt in the ladder |
| `llm.py` | Model backends and the cost governor |
| `orchestrator.py` | The cycle driver, island theses, ledgers, stall counter |
| `report.py` | Renders a cycle to standalone HTML |

## Things worth knowing before you change it

**The obviousness threshold calibrates itself.** The absolute scale of a lexical
similarity depends on corpus size and vocabulary, so a hand-set constant is
meaningless across runs. The invariant is the design target: gate L1 exists to
kill roughly 30% of what reaches it.

**Gates are recorded once per idea.** Re-running a resumed cycle must not
re-screen. An earlier version recalibrated the threshold against whoever was
left on every pass, and ate the whole population in four rounds.

**Similarity is lexical, not semantic.** It over-rewards ideas that say the same
thing in different words. Swapping in a real embedding model is a one-function
change: replace `Index.vec`.

**Nothing here is calibrated against real outcomes yet.** That is phase 6 of the
build plan and it is what separates a measured scoring function from a confident
one.
