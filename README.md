# OligoVoid

**The first generative AI platform for siRNA chemical modification gap detection:** maps unexplored design space, trains on 3,700+ real experiments, generates novel candidates using a Conditional VAE, and guides experiments using an active learning loop.

---

> *"Most modification patterns of approved or clinically investigated siRNAs are protected by patents, significantly restricting their broader application. Therefore, the development of proprietary modification patterns has been essential for siRNA therapeutics companies."*
> — Molecular Therapy: Methods & Clinical Development, 2025

---

## What Makes This Different

| Capability | Random Design | Rule-Based | OligoFormer (2024) | OligoVoid |
|-----------|:---:|:---:|:---:|:---:|
| Uses real experimental data | - | - | 2,431 sequences | **3,535 sequences** |
| Generates novel patterns | - | - | - | **CVAE generation** |
| Quantifies uncertainty | - | - | - | **GP with calibrated CI** |
| Guides next experiment | - | - | - | **VPA active learning** |
| Maps unexplored space | - | - | - | **Void detection** |
| Open source | - | Varies | Yes | **Yes** |

---

## Honest Performance

All metrics from real cross-validation. No synthetic benchmarks.

| Metric | Value | Context |
|--------|-------|---------|
| GP Pearson r | 0.212 | 5-fold CV on 498 subsampled sequences |
| GP RMSE | 25.0% | Trained on 3,535 OligoFormer sequences |
| FDA drug validation | MAE 27.0% | Predictions vs 8 approved siRNA drugs |
| CVAE valid generation | >90% | Generated patterns within biophysical bounds |
| Training data | 3,535 | From Huesken 2005, Takahashi 2009, mixed sources |

**For context:** OligoFormer (transformer, 2024) achieves Pearson r=0.719 on the Huesken benchmark, but uses sequence-level features and does not quantify uncertainty. Our GP is intentionally smaller — designed for uncertainty quantification and experiment prioritization, not maximum accuracy. Both models are open and reproducible.

---

## Architecture

```
Real Data (3,535 siRNAs)
    │
    ├── Feature Engineering (19 biophysical features)
    │       │
    │       ├── RealDataGP ──── Efficacy prediction + calibrated uncertainty
    │       │                       Matern-5/2 kernel, 5-fold CV
    │       │
    │       └── CVAE ────────── Novel pattern generation
    │                               42-dim features, 16-dim latent, MSE+KL loss
    │
    ├── Biophysics Rules ──── 4 sub-scores (thermo, RISC, nuclease, off-target)
    │
    ├── Void Detector ─────── 2,397 biologically feasible void candidates
    │
    └── VPA Active Learning ── Void-Prioritized Acquisition (novel)
            │                       EI(x) × novelty_bonus(x)
            │
            └── Ranked Candidates with plain English explanations
```

### 3-Layer Scoring Engine

| Layer | What | Source |
|-------|------|--------|
| 1. Biophysics rules | Thermo, RISC, nuclease, off-target sub-scores | `modification_grammar.py` rules |
| 2. RealDataGP | Efficacy prediction + calibrated uncertainty | 3,535 OligoFormer sequences |
| 3. CVAE novelty | Pattern novelty/quality from generative model | `generative_model.py` |

### Novel Contribution: Void-Prioritized Acquisition (VPA)

```
VPA(x) = EI(x) × novelty_bonus(x)
novelty_bonus = 1.0 + alpha × (hamming_to_nearest / 21)
```

VPA biases active learning toward "void" regions of modification space — patterns farthest from any known tested combination. This is the same class of approach used by Insilico Medicine's Chemistry42 for small molecule drug design.

---

## The Challenge

Eight siRNA drugs have received FDA approval since 2018. Every one depends on a carefully engineered chemical modification pattern. The modification design space is enormous (42 positions × 8 sugar modifications × 3 backbone chemistries × 4 conjugates), but **published exploration has converged on a remarkably narrow slice.** Alnylam's ESC chemistry accounts for four of eight approved drugs. Most labs test 5-10 patterns per paper.

**Nobody has systematically mapped what has been tested versus what has not.** OligoVoid fills this gap.

---

## Features

