# OligoVoid

### Systematic Complement-Set Enumeration and Feasibility Scoring of the siRNA Chemical Modification Design Space

---

> *"Most modification patterns of approved or clinically investigated siRNAs are protected by patents, significantly restricting their broader application. Therefore, the development of proprietary modification patterns has been essential for siRNA therapeutics companies."*
> — Molecular Therapy: Methods & Clinical Development, 2025

---

## The Challenge

Eight siRNA drugs have received FDA approval since 2018. Every one of them depends on a carefully engineered chemical modification pattern — specific sugar modifications, backbone chemistries, and conjugates placed at specific positions across a 21-nucleotide duplex. These patterns are the difference between a molecule that degrades in seconds and a drug that silences a gene for six months.

The field faces a structural problem: **the modification design space is enormous, but exploration has been narrow.**

A 21-mer siRNA duplex has 42 modifiable positions (21 guide + 21 passenger). Each position can carry one of 8 established sugar modifications (2'-OMe, 2'-F, LNA, cEt, DNA, RNA, UNA, MOE). The backbone between each pair of positions can be natural phosphodiester (PO), phosphorothioate (PS), or mesyl phosphoramidate (MsPA). Terminal conjugates (GalNAc, cholesterol, LNP) determine tissue targeting.

The theoretical combinatorial space is astronomically large. Even after applying known biological constraints (no modifications at the cleavage site, no rigid modifications in the seed region, nuclease resistance thresholds), thousands of feasible patterns remain.

**Yet the published literature has converged on a remarkably narrow slice of this space.** Alnylam's Enhanced Stabilization Chemistry (ESC) — alternating 2'-OMe/2'-F with terminal PS and GalNAc conjugation — accounts for the modification logic behind four of eight approved drugs (Givosiran, Lumasiran, Inclisiran, Vutrisiran). Most academic labs test 5–10 patterns per paper, typically minor variations of ESC. Companies keep their best patterns as trade secrets behind patent walls.

**Nobody has systematically mapped what has been tested versus what has not.**

Existing databases like siRNAmod (Dar et al., *Scientific Reports*, 2016; 4,894 sequences) and CMsiRNAdb (He et al., *BMC Bioinformatics*, 2026; 43,153 sequences from 90 patents) catalog chemically modified siRNAs. But they are **sequence-level repositories** — they store individual siRNA sequences with their modifications, not **pattern-level analysis tools**. They answer "what modifications does this siRNA have?" not "which position × modification combinations have never been tested across all published siRNAs?"

OligoVoid fills this gap.

---

## What OligoVoid Does

OligoVoid performs five operations that, to our knowledge, have not been combined in any published tool:

### 1. Position × Modification Co-occurrence Mapping

OligoVoid builds a matrix of 42 positions × 8 modifications = 336 cells, separately for guide and passenger strands. Each cell counts how many published siRNA patterns use that specific modification at that specific position.

This immediately reveals the structure of the field's exploration:
- **2'-OMe and 2'-F** appear at nearly every position (the ESC backbone)
- **DNA** appears widely due to early academic work with unmodified controls
- **LNA, cEt, UNA, MOE** are almost entirely absent from published siRNA guide strands
- The **passenger strand** has even more voids than the guide strand

The heatmap visualization makes this visible at a glance — red cells are voids (0 published occurrences), green cells are well-explored.

### 2. Void Enumeration with Biological Filtering

Starting from known patterns, OligoVoid generates all variants with 1, 2, or 3 position changes and filters them through biological feasibility rules:

