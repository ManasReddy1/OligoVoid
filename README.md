# OligoVoid — siRNA Modification Design Space Intelligence

OligoVoid systematically maps the untested regions of the siRNA chemical modification design space. It parses published modification patterns, builds position-specific co-occurrence matrices, detects research voids, scores them for biophysical feasibility, and uses active learning to suggest which void to test next.

## Quick Start

```bash
cd oligovoid
pip install -r backend/requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY for Claude scoring
uvicorn backend.main:app --reload
```

Open http://localhost:8000

## Architecture

| Module | Purpose |
|---|---|
| `modification_grammar.py` | Core ontology: 7 sugar mods, 3 backbone mods, 42 positions, biophysics rules |
| `literature_parser.py` | Ingests published siRNA data, builds frequency + co-occurrence matrices |
| `void_detector.py` | Scans co-occurrence matrix for under-tested pairs |
| `feasibility_scorer.py` | Dual scoring: deterministic biophysics rules + Claude LLM reasoning |
| `active_learner.py` | DMTL loop: uncertainty-weighted acquisition function for experiment prioritization |
| `velocity_tracker.py` | Void Closure Velocity: tracks how fast each gap is being filled |
| `database.py` | SQLAlchemy models for SQLite persistence |
| `main.py` | FastAPI with 20+ API endpoints |

## Design Space

- 42 nucleotide positions (21 guide + 21 passenger)
- 7 sugar modifications per position = 294 position-sugar assignments
- C(294, 2) = 43,071 unique co-occurrence pairs to scan
- Published literature covers ~2% of this space
- 12 FDA-approved/clinical siRNAs pre-loaded as seed data

## Key Concepts

- **Void**: A (position:mod, position:mod) pair observed fewer than 3 times in published siRNAs
- **Feasibility Score**: Biophysics rule engine (seed region, cleavage site, PS toxicity constraints)
- **Claude Score**: LLM-based contextual reasoning about mechanistic compatibility
- **Information Gain**: Active learning metric combining uncertainty, novelty, and score disagreement
- **Closure Velocity**: Rate at which each void is being filled by the field (obs/year)
- **DMTL Cycle**: Design-Make-Test-Learn loop tracking experimental suggestions and outcomes