### 1. Position × Modification Heatmap
Interactive dual-strand heatmap showing exploration density across 336 position-modification cells. Red = void (never published). Green = well-explored.

### 2. Void Enumeration with Biological Filtering
Generates all 1-2 position variants from known patterns, filtered through biological constraints (cleavage site integrity, seed region rules, nuclease resistance thresholds). Produces **2,397 biologically feasible void candidates**.

### 3. Three-Layer Feasibility Scoring
- **Layer 1:** Rule-based biophysics (thermodynamic stability, RISC loading, nuclease resistance, off-target risk)
- **Layer 2:** RealDataGP trained on 3,535 real sequences with calibrated uncertainty
- **Layer 3:** CVAE novelty score measuring pattern distance from training distribution

### 4. CVAE Novel Pattern Generation
Conditional Variational Autoencoder generates novel modification profiles conditioned on target knockdown efficacy. Users control target efficacy (60-95%) and generation temperature.

### 5. Active Learning (DMTL)
Four acquisition functions: Expected Improvement, Upper Confidence Bound, Thompson Sampling, and **VPA** (novel). Simulation compares Random vs EI vs VPA across N cycles.

### 6. Void Closure Velocity
Temporal metric tracking how fast each void is being filled by the field. HOT/WARMING/COLD classification for competitive intelligence.

### 7. Model Validation Dashboard
Transparent validation: training data provenance, 5-fold CV results, FDA drug validation, and honest limitations — all visible in the UI.

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

**Total: 3,535 sequences for GP training + 60 curated modification patterns for void detection.**

---

## What OligoVoid Cannot Do

We are transparent about limitations:

- **No wet-lab validation:** all results are computational
- **Limited chemical diversity:** most training data uses 2'-OMe and 2'-F; other modifications have fewer examples
- **Context-free:** we don't model the target mRNA sequence (OligoFormer does this better — use it for sequence design)
- **GP uncertainty is approximate:** not a rigorous Bayesian guarantee
- **GP accuracy is modest:** Pearson r=0.212 — designed for uncertainty quantification, not maximum prediction accuracy

OligoVoid is best used as a **gap-finding and experiment-prioritization tool**. It answers "what should I try next?" not "will this definitely work?"

---

## References

1. Reynolds A, et al. **Rational siRNA design for RNA interference.** *Nature Biotechnology*. 2004;22(3):326-330.
2. Khvorova A, et al. **Functional siRNAs and miRNAs exhibit strand bias.** *Cell*. 2003;115(2):209-216.
3. Huesken D, et al. **Design of a genome-wide siRNA library using an artificial neural network.** *Nature Biotechnology*. 2005;23(8):995-1001.
4. Setten RL, et al. **The current state and future directions of RNAi-based therapeutics.** *Nature Reviews Drug Discovery*. 2019;18(6):421-446.
5. Foster DJ, et al. **Advanced siRNA designs further improve in vivo performance of GalNAc-siRNA conjugates.** *Molecular Therapy*. 2018;26(3):708-717.
6. O'Reilly D, et al. **Systematic evaluation of position-specific tolerability of seven backbone and ribose modifications.** *Nucleic Acid Therapeutics*. 2025.
7. Dar SA, et al. **siRNAmod: A database of experimentally validated chemically modified siRNAs.** *Scientific Reports*. 2016;6:20031.
8. He S, et al. **CMsiRNAdb: a database of chemically modified SiRNA silencing efficiency.** *BMC Bioinformatics*. 2026;27:15.
9. Davis SM, et al. **Systematic analysis of siRNA and mRNA features impacting fully chemically modified siRNA efficacy.** *Nucleic Acids Research*. 2025;53(12):gkaf479.
10. Jackson AL, et al. **Widespread siRNA off-target transcript silencing mediated by seed region sequence complementarity.** *RNA*. 2006;12(7):1179-1187.

---

## Citation

```bibtex
@software{reddy2026oligovoid,
  author = {Reddy, Manas},
  title = {OligoVoid: Generative AI for siRNA Chemical Modification Space Exploration},
  year = {2026},
  url = {https://github.com/ManasReddy1/oligovoid}
}
```

---

## License

MIT

---

Built by **Manas Reddy** · [GitHub](https://github.com/ManasReddy1)
