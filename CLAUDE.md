# CLAUDE.md — Project Context for OligoVoid

This file explains OligoVoid to any developer, AI assistant, or contributor who needs to understand the project from scratch.

---

## One-sentence summary

OligoVoid is a research intelligence tool that systematically maps which chemical modification patterns for siRNA drugs have been tested in published literature and which haven't, then scores the untested patterns for biophysical feasibility and recommends which to test next using active learning.

---

## The science in plain English

### What is siRNA?

siRNA (small interfering RNA) is a class of drug that silences disease-causing genes. It's a short molecule — 21 nucleotides long — made of two strands:

- **Guide strand** (antisense): binds to the target mRNA and silences it
- **Passenger strand** (sense): gets discarded after the guide is loaded into the RISC complex (Argonaute protein)

### Why chemical modifications matter

Unmodified RNA is destroyed in seconds by enzymes (nucleases) in the human body. To make siRNA drugs work, researchers chemically modify specific positions on both strands. These modifications:

- Protect against nuclease degradation (so the drug survives in blood)
- Help the drug enter cells (uptake)
- Ensure the guide strand loads into RISC correctly (activity)
- Reduce off-target gene silencing (safety)

### The modification space

Each of the 42 positions (21 per strand) can have one of 8 sugar modifications. The backbone between positions can be natural (PO) or modified (PS, MsPA). A conjugate molecule (GalNAc, cholesterol, etc.) can be attached to help delivery.

### What OligoVoid found

From 60 curated published patterns (including all 8 FDA-approved siRNA drugs), OligoVoid determined that roughly 45% of feasible position × modification combinations have been explored. The remaining 55% — the "voids" — are untested but potentially viable.

---

## Codebase overview

### Backend modules (in order of dependency)

1. **`modification_grammar.py`** — The foundation. Contains:
   - `SUGAR_MODIFICATIONS` dict: 8 entries with biophysical properties (RISC tolerance, nuclease resistance, ΔTm contribution, seed/cleavage safety flags)
   - `BACKBONE_MODIFICATIONS` dict: 3 entries (PO, PS, MsPA)
   - `TERMINAL_CONJUGATES` dict: 4 entries with tissue targeting info
   - `SiRNAModificationPattern` class: represents a 21-position duplex with guide/passenger modifications, backbone, and conjugate
   - 10 biophysics rules (cleavage site rigidity, seed overload, excessive LNA, etc.)
   - 5 known patterns (Inclisiran, Patisiran, Givosiran, Reynolds standard, Khvorova stabilized)
   - `enumerate_all_feasible_patterns()`: generates ~220 template patterns
   - Coverage analysis: 336 position-mod combinations, 18.5% covered by the 5 base patterns

2. **`literature_parser.py`** — Curated data layer. Contains:
   - `PUBLISHED_MODIFICATIONS_DATASET`: 60 real-world siRNA patterns with modification details, knockdown efficacy, source citations, year
   - `build_position_cooccurrence_matrix()`: counts how many times each modification appears at each position across all known patterns
   - `get_position_coverage_stats()`: 151/336 combinations tested (44.9%), identifies void positions
   - `search_pubmed_for_pattern()`: async PubMed E-utilities query for finding papers about specific modification combinations

3. **`void_detector.py`** — Enumeration engine. Contains:
   - `enumerate_modification_voids()`: takes each known pattern, generates all 1/2/3-position variants, filters biologically invalid ones → 2,397 candidates
   - `calculate_hamming_to_nearest()`: position-wise comparison to find closest known pattern
   - `get_void_novelty_score()`: 0-100 score based on Hamming distance + neighborhood density + modification rarity
   - `classify_void_type()`: categorizes as conservative_variant (1,400), chemistry_hybrid (643), regional_explorer (276), or modification_pioneer (78)

4. **`feasibility_scorer.py`** — Scoring engine. Two layers:
   - **Rule-based biophysics** (always available):
     - `calculate_thermodynamic_score()`: ΔTm prediction, optimal +5 to +15°C window
     - `calculate_risc_loading_score()`: seed region penalties, cleavage site checks
     - `calculate_nuclease_resistance_score()`: backbone and sugar protection
     - `calculate_off_target_risk_score()`: passenger seed mods, immunogenicity
     - Weighted composite: 35% RISC + 25% nuclease + 20% thermo + 20% off-target
   - **Claude API enhanced** (optional, requires API key):
     - Sends pattern + biophysics scores to Claude Sonnet
     - Gets back: predicted knockdown %, one-line insight, key risk, recommended experiment, field readiness
     - Graceful fallback when API key not configured