- **Cleavage site integrity**: Guide positions 10–11 must remain RNA or DNA. Argonaute2 cleaves the target mRNA between guide nucleotides 10 and 11 (Liu et al., *Science*, 2004). Any bulky modification here abolishes catalytic activity.
- **Seed region constraints**: Guide positions 2–8 form the "seed" that initiates target recognition (Bartel, *Cell*, 2009). Rigid modifications (LNA, cEt) here impair RISC loading (Obad et al., *Nature Genetics*, 2011).
- **Consecutive LNA limit**: More than 3 consecutive LNA nucleotides create excessive rigidity that prevents duplex unwinding during RISC activation.
- **Minimum nuclease resistance**: Patterns with insufficient sugar/backbone protection are filtered as non-viable drug candidates.

This produces **2,397 biologically feasible void candidates** from 60 seed patterns.

### 3. Multi-Dimensional Biophysics Feasibility Scoring

Each void is scored across four dimensions using rule-based models derived from published thermodynamic and biochemical data:

**Thermodynamic Stability (20% weight)**
Predicts the change in duplex melting temperature (ΔTm) from the native RNA duplex. Each modification contributes a position-independent ΔTm increment: 2'-OMe (+1.0°C/position), 2'-F (+1.8°C), LNA (+4.0°C), UNA (−2.0°C), DNA (−1.5°C). These values derive from optical melting studies (Koshkin et al., *Tetrahedron*, 1998; Pinheiro et al., *Science*, 2012). An optimal window of +5 to +15°C is enforced — below this the duplex is too unstable, above it the duplex is too rigid for RISC unwinding.

**RISC Loading Efficiency (35% weight — highest)**
This is the most critical bottleneck. A perfectly stable duplex is useless if Argonaute2 cannot load the guide strand. Scoring rules:
- Each LNA in the seed region: −15 points (Elmén et al., *Nature*, 2008)
- Each cEt in the seed region: −12 points
- Any modification at the cleavage site: −25 points (fatal)
- UNA at guide position 1: +8 points (promotes asymmetric loading; Vaish et al., *Nucleic Acids Research*, 2011)
- Overall strand rigidity penalty if >30% of guide positions carry LNA or cEt

**Nuclease Resistance (25% weight)**
Terminal PS linkages at 5' and 3' ends provide the primary defense against exonucleases (Eckstein, *Nucleic Acids Research*, 2014). Sugar modifications contribute additional protection. Unprotected RNA positions incur −5 points each.

**Off-Target Risk (20% weight)**
2'-OMe modifications in the passenger strand seed region reduce passenger-strand-mediated off-target silencing (Jackson et al., *RNA*, 2006). UNA at guide positions 2–7 reduces miRNA-like off-targeting. Heavy PS backbone (>10 linkages) increases immunogenicity risk.

**Composite score**: weighted sum normalized to 0–100.

**Calibration results** (validated against known patterns):
| Pattern | Overall Score | Interpretation |
|---------|-------------|---------------|
| Alnylam ESC (Inclisiran) | 88.3 | Gold standard — correctly high |
| All-2'-F guide | 92.0 | High RISC loading, good stability |
| Unmodified RNA | 43.8 | No drug viability — correctly low |
| LNA-heavy (>50% LNA) | 47.7 | RISC loading blocked — correctly penalized |

### 4. Active Learning for Experiment Prioritization (DMTL)

OligoVoid implements a Design-Make-Test-Learn (DMTL) cycle engine that answers the question: *"If I can only synthesize N siRNAs, which void patterns teach me the most about the modification space?"*

The active learner uses three components:
- **Uncertainty estimation**: combines Hamming distance to nearest known pattern, position-level modification rarity, and neighborhood sparsity in feature space
- **Expected improvement**: probability of exceeding the current best knockdown, adjusted for pattern feasibility
- **Diversity bonus**: prevents recommending patterns that are too similar to each other

Four acquisition functions are available:
- **Balanced**: weighted combination of all three (default)
- **Exploitation**: maximize predicted knockdown
- **Exploration**: maximize space coverage
- **Uncertainty**: maximize information gain

Simulation results (8 cycles starting from 5 known patterns):
- **26.4% uncertainty reduction** (0.527 → 0.394)
- Diminishing returns visible across cycles — consistent with information-theoretic predictions
- The learner systematically explores different regions: guide position 1 variants first, then seed region, then 3' end

