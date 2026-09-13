# Data schema and agent contracts

Concrete enough to implement directly. Mirrors the conventions already used in
`backend/database.py` (SQLAlchemy + SQLite, file-based, zero-config).

## Tables

### `signals` — the evidence store (L1)

| Column | Type | Notes |
|---|---|---|
| `id` | int pk | |
| `kind` | enum | `UNLOCK` `PAIN` `DEMAND` `SHIFT` `TOMBSTONE` `PROBE_RESULT` |
| `title` | str | one line |
| `body` | text | normalised payload, includes verbatim quote for PAIN |
| `payload` | json | kind-specific required fields (see architecture §2) |
| `source_url` | str | **not null** — no citation, no row |
| `source_name` | str | harvester id |
| `observed_at` | datetime | |
| `dated_at` | datetime | the date the *fact* belongs to, for clock-freezing |
| `confidence` | float | 0-1 |
| `embedding` | blob | for retrieval and distance |

### `products` — the occupancy corpus (L2)

| Column | Type | Notes |
|---|---|---|
| `id` | int pk | |
| `name` `url` `category` | str | |
| `status` | enum | `shipped` `funded` `dead` |
| `launched_at` `died_at` | datetime | nullable |
| `genome` | json | projected into the same 9 slots |
| `death_cause` | text | for `dead`, feeds TOMBSTONE |
| `metrics` | json | downloads, revenue, funding where known |
| `embedding` | blob | |

### `ideas` — the population

| Column | Type | Notes |
|---|---|---|
| `id` | int pk | |
| `genome` | json | the 9 slots, each `{value, provenance, signal_ids}` |
| `descriptor` | str | archive cell key: `unlock|pain|audience|mechanic` |
| `island` | int | |
| `generation` | int | |
| `parent_ids` | json | lineage |
| `operator` | str | which of the six/three operators produced it |
| `status` | enum | `alive` `killed` `shortlisted` `probing` `validated` `rejected` |
| `killed_at_gate` | str | nullable: `L0`...`L4` |
| `kill_reason` | text | |
| `token_cost` | int | |

### `gate_verdicts` — one row per idea per gate

| Column | Type | Notes |
|---|---|---|
| `idea_id` | fk | |
| `gate` | str | `L0`-`L5` |
| `passed` | bool | |
| `score` | float | gate-local |
| `detail` | json | sub-scores, attack transcripts, citations checked |
| `model` | str | which model tier ran it |
| `cost_tokens` | int | |

### `scores` — the composite

| Column | Type | Notes |
|---|---|---|
| `idea_id` | fk | |
| `originality` `quality` `novelty` | float | novelty = harmonic(originality, quality) |
| `buildability` `unit_economics` `distribution` `viability` | float | viability = harmonic of the three |
| `timing` | float | from capability-curve proximity |
| `survival_multiplier` | float | fraction of L4 attacks survived |
| `founder_score` | float | 0-100, harmonic composite |
| `elo` | float | from L5 pairwise tournament |
| `weights_version` | str | which calibration produced it |

### `probes` — reality contact (L7)

| Column | Type | Notes |
|---|---|---|
| `idea_id` | fk | |
| `kind` | enum | landing, ad_ab, community, concierge, fake_door |
| `hypothesis` | text | pre-registered, with the number that would falsify it |
| `budget_usd` | float | |
| `approved_by_human` | bool | **required before any spend** |
| `result` | json | |
| `verdict` | enum | `supported` `refuted` `inconclusive` |

### `cycles` — the run ledger

`id`, `started_at`, `finished_at`, `config` json, `budget_usd`, `spent_usd`,
`ideas_generated`, `ideas_survived`, `halted_reason`, `weights_version`.

### `calibrations` — backtest results

`id`, `cut_date`, `dataset`, `weights` json, `lift_over_base_rate`,
`ranking_auc`, `notes`.

## Agent contract

Every agent is a pure function with a declared envelope. No agent calls another
agent; the orchestrator is the only writer.

```
AgentCall:
  agent_id:      str
  model_tier:    "cheap" | "strong"     # routed, never hardcoded to a model name
  input_schema:  json-schema            # validated before dispatch
  output_schema: json-schema            # validated on return; 1 retry, then drop
  token_ceiling: int
  cache_prefix:  str                    # shared evidence context, cached across calls
  requires_citations: bool              # if true, uncited output fields are stripped
```

Outputs are always structured. Free-text hand-offs between stages are forbidden —
that is the documented origin of most multi-agent failure (finding F9).

## Module layout

```
founder-os/
  docs/                      01-research-findings, 02-architecture, 03-schema-and-contracts
  genome.py                  slot vocabularies, IdeaGenome, descriptor, validity rules (L0)
  store.py                   SQLAlchemy models above
  orchestrator.py            cycle driver, scheduler, checkpointing, single-writer state
  budget.py                  cost governor, model routing, metering, halt
  harvesters/                one module per source; all idempotent, all cite
  normalize.py               raw item -> typed Signal, or discard
  voidmap.py                 occupancy matrix, void classification, distances
  genesis/                   the six genius operators + three variation operators
  archive.py                 MAP-Elites archive + island model + migration
  gates/                     l0_validity, l1_obviousness, l2_grounding,
                             l3_buildability, l4_adversarial, l5_elo
  scoring.py                 harmonic composites, weights_version
  calibrate.py               clock-freeze backtest, weight fitting, lift reporting
  probes.py                  probe design, human approval gate, result ingestion
  api.py                     FastAPI endpoints
  web/                       console: brief, dossiers, kill log, probe queue
```

Conventions follow the existing repo: FastAPI + SQLAlchemy + SQLite backend, vanilla
JS frontend with no build step, rule-based logic that runs with no API key and a
model-enhanced layer on top that degrades gracefully when keys are absent.
