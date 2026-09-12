# Running a cycle

Two ways to supply the model layer. The pipeline is identical either way.

## With an API key

```bash
cd founder-os/engine
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env && set -a && . ./.env && set +a
python3 run.py load
python3 run.py cycle --budget 6
python3 run.py report ../web/report.html
```

Runs start to finish unattended. The cost governor halts the cycle if the
budget cannot cover the next stage, and reports partial results rather than
overrunning.

## With an agent as the model layer, and no key

This is how the first cycle was actually run. The file backend writes every
prompt it needs to `work/prompts/` and stops; any agent that can read and write
files can serve as the model.

```bash
python3 run.py load
python3 run.py cycle --files-only --islands 6 --per-island 5 --panel 5
python3 run.py pending          # what is waiting
```

Then, for each pending prompt, an agent reads `work/prompts/<task_id>.json`,
follows its `system` and `user` fields, and writes

```json
{"parsed": <the JSON the prompt asked for>, "text": "", "usage": {}}
```

to `work/responses/<task_id>.json`. Run `cycle` again and it picks up.

**How to shard the work across agents.** The sharding is not arbitrary; it
preserves the isolation properties the gates depend on.

| Stage | Agents | Why that shape |
|---|---|---|
| Generation | one per island | Islands must not see each other's output. Independent generation before any contact is what protects diversity |
| Buildability | one for all | A pricing task with no isolation requirement |
| Adversarial panel | one per attack surface | Each attacker owns one surface across every idea, and never sees the generator's reasoning. Clean context is the whole point |
| Tournament | one per head | Novelty and viability are judged separately and never collapsed |
| Probe design | one for all | Three probes, one judgement call |

Roughly fourteen agent calls per cycle at this scale.

## Things that will bite you

**Changing a prompt changes its task id.** The id is a hash of the prompt text,
which is what makes responses cacheable and resumable. Edit `prompts.py`
mid-cycle and every outstanding answer is orphaned, because it answered a
different question. That is correct behaviour, and it is also how an
afternoon's work gets stranded. Finish the cycle, then edit.

**The same applies to flags.** `--per-island 5` and `--per-island 6` produce
different prompts, so resuming with different flags strands the answers too.
Resume with the flags you started with.

**Gates record once per idea.** Re-running a resumed cycle does not re-screen.
An earlier version recalibrated the obviousness threshold against whoever was
left on every pass and ate the whole population in four rounds.

**Watch the kill log, not just the survivors.** The first cycle killed seven
sound candidates because a deny rule for crypto matched the phrase
"million-token context" in their enabling capability. Nothing in the ranking
would have shown that. The kill log did.

## Recovering from a bad kill

Gates are auditable on purpose. To give wrongly-killed ideas a fair hearing:

```python
from store import Store
s = Store()
rows = [r for r in s.ideas(cycle_id=1)
        if r["status"] == "killed" and "<the bad reason>" in (r["kill_reason"] or "")]
for r in rows:
    s.db.execute("DELETE FROM verdicts WHERE idea_id=? AND gate IN ('L0','L1','L2')", (r["id"],))
    s.db.execute("UPDATE ideas SET status='alive', killed_at_gate=NULL, kill_reason=NULL WHERE id=?", (r["id"],))
s.db.commit()
```

Then fix the rule and run `cycle` again. Record what happened in the cycle's
progress ledger rather than fixing it silently.