### 5. Void Closure Velocity

A temporal metric tracking how fast each void is being filled by the field. Paper counts are measured across four windows (2018–2020, 2020–2022, 2022–2024, 2024–2026) and a linear trend is fitted. Voids are classified as:
- **HOT**: accelerating publication rate — other labs are converging on this combination
- **WARMING**: detectable but slow trend
- **COLD**: no activity for 5+ years
- **CLOSED**: no longer a void (>5 papers in latest window)

This creates competitive intelligence: a researcher can see which voids are about to be filled by others and prioritize accordingly.

---

## What Makes OligoVoid Novel

### No existing tool does this

| Capability | siRNAmod (2016) | CMsiRNAdb (2026) | OligoVoid |
|-----------|----------------|-----------------|-----------|
| Stores modified siRNA sequences | Yes (4,894) | Yes (43,153) | Yes (60 curated) |
| Position × modification heatmap | No | Partial (frequency plots) | **Full interactive heatmap** |
| Identifies void (untested) patterns | No | No | **Yes — 2,397 enumerated** |
| Scores void feasibility | No | Efficacy prediction (Cm-siRPred) | **4-dimensional biophysics + LLM** |
| Active learning for experiment design | No | No | **Yes — DMTL with 4 acquisition functions** |
| Void Closure Velocity tracking | No | No | **Yes** |
| Interactive custom pattern builder | No | No | **Yes** |

The closest published work is O'Reilly et al. (*Nucleic Acid Therapeutics*, 2025), who systematically evaluated 522 siRNA variants across 7 backbone and sugar modifications. Their work is the most comprehensive positional tolerability study to date, but it is a **wet-lab screen** of individual sequences, not a **computational tool for mapping the full design space**. OligoVoid complements this kind of experimental work by identifying which regions of the space remain unexplored.

### Five novelty claims

1. **First systematic complement-set enumeration** of the siRNA modification design space — identifying what *hasn't* been tested rather than cataloging what has
2. **First position-specific co-occurrence heatmap** built from published siRNA modification data, visualizing exploration density across all 42 positions × 8 modifications
3. **First biophysics-based feasibility scorer for void patterns** using established ΔTm, RISC loading, and nuclease resistance rules
4. **First active learning loop (DMTL)** for siRNA modification space exploration, demonstrating information-optimal experiment prioritization
5. **First temporal void metric** (Void Closure Velocity) for competitive intelligence in oligonucleotide design

---

## Known Pattern Database

OligoVoid ships with 60 curated published modification patterns from 5 sources:

| Source | Count | Citation | Key Contribution |
|--------|-------|----------|-----------------|
| FDA-approved drugs | 8 | FDA approval documents; Setten et al., *Nature Reviews Drug Discovery*, 2019 | Patisiran, Givosiran, Lumasiran, Inclisiran, Vutrisiran, Fitusiran, Nedosiran, Teprasiran |
| Reynolds rules | 20 | Reynolds et al., *Nature Biotechnology*, 2004 | 8 criteria for siRNA functionality from 180 siRNAs |
| Khvorova group | 15 | Khvorova et al., *Cell*, 2003; Foster et al., *Molecular Therapy*, 2018 | Fully modified 2'-OMe/2'-F chemistries, ESC platform |
| Ui-Tei rules | 10 | Ui-Tei et al., *Nucleic Acids Research*, 2004 | Thermodynamic asymmetry guidelines |
| Academic variants | 7 | Multiple sources (LNA, UNA, MsPA, cEt, MOE studies) | Non-standard modification exploration |