5. **`active_learner.py`** — DMTL engine. Contains:
   - `ActiveLearner` class with:
     - `_compute_uncertainty()`: 3-component epistemic uncertainty (Hamming distance, position rarity, neighborhood sparsity)
     - `_compute_expected_improvement()`: EI over target knockdown
     - `_compute_diversity_bonus()`: prevents recommending similar patterns
     - `recommend_next_experiment()`: 4 acquisition functions (balanced, uncertainty, exploitation, exploration)
     - `simulate_dmtl_cycle()`: full simulation starting from N known patterns
     - `get_exploration_coverage()`: 8-subregion coverage analysis
   - `run_dmtl_demo()`: standalone async function for dashboard

6. **`velocity_tracker.py`** — Publication trend tracking (simulated data for proof of concept)

7. **`database.py`** — SQLAlchemy models:
   - `KnownSiRNA`: published patterns with drug names, citations
   - `ModificationVoid`: enumerated voids with Hamming distances
   - `VoidFeasibilityScore`: biophysics + Claude scores
   - `VoidClosureVelocity`: paper counts per time window
   - `DMTLCycleLog`: active learning cycle records
   - `CommunityResult`: user-submitted validation results

8. **`main.py`** — FastAPI app with 11 endpoints, CORS middleware, static file serving

### Frontend

- `index.html`: 5-tab SPA (Modification Map, Top Voids, DMTL Cycles, Velocity, Custom Scorer)
- `styles.css`: ~830 lines, bioluminescent dark theme (#0d0f14 background, #00ff88 green accent, Space Mono + Inter fonts)
- `app.js`: ~730 lines, all API integration, heatmap rendering, score bar animation, DMTL canvas chart

---

## Key design decisions

1. **Vanilla JS frontend** — No React/Vue. This is a research tool, not a product. Fewer dependencies = easier to run anywhere.

2. **Rule-based scoring as the default** — The biophysics scorer works without any API key. Claude API is an optional enhancement layer, not a dependency.

3. **3-position-change limit for void enumeration** — Balances coverage (2,397 candidates) with computational feasibility. 4+ changes would generate millions of patterns, most trivially different from each other.

4. **Curated dataset over automated extraction** — 60 hand-curated patterns with verified modification details are more reliable than NLP-extracted data with potential errors. The dataset is small but accurate.

5. **Weighted RISC loading as the dominant score component (35%)** — RISC loading is the most critical bottleneck. A pattern with perfect stability but no RISC loading is useless. This weighting reflects biological reality.

---

## Running tests

```bash
cd backend

# Test biophysics scoring
python -c "
from feasibility_scorer import score_pattern_biophysics
from modification_grammar import KNOWN_PATTERNS
result = score_pattern_biophysics(KNOWN_PATTERNS[0])
print(result)
"

# Test void enumeration
python -c "
from void_detector import enumerate_modification_voids
from modification_grammar import KNOWN_PATTERNS
voids = enumerate_modification_voids(KNOWN_PATTERNS, max_positions_changed=2)
print(f'{len(voids)} voids found')
"

# Test DMTL simulation
python -c "
import asyncio
from active_learner import run_dmtl_demo
result = asyncio.run(run_dmtl_demo(n_cycles=5))
print(f'Uncertainty: {result[\"summary\"][\"start_uncertainty\"]:.3f} → {result[\"summary\"][\"end_uncertainty\"]:.3f}')
"

# Start server
uvicorn main:app --reload --port 8000
```

---

## Common tasks

### Add a new known pattern
Edit `modification_grammar.py`, add to the `KNOWN_PATTERNS` list following the existing format. Then re-run `seed_known_patterns()` to update the database.

### Change scoring weights
Edit `feasibility_scorer.py`, find the `score_pattern_biophysics()` function. The weights are: `thermo * 0.20 + risc * 0.35 + nuclease * 0.25 + off_target_display * 0.20`.

### Add a new modification type
Add to `SUGAR_MODIFICATIONS` in `modification_grammar.py` with all required properties (risc_tolerance, nuclease_resistance, binding_affinity_delta_tm, seed_region_safe, cleavage_site_safe). Update the abbreviation map. The rest of the system picks it up automatically.

### Run Claude API scoring
Set `ANTHROPIC_API_KEY` in `.env`. The scorer will automatically use Claude for enhanced analysis when scoring voids via the API.

---

## Environment

- Python 3.9+
- Key dependencies: fastapi, uvicorn, sqlalchemy, httpx, anthropic, numpy, scipy, pandas
- Database: SQLite (zero-config, file-based at `data/oligovoid.db`)
- No build step for frontend — static files served by FastAPI
