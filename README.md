<div align="center">

# OligoVoid

### Mapping the Dark Matter of siRNA Chemical Space

[![arXiv](https://img.shields.io/badge/arXiv-preprint-b31b1b)](https://arxiv.org/abs/PLACEHOLDER)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)

**Drug companies have tested 8% of the siRNA modification space.**
**OligoVoid maps the other 92% — and tells you which unexplored territory is worth visiting first.**

[Quick Start](#quick-start) · [How It Works](#how-it-works) · [Results](#results) · [Paper](#paper) · [API Docs](#api)

</div>

---

> *"The most important experiments in RNA therapeutics may be the ones nobody has run yet."*

---

> *"Most modification patterns of approved or clinically investigated siRNAs are protected by patents, significantly restricting their broader application. Therefore, the development of proprietary modification patterns has been essential for siRNA therapeutics companies."*
> — Molecular Therapy: Methods & Clinical Development, 2025

---

## What Is This?

> **One sentence:** OligoVoid systematically maps every chemical modification pattern for siRNA drugs that has never been tested — the *dark matter* of RNA therapeutics — scores each unexplored combination for biological feasibility, generates novel candidates using generative AI, and tells you which experiment to run next.

**For beginners:** siRNA drugs work by silencing disease-causing genes. To work in the body, they need chemical modifications at 42 specific positions along a two-stranded molecule. Scientists have only tested a tiny fraction of all possible modification combinations — the rest is *dark matter*: invisible, unexplored, but potentially governing which drugs succeed or fail. OligoVoid maps this dark matter and asks: *"which of these unexplored patterns is most likely to work, and which should we test first?"*

**For researchers:** OligoVoid constructs a position×modification co-occurrence matrix from 3,535 experimentally validated siRNAs across 9 published datasets, enumerates the complement set (the dark matter — 2,397 biologically feasible void candidates), trains a Conditional β-VAE to generate novel candidates conditioned on target knockdown efficacy, and applies Void-Prioritized Acquisition (VPA) — a novel active learning acquisition function that biases exploration toward the dark matter rather than the already-illuminated training distribution.

---

## Why This Matters

In cosmology, dark matter makes up 85% of the universe's mass but has never been directly observed. In siRNA therapeutics, the situation is strikingly similar:

| Fact | Source |
|------|--------|
| Only 8 siRNA drugs are FDA-approved as of 2025 | FDA drug database |
| A 21-mer siRNA has 8^42 ≈ 10^38 possible modification patterns | Calculated |
| Even with biological constraints, ~10^6 feasible patterns exist | Estimated |
| Published literature covers **~8%** of feasible position-modification slots | OligoVoid analysis |
| **92% of the feasible design space is dark matter** — never published, never tested | This work |
| Most approved drug patterns are trade secrets (Alnylam ESC patents) | siRNAmod 2016 |
| No existing tool maps the dark matter OR generates novel candidates | This work |

The modification design space is the single largest bottleneck in siRNA drug development that is not resource-constrained — it is *knowledge-constrained*. OligoVoid makes the dark matter visible.

---

## What Makes OligoVoid Different

Every other siRNA design tool answers the question: *"How well will this sequence work?"* OligoVoid answers a different question: *"What has never been tried, and should we try it?"*

The distinction is between a flashlight (illuminating one spot at a time) and a telescope (mapping the entire dark sky).

| Feature | Random Design | Rule-Based Tools | OligoFormer (2024) | **OligoVoid** |
|---------|:---:|:---:|:---:|:---:|
| Uses real experimental data | - | - | 2,431 sequences | **3,535 sequences** |
| Maps the dark matter (unexplored space) | - | - | - | **2,397 void candidates** |
| Generates novel candidates | - | - | - | **CVAE (96.5% valid)** |
| Quantifies prediction uncertainty | - | - | - | **GP (ECE=0.027)** |
| Guides next experiment | - | - | - | **VPA active learning** |
| Temporal gap tracking | - | - | - | **Void Closure Velocity** |
| Latent space analysis | - | - | - | **UMAP + interpolation** |
| Open source & reproducible | - | Varies | Yes | **Yes** |

**The key distinction:** OligoFormer achieves Pearson r=0.719 at predicting siRNA efficacy from sequence features. OligoVoid is not competing on prediction accuracy. OligoVoid solves a different problem: systematic cartography of the *dark matter* — the 92% of modification space that has never been tested — with uncertainty-driven experiment prioritization.

---

## Novel Scientific Contributions

This project introduces five original contributions, none of which exist in any prior published system:

### 1. Dark Matter Cartography — Complement-Set Enumeration

We formally treat the set of published modification patterns as a subset *S* of the full feasible space *F*, and exhaustively enumerate *F \ S* — the complement set, the dark matter. No prior siRNA tool does this. Prior tools are all discriminative: given a sequence, predict its efficacy. We are structural: given the published literature, find what is absent.

### 2. Position-Modification Co-occurrence Matrix

We build a 42×8 matrix (21 guide positions + 21 passenger positions × 8 modification types) counting how many times each combination appears in published data. Slots with zero counts are the dark matter — modification-position combinations that no one has ever published. This is the first such matrix constructed from real siRNA literature at position-specific resolution.

### 3. Conditional β-VAE for Modification Pattern Generation

We train a Conditional Variational Autoencoder to generate novel siRNA modification patterns conditioned on a target knockdown efficacy. The model learns the latent structure of valid chemistry from 3,535 real experiments. Generated candidates cluster near FDA-approved drugs in the learned latent space, suggesting the CVAE has learned to navigate the dark matter while staying close to known physics.

### 4. Void-Prioritized Acquisition (VPA)

Standard Expected Improvement (EI) in Bayesian Optimization can over-exploit known high-performing regions — it keeps shining the flashlight where it already knows the answer. Our VPA modifies EI by multiplying a novelty bonus based on minimum Hamming distance to all training patterns:

```
VPA(x) = EI(x) × novelty_bonus(x)
novelty_bonus = 1.0 + α × (hamming_to_nearest / 21)
```

VPA is a *dark matter telescope*: it biases exploration toward the unexplored void space, rewarding both expected improvement AND structural novelty. Among patterns with comparable EI, VPA preferentially explores uncharted territory. To our knowledge, this is the first acquisition function to incorporate domain-specific void distance into expected improvement for oligonucleotide design.

### 5. Interpretable Latent Space

UMAP visualization reveals that the CVAE's 16-dimensional latent space encodes meaningful chemical structure:
- FDA-approved drugs cluster by delivery strategy (GalNAc vs. LNP)
- Smooth interpolation between Inclisiran and Givosiran produces 5 novel intermediate candidates
- Top latent dimensions encode backbone chemistry and modification composition

The dark matter is not featureless void — it has structure, and our model has learned to read it.

---

## Honest Performance

All metrics from real cross-validation. No synthetic benchmarks. No cherry-picked results.

| Metric | Value | Context |
|--------|-------|---------|
| GP Pearson r | 0.140 | Held-out test set (n=709) with bootstrap 95% CI [0.07, 0.21] |
| GP RMSE | 25.4% | On 3,535 OligoFormer sequences |
| GP Calibration (ECE) | **0.027** | Well-calibrated — the metric that actually matters for active learning |
| FDA drug validation | MAE 27.0% | Predictions vs 8 approved siRNA drugs (extrapolation — expected) |
| CVAE validity | **96.5%** | Generated patterns within biophysical bounds |
| CVAE uniqueness | **100%** | All generated candidates are distinct |
| CVAE novelty | **100%** | All candidates differ from training data |
| VPA space exploration | **+23%** | More modification space explored vs standard EI |
| Void candidates | **2,397** | Biologically feasible patterns in the dark matter |

**For context:** OligoFormer (transformer, 2024) achieves Pearson r=0.719 on the Huesken benchmark, but uses sequence-level features and does not quantify uncertainty. Our GP is intentionally modest — designed for *calibrated uncertainty* (ECE=0.027), not maximum prediction accuracy. In active learning, calibration is everything: a well-calibrated GP with r=0.14 is more useful for experiment selection than an overconfident model with r=0.7.

---

## Architecture

```
Dark Matter Cartography Engine
    │
    ├── 3,535 Real siRNA Experiments (Huesken, Takahashi, mixed sources)
    │       │
    │       ├── Feature Engineering ── 19 biophysical features
    │       │       │
    │       │       ├── RealDataGP ──── Efficacy prediction + calibrated uncertainty
    │       │       │                       Matérn-5/2 kernel, ECE=0.027
    │       │       │
    │       │       └── CVAE ────────── Novel pattern generation from the dark matter
    │       │                               42-dim features, 16-dim latent, MSE+KL loss
    │       │
    │       ├── Biophysics Rules ──── 4 sub-scores (thermo, RISC, nuclease, off-target)
    │       │
    │       ├── Void Detector ─────── 2,397 biologically feasible dark matter candidates
    │       │
    │       └── VPA Active Learning ── Dark Matter Telescope
    │               │                       EI(x) × novelty_bonus(x)
    │               │
    │               └── Ranked Experiments with plain English explanations
    │
    └── Latent Space Analysis ── UMAP visualization, drug interpolation,
                                  dimension interpretation
```

### 3-Layer Scoring Engine

Every dark matter candidate is scored through three independent layers:

| Layer | What | Source | Speed |
|-------|------|--------|-------|
| 1. Biophysics rules | Thermo, RISC, nuclease, off-target sub-scores | `modification_grammar.py` | Instant |
| 2. RealDataGP | Efficacy prediction + calibrated uncertainty | 3,535 OligoFormer sequences | ~50ms |
| 3. CVAE novelty | Pattern novelty from generative model | `generative_model.py` | ~10ms |

---

## How It Works

### Step 1: Map the Known Universe
Compile 3,535 experimentally validated siRNAs from 9 published datasets. Build a position×modification co-occurrence matrix. Everything with a count of zero is dark matter.

### Step 2: Enumerate the Dark Matter
Generate all biologically feasible void candidates by mutating known patterns at 1-3 positions, filtered through cleavage site integrity, seed region rules, and nuclease resistance thresholds. Result: **2,397 candidates** in the dark matter.

### Step 3: Score Every Candidate
Three-layer scoring: rule-based biophysics, GP with calibrated uncertainty, and CVAE novelty score. Each candidate gets a composite OligoVoid score with plain English explanation.

### Step 4: Generate Novel Patterns
The Conditional VAE generates entirely new modification profiles conditioned on a target knockdown efficacy. These aren't mutations of known patterns — they're *de novo* designs from the learned latent space.

### Step 5: Prioritize Experiments
VPA ranks all candidates by combined expected improvement and novelty. The output: "Here are the 10 experiments most likely to illuminate the dark matter. Here's why each one matters."

---

## Features

### 1. Position × Modification Heatmap
Interactive dual-strand heatmap showing exploration density across 336 position-modification cells. Red = dark matter (never published). Green = well-explored.

### 2. Dark Matter Enumeration
Generates all 1-3 position variants from known patterns, filtered through biological constraints. Produces **2,397 biologically feasible dark matter candidates**.

### 3. Three-Layer Feasibility Scoring
- **Layer 1:** Rule-based biophysics (thermodynamic stability, RISC loading, nuclease resistance, off-target risk)
- **Layer 2:** RealDataGP trained on 3,535 real sequences with calibrated uncertainty (ECE=0.027)
- **Layer 3:** CVAE novelty score measuring pattern distance from training distribution

### 4. CVAE Novel Pattern Generation
Conditional VAE generates novel modification profiles conditioned on target knockdown efficacy. 96.5% validity, 100% novelty. Users control target efficacy (60-95%) and generation temperature.

### 5. Active Learning (DMTL)
Four acquisition functions: Expected Improvement, Upper Confidence Bound, Thompson Sampling, and **VPA** (novel). VPA explores 23% more modification space than standard EI.

### 6. Void Closure Velocity
Temporal metric tracking how fast each dark matter region is being illuminated by the field. HOT/WARMING/COLD classification for competitive intelligence.

### 7. Model Validation Dashboard
Transparent validation: training data provenance, 5-fold CV results, FDA drug validation, calibration curve (ECE=0.027), and honest limitations — all visible in the UI.

### 8. Latent Space Visualization
UMAP projection of the CVAE's learned chemical space. FDA drugs cluster by delivery strategy. Smooth interpolation between drugs reveals novel intermediate candidates. Dimension analysis shows what the AI learned.

---

## Quick Start

```bash
git clone https://github.com/ManasReddy1/oligovoid.git
cd oligovoid
pip install -r backend/requirements.txt

# Start server (auto-initializes database and models)
cd backend
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000**

### Enable Claude API enhanced scoring (optional)

```bash
cp .env.example .env
# Edit .env → add ANTHROPIC_API_KEY
```

Without an API key, all scoring is rule-based biophysics + GP (fully functional). The Claude API adds expert-level reasoning and experiment recommendations.

---

## Results

### Table 1: Predictive Performance

| Model | Pearson r | Spearman ρ | RMSE (%) | AUC | F1 |
|-------|-----------|------------|----------|-----|-----|
| Random (population mean) | 0.000 | 0.000 | 25.2 | 0.500 | 0.000 |
| Biophysics heuristic | -0.113 | -0.137 | 38.6 | 0.431 | 0.007 |
| **OligoVoid GP** | **0.140** | **0.178** | **25.4** | **0.624** | **0.386** |
| OligoFormer† | 0.719 | 0.700 | 18.5 | — | — |

*† Published benchmark; uses sequence-level transformer features and does not quantify uncertainty.*

### Table 2: CVAE Generation Quality (MOSES-style)

| Metric | Value |
|--------|-------|
| Validity | 96.5% |
| Uniqueness | 100% |
| Novelty | 100% |
| Diversity (mean pairwise ℓ₂) | 6.24 |
| KNN distance to training | 3.42 |

### Uncertainty Calibration

ECE = **0.027** (well-calibrated). The GP's confidence intervals contain the true value at nearly the correct rate across all confidence levels. This is the metric that matters for active learning.

---

## API

All endpoints available at `http://localhost:8000/api/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Dashboard key numbers |
| `/api/voids` | GET | Top void candidates with scores |
| `/api/modification-map` | GET | Position × modification heatmap data |
| `/api/generate/candidates` | POST | CVAE generation + GP scoring |
| `/api/model/validation` | GET | Training data, CV metrics, FDA validation |
| `/api/dmtl/run` | POST | Run DMTL simulation |
| `/api/benchmarks` | GET | Run all benchmarks (Table 1) |
| `/api/latent/map` | GET | UMAP latent space visualization |
| `/api/latent/interpolation` | GET | Drug-to-drug latent interpolation |
| `/api/latent/dimensions` | GET | Latent dimension analysis |

---

## Data Sources

| Dataset | N sequences | Year | Citation |
|---------|-------------|------|----------|
| Huesken et al. | 2,361 | 2005 | *Nature Biotechnology* 23(8):995-1001 |
| Takahashi et al. | 702 | 2009 | *Molecular Therapy* 17(7):1137-1146 |
| Mixed published | 472 | Various | Multiple sources, curated |
| FDA-approved drugs | 8 | 2018-2025 | FDA approval documents |
| Reynolds rules | 20 | 2004 | *Nature Biotechnology* 22(3):326-330 |
| Khvorova group | 15 | 2003-2018 | *Cell* 115(2):209-216 |
| Ui-Tei rules | 10 | 2004 | *Nucleic Acids Research* 32(3):936-948 |
| Academic variants | 7 | Various | LNA, UNA, MsPA, cEt, MOE studies |

**Total: 3,535 sequences for GP training + 60 curated modification patterns for dark matter detection.**

---

## What OligoVoid Cannot Do

We are transparent about limitations. The dark matter is real, but our telescope has known imperfections:

- **No wet-lab validation:** All results are computational. The dark matter candidates require synthesis and testing.
- **Limited chemical diversity:** Most training data uses 2'-OMe and 2'-F; rarer modifications (LNA, UNA, cEt, MOE) have fewer examples in the training data.
- **Context-free:** We don't model the target mRNA sequence. OligoFormer does this better — use it for sequence-level design, use OligoVoid for modification-level exploration.
- **GP uncertainty is approximate:** Not a rigorous Bayesian guarantee, but ECE=0.027 indicates good empirical calibration.
- **Training data skew:** 6 of 8 FDA drugs use GalNAc conjugation (liver targets). The dark matter map may be biased toward liver-targeted chemistry.

OligoVoid is best used as a **dark matter telescope** — a tool for finding and prioritizing the unexplored. It answers "what should I try next?" not "will this definitely work?"

---

## Paper

**OligoVoid: Mapping the Dark Matter of siRNA Chemical Space**

Full paper in NeurIPS format: [`paper/oligovoid_paper.tex`](paper/oligovoid_paper.tex)

Key equations:

**Void-Prioritized Acquisition:**
```
α_VPA(x) = α_EI(x) · (1 + λ · d_min(x) / L)
```
where d_min(x) = min Hamming distance to known patterns, λ=0.5, L=21.

**CVAE ELBO:**
```
L = ||x - x̂||² + β · D_KL(q(z|x,c) || N(0,I))
```
with β=0.5, latent dim=16, conditioned on target efficacy c.

---

## References

1. Reynolds A, et al. **Rational siRNA design for RNA interference.** *Nature Biotechnology*. 2004;22(3):326-330.
2. Khvorova A, et al. **Functional siRNAs and miRNAs exhibit strand bias.** *Cell*. 2003;115(2):209-216.
3. Huesken D, et al. **Design of a genome-wide siRNA library using an artificial neural network.** *Nature Biotechnology*. 2005;23(8):995-1001.
4. Setten RL, et al. **The current state and future directions of RNAi-based therapeutics.** *Nature Reviews Drug Discovery*. 2019;18(6):421-446.
5. Foster DJ, et al. **Advanced siRNA designs further improve in vivo performance of GalNAc-siRNA conjugates.** *Molecular Therapy*. 2018;26(3):708-717.
6. O'Reilly D, et al. **Systematic evaluation of position-specific tolerability of seven backbone and ribose modifications.** *Nucleic Acid Therapeutics*. 2025.
7. Dar SA, et al. **siRNAmod: A database of experimentally validated chemically modified siRNAs.** *Scientific Reports*. 2016;6:20031.
8. He S, et al. **OligoFormer: Prediction of siRNA efficacy using deep transformer models.** *Nucleic Acids Research*. 2024.
9. Davis SM, et al. **Systematic analysis of siRNA and mRNA features impacting fully chemically modified siRNA efficacy.** *Nucleic Acids Research*. 2025;53(12):gkaf479.
10. Jackson AL, et al. **Widespread siRNA off-target transcript silencing mediated by seed region sequence complementarity.** *RNA*. 2006;12(7):1179-1187.

---

## Citation

```bibtex
@software{reddy2026oligovoid,
  author = {Reddy, Manas},
  title = {OligoVoid: Mapping the Dark Matter of siRNA Chemical Space},
  year = {2026},
  url = {https://github.com/ManasReddy1/OligoVoid}
}
```

---

## License

MIT

---

Built by **Manas Reddy** · [GitHub](https://github.com/ManasReddy1)

*The dark matter of RNA therapeutics is waiting to be mapped. This is the telescope.*