### Coverage analysis
- **336 unique position × modification combinations** possible (42 positions × 8 sugars)
- **151 combinations tested** in at least one published pattern (44.9%)
- **185 combinations never tested** (55.1%) — these are the voids
- **Most tested position**: Guide position 1 (all 8 modifications tested)
- **Rarest modification**: UNA (3 patterns)
- **Most void-dense strand**: Passenger (more unexplored than guide)

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │         BROWSER (localhost:8000)      │
                    │                                       │
                    │  Tab 1: Modification Heatmap          │
                    │  Tab 2: Top Scored Voids              │
                    │  Tab 3: DMTL Active Learning          │
                    │  Tab 4: Void Closure Velocity         │
                    │  Tab 5: Custom Pattern Scorer         │
                    └──────────────┬──────────────────────┘
                                   │ REST API (11 endpoints)
                    ┌──────────────┴──────────────────────┐
                    │          FASTAPI BACKEND              │
                    │                                       │
                    │  modification_grammar.py               │
                    │    └─ 8 sugars, 3 backbones, 4 conj.  │
                    │    └─ SiRNAModificationPattern class   │
                    │    └─ 10 biophysics constraint rules   │
                    │    └─ 5 known reference patterns       │
                    │    └─ Pattern enumeration engine       │
                    │                                       │
                    │  literature_parser.py                   │
                    │    └─ 60 curated published patterns    │
                    │    └─ Position co-occurrence matrix    │
                    │    └─ PubMed E-utilities integration   │
                    │                                       │
                    │  void_detector.py                       │
                    │    └─ 1/2/3-position variant generator │
                    │    └─ Biological feasibility filter    │
                    │    └─ Hamming distance calculator      │
                    │    └─ Void type classifier (4 types)  │
                    │                                       │
                    │  feasibility_scorer.py                  │
                    │    └─ Thermodynamic scorer (ΔTm model) │
                    │    └─ RISC loading scorer              │
                    │    └─ Nuclease resistance scorer       │
                    │    └─ Off-target risk scorer           │
                    │    └─ Claude API enhanced reasoning    │
                    │                                       │
                    │  active_learner.py                      │
                    │    └─ Uncertainty estimation           │
                    │    └─ Expected improvement             │
                    │    └─ Diversity-aware selection        │
                    │    └─ DMTL cycle simulation            │
                    │                                       │
                    │  velocity_tracker.py                    │
                    │    └─ 4-window publication trend       │
                    │    └─ HOT/WARMING/COLD classification  │
                    │                                       │
                    │  database.py                            │
                    │    └─ 6 SQLAlchemy tables (SQLite)     │
                    └──────────────────────────────────────┘
```

---

## Quick Start

```bash
git clone https://github.com/ManasReddy1/OligoVoid.git
cd OligoVoid/backend
pip install -r requirements.txt

# Initialize database with seed data
python -c "
from database import init_db, seed_known_patterns, seed_demo_voids
init_db(); seed_known_patterns(); seed_demo_voids()
print('Ready')
"

# Start server
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000**

### Enable Claude API enhanced scoring (optional)

```bash
cp .env.example .env
# Edit .env → add ANTHROPIC_API_KEY
```

Without an API key, all scoring is rule-based biophysics (fully functional). The Claude API adds expert-level reasoning, predicted knockdown percentages, failure mode analysis, and specific experiment recommendations.

---

## Assumptions and Limitations

Every tool makes assumptions. These are ours, stated explicitly:

### Assumption 1: Published patterns approximate the explored space
**Reality**: Pharmaceutical companies test thousands of patterns internally and patent them without publishing efficacy data. The true explored space is larger than 45%. OligoVoid sees only publicly accessible data. This means some "voids" may have been tested behind closed doors. We accept this limitation because: (a) the publicly explored space is what the research community can build upon, and (b) even if a company tested a pattern, if the result is unpublished, the scientific community gains no knowledge from it.

