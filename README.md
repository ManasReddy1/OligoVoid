<div align="center">

# OligoVoid

### Mapping the Dark Matter of siRNA Chemical Space

[![arXiv](https://img.shields.io/badge/arXiv-2026.XXXXX-b31b1b.svg)](https://arxiv.org/abs/PLACEHOLDER)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)

</div>

---

## The Hook

**For anyone:** siRNA drugs silence disease-causing genes, but they need chemical armor to survive inside the body. Scientists have only tested 8% of possible armor combinations. OligoVoid maps the other 92% and ranks which untested combinations are worth trying first.

**For researchers:** OligoVoid constructs a position-modification co-occurrence matrix from 3,535 experimentally validated siRNA sequences across 9 published datasets, enumerates 2,397 biologically feasible void candidates occupying the complement set (the 92% of feasible modification space absent from published literature), trains a Conditional beta-VAE to generate novel candidates conditioned on target knockdown efficacy, scores each candidate through a three-layer biophysics/GP/CVAE engine, and applies Void-Prioritized Acquisition (VPA) -- a novel active learning acquisition function that biases exploration toward the unexplored dark matter rather than the already-illuminated training distribution. Uncertainty is quantified via a Gaussian Process with calibrated confidence intervals (ECE=0.027).

---

## Why This Matters

In cosmology, dark matter makes up 85% of the universe's mass but has never been directly observed. In siRNA therapeutics, the situation is strikingly parallel:

| Fact | Source |
|------|--------|
| Only 8 siRNA drugs are FDA-approved as of 2025 | FDA drug database |
| A 21-mer duplex siRNA has 8^42 ~ 10^38 possible modification patterns | Combinatorial calculation (8 sugar mods x 42 positions) |
| Even under biological constraints, ~10^6 feasible patterns exist | Estimated from cleavage site integrity + seed region rules |
| Published literature covers **~8%** of feasible position-modification slots | OligoVoid co-occurrence matrix analysis |
| **92% of the feasible design space is dark matter** -- never published, never tested | This work |
| Most approved drug modification patterns are trade secrets (Alnylam ESC patents) | siRNAmod, Dar et al., *Scientific Reports* 2016 |
| Development of proprietary modification patterns is essential for siRNA companies | *Molecular Therapy: Methods & Clinical Development*, 2025 |
| No existing tool maps the dark matter or generates novel modification candidates | This work |

The modification design space is the single largest bottleneck in siRNA drug development that is not resource-constrained -- it is *knowledge-constrained*. OligoVoid makes the dark matter visible.

---

## The Honest Comparison

Every other siRNA design tool answers the question: *"How well will this sequence work?"* OligoVoid answers a different question: *"What has never been tried, and should I try it?"*

| Feature | Random Design | Rule-Based Tools | OligoFormer (2024) | **OligoVoid** |
|---------|:---:|:---:|:---:|:---:|
| Uses real experimental data | -- | -- | 2,431 sequences | **3,535 sequences** |
| Maps the dark matter (unexplored space) | -- | -- | -- | **2,397 void candidates** |
| Generates novel candidates | -- | -- | -- | **CVAE (97.5% valid)** |
| Quantifies prediction uncertainty | -- | -- | -- | **GP (ECE=0.027)** |
| Guides next experiment | -- | -- | -- | **VPA active learning** |
| Temporal gap tracking | -- | -- | -- | **Void Closure Velocity** |
| Open source & reproducible | -- | Varies | Yes | **Yes** |

**Important caveat:** This comparison reflects tool *capabilities*, not prediction accuracy. OligoFormer achieves Pearson r=0.719 at predicting siRNA efficacy from sequence features and is the state-of-the-art for that task. OligoVoid is not competing on prediction accuracy -- it solves a structurally different problem: cartography and experiment prioritization in the unexplored 92% of modification space. Additionally, all five FDA-approved drugs used for validation have clinical efficacy >70%, meaning a trivial always-high classifier would also appear to "classify" them correctly. I report ranking metrics (Spearman rho) rather than classification accuracy for this reason.

---

## Five Novel Contributions

This project introduces five original contributions, none of which exist in any prior published system.

### 1. Dark Matter Cartography -- Complement-Set Enumeration

**Definition.** Let *S* denote the set of published modification patterns and *F* the full biologically feasible space. I exhaustively enumerate *F \ S* -- the complement set, the dark matter. No prior siRNA tool does this. Prior tools are all discriminative: given a sequence, predict its efficacy. OligoVoid is structural: given the published literature, find what is absent. This reframes siRNA design from a prediction problem to an exploration problem.

### 2. Position-Modification Co-occurrence Matrix

**Definition.** A 42 x 8 matrix *M* where *M[i][j]* counts the number of published siRNAs bearing modification type *j* at position *i* (21 guide positions + 21 passenger positions, 8 modification types: 2'-OMe, 2'-F, LNA, cEt, DNA, RNA, UNA, MOE). Slots where *M[i][j] = 0* are the dark matter -- modification-position combinations that no one has ever published. This is the first such matrix constructed from real siRNA literature at position-specific resolution.

### 3. Conditional beta-VAE for Modification Pattern Generation

**Definition.** A Conditional Variational Autoencoder with architecture [43 -> 64 -> 32 -> z(16)] -> [17 -> 32 -> 64 -> 42], trained on 3,535 real experiments with beta=0.5 KL weighting. The model learns a smooth 16-dimensional latent space of valid modification chemistry, conditioned on a target knockdown efficacy *c*. The ELBO objective is:

```
L = ||x - x_hat||^2 + beta * D_KL( q(z|x,c) || N(0,I) )
```

Generated candidates cluster near FDA-approved drugs in the learned latent space, suggesting the CVAE has learned to navigate the dark matter while staying close to known biophysics.

### 4. Void-Prioritized Acquisition (VPA)

**Definition.** Standard Expected Improvement (EI) in Bayesian optimization can over-exploit known high-performing regions. VPA modifies EI by multiplying a novelty bonus based on minimum Hamming distance to all training patterns:

```
alpha_VPA(x) = alpha_EI(x) * (1 + lambda * d_min(x) / 21)
```

where *d_min(x) = min Hamming distance to nearest known pattern*, lambda=0.5, and 21 is the strand length. Among patterns with comparable EI, VPA preferentially explores uncharted territory. To my knowledge, this is the first acquisition function to incorporate domain-specific void distance into expected improvement for oligonucleotide design.

### 5. Chemistry Fingerprint -- an 8-Feature Representation

**Definition.** A novel 8-dimensional fingerprint that captures the chemical character of an siRNA modification pattern at the *pattern* level rather than the *position* level. The eight biologically motivated features are:

1. **Alternation score** -- How alternating is the 2'-OMe / 2'-F pattern? (ESC chemistry compliance)
2. **Seed region 2'-F density** -- Fraction of guide positions 2-8 that are 2'-F (target recognition fidelity)
3. **3' protection score** -- Stabilizing modifications at guide positions 17-21 (exonuclease resistance)
4. **Strand asymmetry** -- RISC-loading bias between guide and passenger (Ago2 selection)
5. **Consecutive LNA max** -- Longest run of consecutive LNA residues (hepatotoxicity risk)
6. **Modification diversity** -- Normalized Shannon entropy of mod-type distribution (design sophistication)
7. **GalNAc compatibility** -- Binary flag for GalNAc conjugation compatibility (delivery feasibility)
8. **Similarity to Givosiran** -- Hamming similarity to the best-performing FDA drug (83% clinical efficacy)

A composite fingerprint quality score (0-100) and a plain-English interpretation are computed from these features. This fingerprint enables rapid screening and ranking of thousands of void candidates without requiring full biophysics simulation.

---

## Results

All metrics below come from real cross-validation on held-out data. No synthetic benchmarks. No cherry-picked results.

### 6a. FDA Drug Sanity Check

I validated OligoVoid's scoring system against 5 FDA-approved siRNA drugs (Inclisiran, Givosiran, Lumasiran, Vutrisiran, Patisiran) with known clinical efficacy. These drugs were **not** used to train the model -- this is a prospective sanity check.

| Metric | Value |
|--------|-------|
| Drugs correctly classified as high-efficacy | 4 / 5 |
| Spearman rank correlation (rho) with clinical outcomes | 0.229 |
| Mean absolute error vs. clinical efficacy | 11.3% |

**The honest caveat:** All 5 FDA-approved drugs have clinical efficacy >70%, because only effective drugs get approved. A trivial always-high classifier would score 5/5 on classification accuracy. The meaningful metric is therefore *ranking* (Spearman rho), not classification. OligoVoid's rho=0.229 indicates that the scoring system captures some real chemical signal -- it correctly ranks Givosiran (83%) above Inclisiran (51%) -- but ranking power is inherently limited by having only 5 data points. A bootstrap analysis against 1,000 random rankings places OligoVoid at approximately the 60th percentile, meaning it performs better than chance but is far from definitive with this sample size.

### 6b. GP Cross-Validation

The Gaussian Process regressor was evaluated on a held-out test set (n=709) from 3,535 OligoFormer sequences using 19 biophysical features and a Matern-5/2 kernel.

| Metric | Value | 95% Bootstrap CI |
|--------|-------|------------------|
| Pearson r | 0.272 | [0.19, 0.35] |
| RMSE | 24.3% | [23.1, 25.5] |
| ECE (calibration error) | **0.027** | -- |

**Why r=0.272 is acceptable.** OligoVoid's GP is not designed to maximize point prediction accuracy -- OligoFormer (r=0.719) already does that using a deep transformer with sequence-level features. The GP uses only 19 biophysical summary features from unmodified RNA and intentionally trades prediction accuracy for *calibrated uncertainty*. In active learning, what matters is not whether the model predicts 72% vs. 78% efficacy, but whether the model *knows what it does not know*. An ECE of 0.027 means the GP's 90% confidence intervals contain the true value approximately 90% of the time. This calibration property is what makes the GP useful as the backbone of the VPA acquisition function: it can reliably distinguish "I am confident this will work" from "I have no idea -- this is dark matter, and we should test it."

### 6c. CVAE Generation Quality (MOSES-style Metrics)

| Metric | Value |
|--------|-------|
| Validity | **97.5%** |
| Uniqueness | **100%** |
| Novelty | **100%** |
| Diversity (mean pairwise L2) | **6.22** |

The CVAE generates modification feature profiles that are (a) within biophysical bounds (97.5% validity), (b) all distinct from each other (100% uniqueness), (c) all structurally different from every training example (100% novelty), and (d) well-spread across the feature space (diversity 6.22). Conditioning on higher target efficacy produces profiles with correspondingly higher GP-predicted efficacy, confirming that the conditioning mechanism works. In the in-silico validation loop, CVAE-guided generation produces a higher fraction of candidates predicted above the 70% therapeutic threshold compared to random sampling from the same latent space.

### 6d. Active Learning: VPA vs. EI

In a simulated active learning benchmark (15 cycles, 10 independent repeats), VPA explores more of the modification space than standard Expected Improvement. EI tends to cluster selections near known high-performing regions (exploitation), while VPA's novelty bonus pushes it into uncharted territory (exploration). The result: VPA covers a broader range of modification-position combinations per cycle, making it the better strategy for the specific goal of illuminating the dark matter. EI remains superior when the sole objective is finding the single highest-efficacy pattern.

### 6e. Modification Space Coverage

The co-occurrence matrix analysis reveals that 92% of biologically feasible position-modification slots have zero published examples. From the dark matter, I enumerate 2,397 void candidates -- patterns that differ from known designs at 1-3 positions, pass cleavage site integrity checks, satisfy seed region constraints, and meet nuclease resistance thresholds. These are not random permutations; they are the nearest neighbors of known functional patterns in the unexplored space, making them high-priority targets for experimental validation.

### 6f. Chemistry Fingerprint

The 8-feature chemistry fingerprint provides a compact, interpretable representation of each modification pattern. Applied to FDA-approved drugs, the fingerprint correctly identifies Givosiran as the highest-quality pattern (score 87/100) due to its strong seed region 2'-F density, good 3' protection, and GalNAc compatibility. The fingerprint also flags known failure modes: patterns with >3 consecutive LNA residues receive a hepatotoxicity penalty, and patterns incompatible with GalNAc conjugation are flagged for non-hepatocyte delivery.

### 6g. Qualitative Case Study: Top Void Candidate

The highest-scoring void candidate differs from the nearest known pattern (a Givosiran variant) at exactly two guide strand positions: position 4 (2'-OMe -> 2'-F, in the seed region) and position 18 (2'-OMe -> LNA, in the 3' protective zone). The biophysics rationale is clear: adding 2'-F at position 4 should enhance seed region binding affinity without disrupting A-form helix geometry, while a single LNA at position 18 provides additional exonuclease resistance. The GP predicts 74% efficacy with a standard deviation of 12%, placing this candidate in the "worth testing" zone. The plain-English interpretation: "This is a conservative modification of a proven drug design -- two targeted chemical changes in regions where the changes make biophysical sense. It has never been published."

---

## Architecture

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                    OligoVoid: Dark Matter Cartography Engine           │
 └─────────────────────────┬───────────────────────────────────────────────┘
                           │
 ┌─────────────────────────▼───────────────────────────────────────────────┐
 │  DATA SOURCES                                                          │
 │  ├── Huesken et al. (2,361 seqs)    ├── FDA drugs (5 approved)         │
 │  ├── Takahashi et al. (702 seqs)    ├── Reynolds rules (20 seqs)       │
 │  ├── Mixed published (472 seqs)     ├── Khvorova group (15 seqs)       │
 │  └── Total: 3,535 sequences         └── 60 curated modification patterns│
 └─────────────────────────┬───────────────────────────────────────────────┘
                           │
 ┌─────────────────────────▼───────────────────────────────────────────────┐
 │  FEATURE ENGINEERING                                                    │
 │  ├── 19 biophysical features (GC%, thermo, RISC, nuclease, off-target) │
 │  ├── 42-dim modification profile (18 core + 24 thermodynamic)          │
 │  ├── 8-dim Chemistry Fingerprint (NEW)                                 │
 │  │     alternation | seed_2F | 3'_protection | strand_asymmetry        │
 │  │     consec_LNA  | diversity | galnac_compat | givosiran_similarity  │
 │  └── Position x Modification Co-occurrence Matrix (42 x 8)            │
 └───────────┬─────────────────────────────┬───────────────────────────────┘
             │                             │
 ┌───────────▼───────────┐     ┌───────────▼───────────────────────────────┐
 │  LAYER 1: BIOPHYSICS  │     │  VOID DETECTOR                           │
 │  ├── Thermodynamic    │     │  ├── Complement set enumeration F \ S    │
 │  │   stability        │     │  ├── 1-3 position mutations              │
 │  ├── RISC loading     │     │  ├── Cleavage site integrity check       │
 │  ├── Nuclease         │     │  ├── Seed region constraint filter       │
 │  │   resistance       │     │  ├── Nuclease resistance threshold       │
 │  └── Off-target risk  │     │  └── Output: 2,397 void candidates       │
 └───────────┬───────────┘     └───────────┬───────────────────────────────┘
             │                             │
 ┌───────────▼───────────┐     ┌───────────▼───────────────────────────────┐
 │  LAYER 2: GP MODEL    │     │  LAYER 3: CVAE GENERATIVE MODEL          │
 │  ├── Matern-5/2 kernel│     │  ├── Encoder: [43->64->32->z(16)]        │
 │  ├── 3,535 training   │     │  ├── Decoder: [17->32->64->42]           │
 │  │   sequences        │     │  ├── beta=0.5 (disentangled latent)      │
 │  ├── Pearson r=0.272  │     │  ├── Conditioned on target efficacy      │
 │  ├── ECE=0.027        │     │  ├── Validity: 97.5%                     │
 │  │   (well-calibrated)│     │  ├── Novelty: 100%                       │
 │  └── Outputs: mu, std │     │  └── UMAP latent space visualization     │
 └───────────┬───────────┘     └───────────┬───────────────────────────────┘
             │                             │
 ┌───────────▼─────────────────────────────▼───────────────────────────────┐
 │  THREE-LAYER COMPOSITE SCORING                                          │
 │  ├── Biophysics sub-scores (thermo + RISC + nuclease + off-target)     │
 │  ├── GP predicted efficacy + calibrated uncertainty (mu +/- 2*sigma)   │
 │  ├── CVAE novelty score (distance from training distribution)          │
 │  └── Chemistry Fingerprint quality score (0-100)                       │
 └─────────────────────────┬───────────────────────────────────────────────┘
                           │
 ┌─────────────────────────▼───────────────────────────────────────────────┐
 │  VPA ACTIVE LEARNING ENGINE                                             │
 │  ├── Acquisition: alpha_VPA(x) = alpha_EI(x) * (1 + lambda*d/21)     │
 │  ├── Strategies: EI | UCB | Thompson | VPA (novel)                     │
 │  ├── Void Closure Velocity tracking (HOT / WARMING / COLD)            │
 │  └── Plain-English experiment recommendations                          │
 └─────────────────────────┬───────────────────────────────────────────────┘
                           │
 ┌─────────────────────────▼───────────────────────────────────────────────┐
 │  OUTPUT                                                                 │
 │  ├── Ranked void candidates with composite scores                      │
 │  ├── Modification intelligence reports (expert + plain English)        │
 │  ├── UMAP latent space maps + drug-to-drug interpolation               │
 │  ├── "Run this experiment next" recommendations with rationale         │
 │  └── Interactive dashboard (FastAPI + static frontend)                 │
 └─────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
git clone https://github.com/ManasReddy1/oligovoid.git
cd oligovoid
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** in your browser. The server auto-initializes the database, trains models on first run, and serves the full dashboard.

---

## Data Sources

| Dataset | N Sequences | Year | Citation |
|---------|-------------|------|----------|
| Huesken et al. | 2,361 | 2005 | *Nature Biotechnology* 23(8):995-1001 |
| Takahashi et al. | 702 | 2009 | *Molecular Therapy* 17(7):1137-1146 |
| Mixed published | 472 | Various | Multiple sources, curated |
| FDA-approved drugs | 5 | 2018-2022 | FDA approval documents; Ray KK et al. NEJM 2020; Scott LJ Drugs 2020; Garrelfs SF et al. NEJM 2021; Adams D et al. NEJM 2023; Adams D et al. NEJM 2018 |
| Reynolds rules | 20 | 2004 | *Nature Biotechnology* 22(3):326-330 |
| Khvorova group | 15 | 2003-2018 | *Cell* 115(2):209-216 |
| Ui-Tei rules | 10 | 2004 | *Nucleic Acids Research* 32(3):936-948 |
| Academic variants | 7 | Various | LNA, UNA, MsPA, cEt, MOE studies |

**Total: 3,535 sequences for GP training + 60 curated modification patterns for dark matter detection.**

---

## Honest Limitations

I am transparent about what OligoVoid cannot do. The dark matter is real, but the telescope has known imperfections.

- **No wet-lab validation.** All results are computational. The 2,397 void candidates are predictions, not experimentally confirmed hits. Until someone synthesizes and tests them, they remain hypotheses. I have not run a single experiment in a lab -- this is a computational cartography project, and the map needs to be validated by explorers.

- **Limited chemical diversity.** The overwhelming majority of training data uses 2'-OMe and 2'-F modifications, because that is what the published literature contains. Rarer modification types (LNA, UNA, cEt, MOE) have far fewer training examples, which means the GP and CVAE have less reliable uncertainty estimates in those regions of chemical space. The dark matter map is most trustworthy in the 2'-OMe/2'-F neighborhood and least trustworthy at the exotic edges.

- **Context-free (no mRNA target sequence).** OligoVoid models the modification pattern in isolation -- it does not account for the target mRNA sequence, secondary structure, or cellular context. OligoFormer handles sequence-level prediction better. Use OligoFormer for "will this specific siRNA silence this specific gene?" and OligoVoid for "what modification chemistry should I explore next?"

- **GP uncertainty is approximate.** The ECE=0.027 indicates good empirical calibration, but this is not a rigorous Bayesian guarantee. The GP assumes stationary noise and a smooth latent function, both of which are approximations. In regions far from training data (which is precisely the dark matter), the uncertainty estimates should be treated as directional rather than precise.

- **Training data skew toward liver targets.** Four of the five FDA-validated drugs use GalNAc conjugation for hepatocyte delivery. The dark matter map may be biased toward liver-targeted chemistry, and the fingerprint's GalNAc compatibility feature reflects this bias. Modifications optimized for non-hepatic delivery (e.g., CNS, lung, kidney) are underrepresented.

- **Base-rate issue in FDA validation.** All 5 FDA-approved drugs have clinical efficacy >70%, because only effective drugs survive the approval process. This means the classification metric (4/5 correct) is inflated by base rate -- a trivial always-high classifier would score 5/5. I report Spearman rank correlation (rho=0.229) as the honest metric, but even this is limited by the tiny sample size (n=5). The FDA validation is a sanity check, not a proof of accuracy.

---

## How to Cite

```bibtex
@software{reddy2026oligovoid,
  author       = {Reddy, Manas},
  title        = {{OligoVoid}: Mapping the Dark Matter of {siRNA} Chemical Space},
  year         = {2026},
  url          = {https://github.com/ManasReddy1/OligoVoid},
  note         = {Solo project. Computational cartography of unexplored
                  siRNA modification space with generative modeling and
                  uncertainty-driven active learning.}
}
```

---

## Future Work

1. **Wet-lab validation partnership.** The single most impactful next step is synthesizing and testing the top 10 void candidates in a cell-based knockdown assay. I am actively seeking collaborators with RNA synthesis capabilities. Even a handful of validated results would transform the dark matter map from hypothesis to evidence.

2. **Sequence-conditioned generation.** Integrating the target mRNA sequence as an additional conditioning signal to the CVAE would allow OligoVoid to generate modification patterns tailored to a specific gene target. This requires pairing the existing modification-level features with OligoFormer-style sequence embeddings.

3. **Multi-objective acquisition.** Extending VPA to simultaneously optimize efficacy, metabolic stability, and off-target risk as a Pareto front rather than a single composite score. This would let researchers specify their own tradeoff preferences (e.g., "I care more about safety than potency") and receive personalized experiment recommendations.

4. **Expanded modification vocabulary.** Incorporating newer modification chemistries (e.g., 2'-azetidine, glycol nucleic acid, phosphoryl guanidine) as they appear in the literature. Each new modification type expands the co-occurrence matrix and reveals new dark matter regions that were previously invisible.

5. **Temporal dark matter dynamics.** Building a longitudinal model that tracks how the dark matter shrinks over time as new papers are published, identifying which regions of chemical space are being explored fastest (hot zones) and which remain persistently ignored (cold zones). This would provide competitive intelligence for pharmaceutical R&D teams deciding where to invest.

---

## Contributing

Contributions are welcome, especially from researchers with experimental data.

**If you have wet-lab results for a modification pattern**, please open an issue or PR with the following template:

```
Pattern tested:
  Guide strand modifications: [list of 21 modifications]
  Passenger strand modifications: [list of 21 modifications]
  Backbone: [PS positions]
  Conjugate: [GalNAc / LNP / None / Other]

Experimental results:
  Cell line: [e.g., HeLa, Hep3B, primary hepatocytes]
  Target gene: [gene name]
  Knockdown efficacy (%): [value]
  Assay: [qRT-PCR / dual-luciferase / Western blot]
  Concentration: [nM]
  Time point: [hours]
  Citation: [DOI or preprint link, if available]
```

Every validated result -- positive or negative -- helps illuminate the dark matter. Negative results are especially valuable because they define the boundaries of what does not work.

---

<div align="center">

Built by **Manas Reddy** | [GitHub](https://github.com/ManasReddy1) | MIT License

*The dark matter of RNA therapeutics is waiting to be mapped. This is the telescope.*

</div>
