# OligoVoid Submission Checklist

## arXiv (Submit this week)
- [ ] Register at [arxiv.org](https://arxiv.org) (if not already)
- [ ] Submit to **cs.LG** (primary) + **q-bio.BM** (cross-list)
- [ ] Title: "OligoVoid: Generative Active Learning for Systematic Exploration of siRNA Chemical Modification Design Space"
- [ ] Upload: `oligovoid_paper.tex`, `references.bib`, `neurips_2025.sty`
- [ ] Abstract: copy from LaTeX (250 words)
- [ ] Add to comments: "Code available at https://github.com/ManasReddy1/OligoVoid"
- [ ] License: CC BY 4.0

## ISMB 2026 Poster (May 7 deadline)
- [ ] Go to [iscb.org/ismb2026](https://www.iscb.org/ismb2026)
- [ ] Submit 1-page abstract (500 words max)
- [ ] Category: "Machine Learning in Computational Biology"
- [ ] Include: Table 1 (prediction comparison), calibration ECE, CVAE metrics
- [ ] You DO NOT need a full paper for a poster — just the abstract
- [ ] Mention: "Code and interactive dashboard available at github.com/ManasReddy1/OligoVoid"

## NeurIPS 2026 Workshop (August-September 2026)
- [ ] Watch for: **"AI for New Drug Modalities"** workshop
- [ ] Watch for: **"AI for Science"** workshop at ICML 2026
- [ ] Watch for: **"Machine Learning for Drug Discovery"** (ML4DD)
- [ ] Target: 4-page workshop paper (trim Sections 2 + 5)
- [ ] Highlight VPA as the novel contribution

## NeurIPS 2026 Main Track
- [ ] Deadline: ~May 2026 (check neurips.cc)
- [ ] Would need: abstract by ~May 4
- [ ] Honest assessment: achievable if wet-lab validation or stronger baselines added
- [ ] Key reviewer concern to address: GP Pearson r=0.14 is modest
- [ ] Counterargument: GP is for calibrated uncertainty, not max accuracy
- [ ] Strengthen with: OligoFormer integration, larger CVAE, more ablations

## After arXiv Posting
- [ ] Tweet with relevant tags: @Alnylam, @insaboratory, @AlanylAmRNA
- [ ] Post to r/MachineLearning with [R] tag
- [ ] Post to r/bioinformatics
- [ ] LinkedIn post with latent space UMAP visualization screenshot
- [ ] Email Anastasia Khvorova lab (UMass RNA Therapeutics Institute)
      — they publish siRNA modification data and might collaborate or cite
- [ ] Email OligoFormer authors — propose integration / joint work
- [ ] Email Dawn O'Reilly (position-specific tolerability paper) — cite overlap

## Before Any Submission — Final Checks
- [ ] Run `pdflatex oligovoid_paper.tex && bibtex oligovoid_paper && pdflatex oligovoid_paper.tex && pdflatex oligovoid_paper.tex`
- [ ] Verify page count is 8 (main) + appendix
- [ ] Check all table numbers match code output
- [ ] Verify all citations resolve (no `[?]` in PDF)
- [ ] Confirm GitHub repo is public
- [ ] Add LICENSE file to repo (MIT)
- [ ] Run all benchmarks one final time and cross-check numbers

## Key Numbers to Verify Before Submission
| Metric | Value | Source |
|--------|-------|--------|
| GP Pearson r (test) | 0.140 | `run_benchmark_comparison()` |
| GP RMSE | 25.4% | `run_benchmark_comparison()` |
| ECE | 0.027 | `evaluate_uncertainty_calibration()` |
| CVAE validity | 96.5% | `evaluate_generation_quality()` |
| CVAE novelty | 100% | `evaluate_generation_quality()` |
| Void candidates | 2,397 | `enumerate_modification_voids()` |
| Training sequences | 3,535 | `oligoformer_combined.csv` |
| FDA drugs | 8 | `PUBLISHED_MODIFICATIONS_DATASET` |
| VPA space explored | 8.5% | `benchmark_active_learning()` |
| EI space explored | 6.9% | `benchmark_active_learning()` |