### Assumption 2: Biophysics scoring is additive and position-independent
**Reality**: Thermodynamic stability depends on nearest-neighbor stacking interactions — a 2'-F at position 5 next to an LNA at position 6 behaves differently than either alone (SantaLucia, *PNAS*, 1998). Our model uses per-position ΔTm increments with sub-additive scaling (√n correction), which captures the general trend but not sequence-specific effects. A more accurate model would use nearest-neighbor parameters, but this requires knowing the actual RNA sequence, which is target-dependent. OligoVoid scores modification patterns, not specific sequences.

### Assumption 3: RISC loading is predictable from modification pattern alone
**Reality**: RISC loading depends on thermodynamic asymmetry between the 5' ends of the two strands (Khvorova et al., *Cell*, 2003; Schwarz et al., *Cell*, 2003), which is sequence-dependent. Our model captures modification-level effects (LNA rigidity blocks loading, UNA at position 1 promotes it) but not sequence-level asymmetry. This is a deliberate design choice: OligoVoid is a pattern-level tool, not a sequence design tool.

### Assumption 4: 3-position-change exploration depth is sufficient
**Reality**: Patterns differing by 4+ positions from any known pattern could contain interesting designs. We limit to 3 changes to keep the void count tractable (2,397 vs potentially millions) and because patterns very far from known territory have higher uncertainty and lower confidence scores. Future versions could expand this with smarter sampling.

### Assumption 5: Void Closure Velocity uses simulated trend data
**Reality**: Real velocity tracking requires periodic PubMed queries over months or years. The proof-of-concept ships with simulated publication counts to demonstrate the framework. The PubMed integration endpoint is functional and can be connected to real data.

### What OligoVoid does NOT do
- **Does not replace wet-lab experiments.** Every void must be synthesized and tested before drawing conclusions.
- **Does not predict absolute knockdown efficacy.** Scores are relative feasibility rankings, not quantitative activity predictions.
- **Does not handle ASO (antisense oligonucleotide) design.** ASOs have different biology (RNase H mechanism, gapmer architecture). The ontology is siRNA-specific.
- **Does not perform molecular dynamics simulations.** Thermodynamic scoring is rule-based, not physics-based.
- **Does not account for manufacturing complexity.** Some modifications (MsPA, certain LNA positions) are harder to synthesize. This is not reflected in the score.

---

## Future Scope

### Immediate extensions (proof-of-concept → research tool)
- **Scale the known pattern database** from 60 to 5,000+ by integrating CMsiRNAdb (43,153 sequences; He et al., 2026) and siRNAmod (4,894 sequences; Dar et al., 2016)
- **Incorporate the O'Reilly 2025 dataset** — 522 systematically evaluated siRNA variants with positional tolerability data for 7 modification types
- **Add sequence-dependent thermodynamic scoring** using nearest-neighbor parameters (SantaLucia, 1998) for target-specific feasibility
- **Validate predictions against experimental data** — blind-score known patterns and measure rank correlation with published knockdown IC50 values

### Research extensions
- **Train a lightweight ML model** on the known pattern → efficacy mapping. Even a random forest on 60 data points with biophysics features could outperform pure rule-based scoring.
- **Graph neural network analysis** — represent modification patterns as molecular graphs and learn position-interaction effects
- **Multi-objective Pareto optimization** — find void patterns that simultaneously maximize efficacy, stability, and safety while minimizing off-target risk and synthesis cost
- **Patent landscape overlay** — cross-reference void patterns against patent claims to identify freedom-to-operate opportunities (critical for companies developing proprietary chemistries)

### Platform-level scope
- **Wet-lab validation partnership** — synthesize and test the top 10 OligoVoid-recommended patterns. One confirmed hit validates the entire framework.
- **Foundation model for oligonucleotide design** — use the modification grammar as a tokenizer for training a transformer on siRNA activity data across thousands of sequences
- **ASO extension** — gapmers, mixmers, splice-switching oligos. The architecture (position × modification matrix, biophysics scoring, active learning) generalizes directly.
- **Real-time DMTL integration** — connect OligoVoid to a laboratory information management system (LIMS) so that each experimental result automatically updates the model and generates the next recommendation

### Who this is built for

This tool is designed for **computational biology teams at oligonucleotide therapeutics companies** — specifically teams building ML-driven platforms for pan-modality therapeutic discovery using active learning and iterative design cycles. The DMTL engine directly demonstrates the Design-Make-Test-Learn paradigm that underlies modern computational drug discovery platforms. The biophysics scoring shows understanding of the real constraints (RISC loading, nuclease stability, off-target silencing) that govern whether a modification pattern can become a drug. The void detection framework provides a systematic alternative to intuition-driven pattern selection.

---

## References

1. Reynolds A, Leake D, Boese Q, Scaringe S, Marshall WS, Khvorova A. **Rational siRNA design for RNA interference.** *Nature Biotechnology*. 2004;22(3):326-330. doi:10.1038/nbt936

2. Khvorova A, Reynolds A, Jayasena S. **Functional siRNAs and miRNAs exhibit strand bias.** *Cell*. 2003;115(2):209-216.

3. Ui-Tei K, Naito Y, Takahashi F, et al. **Guidelines for the selection of highly effective siRNA sequences for mammalian and chick RNA interference.** *Nucleic Acids Research*. 2004;32(3):936-948.

4. Setten RL, Rossi JJ, Han SP. **The current state and future directions of RNAi-based therapeutics.** *Nature Reviews Drug Discovery*. 2019;18(6):421-446.

5. Foster DJ, Brown CR, Shaikh S, et al. **Advanced siRNA designs further improve in vivo performance of GalNAc-siRNA conjugates.** *Molecular Therapy*. 2018;26(3):708-717.

6. O'Reilly D, Furgal R, Hariharan VN, et al. **Systematic evaluation of position-specific tolerability of seven backbone and ribose modifications in fully chemically stabilized siRNAs.** *Nucleic Acid Therapeutics*. 2025. doi:10.1089/nat.2024.0077

7. Dar SA, Thakur A, Qureshi A, Kumar M. **siRNAmod: A database of experimentally validated chemically modified siRNAs.** *Scientific Reports*. 2016;6:20031.

8. He S, Chen C, Pan X, Xue G, Deng K. **CMsiRNAdb: a database of chemically modified SiRNA silencing efficiency for nucleic acid drug design.** *BMC Bioinformatics*. 2026;27:15.

9. Davis SM, Hildebrand S, MacMillan HJ, et al. **Systematic analysis of siRNA and mRNA features impacting fully chemically modified siRNA efficacy.** *Nucleic Acids Research*. 2025;53(12):gkaf479.

10. Jackson AL, Burchard J, Schelter J, et al. **Widespread siRNA "off-target" transcript silencing mediated by seed region sequence complementarity.** *RNA*. 2006;12(7):1179-1187.

11. Eckstein F. **Phosphorothioates, essential components of therapeutic oligonucleotides.** *Nucleic Acids Research*. 2014;42(22):13987-14000.

12. SantaLucia J Jr. **A unified view of polymer, dumbbell, and oligonucleotide DNA nearest-neighbor thermodynamics.** *PNAS*. 1998;95(4):1460-1465.

13. Elmén J, Lindow M, Schütz S, et al. **LNA-mediated microRNA silencing in non-human primates.** *Nature*. 2008;452(7189):896-899.

14. Bartel DP. **MicroRNAs: target recognition and regulatory functions.** *Cell*. 2009;136(2):215-233.

---

## Citation

```bibtex
@software{reddy2026oligovoid,
  author = {Reddy, Manas},
  title = {OligoVoid: Systematic Gap Detection in the siRNA Chemical Modification Design Space},
  year = {2026},
  url = {https://github.com/ManasReddy1/OligoVoid}
}
```

---

## License

MIT

---

Built by **Manas Reddy** · [GitHub](https://github.com/ManasReddy1)
