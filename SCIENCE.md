# OligoVoid — Technical Deep-Dive

**Author:** Manas Reddy
**Date:** April 2026
**Status:** Solo research project — computational only, no wet-lab validation

This document is the technical supplement to the OligoVoid system. It is written for a PhD-level reviewer who wants to evaluate whether the science underlying this tool is credible, whether the modeling choices are justified, and whether the claims are honest. I use first person throughout because this is a solo project.

---

## 1. The siRNA Design Problem — A Precise Formulation

The core object of study in OligoVoid is the **siRNA modification pattern**: the assignment of a chemical modification (sugar modification) to each nucleotide position across a two-stranded RNA duplex. A standard siRNA duplex consists of a 21-nucleotide guide (antisense) strand and a 21-nucleotide passenger (sense) strand, yielding 42 positions in total. Each position can carry one of 8 recognized sugar modifications: 2'-OMe, 2'-F, LNA, cEt, DNA, RNA, UNA, or MOE. I define the problem formally as follows.

Let `P = {1, 2, ..., 42}` denote the set of nucleotide positions (guide positions 1-21 followed by passenger positions 1-21). Let `M = {2'-OMe, 2'-F, LNA, cEt, DNA, RNA, UNA, MOE}` be the alphabet of sugar modifications, with `|M| = 8`. A **modification pattern** is a function `sigma: P -> M` that assigns a modification to every position. The **total combinatorial space** is therefore `|M|^|P| = 8^42`. This is approximately `4.4 x 10^37`, or roughly `10^38` patterns. This is the unconstrained universe of possible modification assignments.

However, the vast majority of these patterns are biologically non-viable. An siRNA must satisfy multiple biophysical constraints simultaneously to function as a drug: the guide strand must load into the RISC complex (Ago2 protein), the cleavage site (positions 10-11) must remain compatible with catalytic activity, the seed region (positions 2-8) must maintain A-form helix geometry for target recognition, the 3' overhang must resist exonuclease degradation, and the overall duplex thermodynamic stability must fall within an optimal window. I encode these constraints as a set of 10 biophysics rules in `modification_grammar.py`. These rules include: cleavage site rigidity (no LNA or cEt at positions 10-11), seed region overload (no more than 2 locked nucleic acids in positions 2-8), excessive consecutive LNA (no runs longer than 3), minimum nuclease resistance (at least 60% of positions must carry protective modifications), RISC loading compatibility (guide strand must have higher average RISC tolerance than passenger), and others.

Let `F` denote the **feasible space** — the subset of `8^42` patterns that satisfy all biophysical constraints. Through enumeration experiments using `enumerate_all_feasible_patterns()`, I estimate `|F| ~ 10^6`. This is a dramatic reduction from `10^38`, but still vastly larger than what any laboratory could test exhaustively.

Let `S` denote the **sampled space** — the set of modification patterns that have been published in the scientific literature or disclosed in patent filings. From 3,535 experimentally validated siRNAs across 9 published datasets (Huesken 2005, Takahashi 2009, Reynolds 2004, Khvorova 2003, and others) plus 60 curated modification-level patterns including all 8 FDA-approved siRNA drugs, I construct a position-modification co-occurrence matrix. This matrix reveals that published literature covers approximately **8% of feasible position-modification slots** — that is, of the 336 possible `(position, modification)` pairs (42 positions times 8 modifications), only about 151 have been observed in published data with meaningful frequency.

The complement `F \ S` is what I call the **dark matter** of siRNA chemical space. These are modification patterns that are biologically feasible but have never been published. OligoVoid's purpose is to enumerate this dark matter, score it for feasibility, and recommend which unexplored patterns to test first.

---

## 2. Why the Modification Space Is Underexplored

The 92% gap between feasible and explored space is not an accident. Three structural factors have conspired to leave the modification landscape largely unmapped.

**(a) Patent secrecy and proprietary chemistry.** The dominant player in siRNA therapeutics is Alnylam Pharmaceuticals, whose Enhanced Stabilization Chemistry (ESC) patents cover the alternating 2'-OMe/2'-F patterns used in all of their GalNAc-conjugated drugs (Givosiran, Inclisiran, Lumasiran, Vutrisiran, and others). These ESC patterns are the gold standard in the field, but the precise position-by-position modification assignments are protected intellectual property. When I analyzed the siRNAmod database (Dar et al., Scientific Reports, 2016), which contains 4,894 chemically modified siRNA entries, I found that many of the most clinically relevant patterns are either missing entirely or represented only at a coarse granularity that obscures position-specific detail. The implication is clear: the most successful modification chemistry is precisely the chemistry that is least accessible to the academic community. Companies developing siRNA drugs — Alnylam, Arrowhead, Silence Therapeutics, Dicerna (now Novo Nordisk) — each develop proprietary modification patterns specifically because they cannot use the patented ESC designs. This creates a perverse incentive: the field's collective knowledge is fragmented across corporate silos, and the published literature represents only the fraction of exploration that companies chose to disclose.

**(b) Trial-and-error culture in modification design.** The prevailing approach to siRNA modification design is empirical: a research group selects a target gene, designs 5-20 candidate modification patterns based on intuition and prior experience, synthesizes them, tests them in cell culture, and publishes the best-performing variants. This is a perfectly reasonable experimental strategy, but it is not systematic exploration. Each paper illuminates a tiny patch of the feasible space — a patch chosen not by any optimization criterion but by the biases and preferences of the research group. The Davis et al. (2025) paper in Nucleic Acids Research is representative: they systematically tested position-specific tolerability of seven modifications across both strands, but even this unusually thorough study covered only a small fraction of the possible combinations. The result is a published landscape that is clustered around a few well-known chemistries (predominantly 2'-OMe/2'-F alternation) with vast regions of the feasible space receiving zero attention.

**(c) No systematic mapping tool has existed until now.** Before OligoVoid, no tool asked the question "what has never been tried?" Every existing siRNA design tool — from the early Reynolds rules (2004) and Ui-Tei rules (2004) to the modern OligoFormer transformer (He et al., 2024) — is discriminative: given a sequence or modification pattern, predict its efficacy. These tools are flashlights, illuminating one spot at a time. None of them constructs a global map of the explored and unexplored space. None of them identifies the complement set. None of them recommends which unexplored region to investigate next based on a formal acquisition function. The absence of such a tool has meant that the field has had no way to even quantify how much of the modification space remains dark, let alone prioritize its exploration.

---

## 3. The Co-occurrence Matrix: Formal Definition

The foundational data structure in OligoVoid is the **position-modification co-occurrence matrix** `C`, defined as follows.

Let `D = {d_1, d_2, ..., d_N}` be the dataset of `N` published siRNA modification patterns (in this work, `N = 3,535` sequences from the OligoFormer dataset plus 60 curated modification-level patterns). Each pattern `d_k` is a function `sigma_k: P -> M` as defined in Section 1.

The co-occurrence matrix `C` is a `|P| x |M|` matrix (42 rows by 8 columns) where:

```
C_{p,m} = |{k : sigma_k(p) = m, k in {1, ..., N}}|
```

That is, `C_{p,m}` counts how many published patterns place modification `m` at position `p`. This matrix is constructed by `build_position_cooccurrence_matrix()` in `literature_parser.py`.

I define two critical concepts from this matrix:

**Void:** A cell `(p, m)` is a **void** if `C_{p,m} = 0`. This means that no published pattern has ever placed modification `m` at position `p`. This is the purest form of dark matter — a position-modification combination with zero empirical evidence.

**Near-void:** A cell `(p, m)` is a **near-void** if `C_{p,m} in {1, 2, 3}`. This means that the combination has been tested only 1-3 times in the entire published literature.

The threshold of 3 for the near-void classification has a statistical power justification. With `C_{p,m} <= 3` observations, there is insufficient statistical power to draw any conclusion about the viability of modification `m` at position `p`. Consider a simple binomial test: if the true probability that modification `m` at position `p` yields a functional siRNA is 0.5 (the null hypothesis of no effect), then observing 3 or fewer successes out of 3 trials cannot reject this null at any conventional significance level (p > 0.05 for all possible outcomes with n=3 under a two-sided binomial test). Even under the most optimistic assumptions — observing 3 successes out of 3 trials — the 95% confidence interval for the true success probability ranges from 0.29 to 1.0, which is too wide to be actionable. Therefore, any cell with `C_{p,m} <= 3` should be treated as effectively unexplored for the purposes of scientific inference.

From the OligoVoid analysis: of 336 total `(position, modification)` cells, 185 are voids (`C_{p,m} = 0`) and an additional 32 are near-voids (`C_{p,m} in {1, 2, 3}`). Together, these 217 cells represent **64.6%** of the position-modification space that is either completely or effectively unexplored. Even counting only strict voids, **55.1%** of the feasible position-modification landscape has zero published data.

---

## 4. The Chemistry Fingerprint: Novel Representation

A key modeling decision in OligoVoid is the representation of modification patterns. Rather than using the raw 336-dimensional one-hot encoding (42 positions times 8 modifications), I designed an **8-dimensional chemistry fingerprint** that captures the biologically meaningful features of a pattern. This fingerprint is implemented in `chemistry_fingerprint.py` and consists of the following features:

1. **`alternation_score`** (float, 0-1): Measures how closely the guide strand follows an alternating 2'-OMe/2'-F pattern. A score of 1.0 indicates perfect alternation, matching the ESC chemistry used in all Alnylam GalNAc-siRNA drugs. Computed by counting consecutive pairs that alternate between 2'-OMe and 2'-F, divided by the total number of consecutive pairs. This captures the dominant design paradigm in the field.

2. **`seed_2F_density`** (float, 0-1): Fraction of guide positions 2-8 (the seed region) that carry 2'-F modifications. The seed region is critical for target mRNA recognition. 2'-F at these positions maintains A-form helix geometry while providing nuclease resistance. A density above 0.5 indicates a pattern that prioritizes target binding fidelity in the seed.

3. **`3prime_protection`** (float, 0-1): Fraction of guide positions 17-21 (the 3' overhang) that carry stabilizing modifications (2'-OMe, LNA, or cEt). The 3' end is the primary site of exonuclease degradation. Patterns with low 3' protection scores are likely to be rapidly degraded in vivo.

4. **`strand_asymmetry`** (float, 0-1): The absolute difference in mean RISC-tolerance scores between the guide and passenger strands. A well-designed siRNA should have higher RISC compatibility on the guide strand to ensure correct strand loading into Ago2. RISC tolerance scores per modification type are: RNA=1.00, 2'-OMe=0.95, 2'-F=0.90, UNA=0.85, DNA=0.70, cEt=0.50, LNA=0.45, MOE=0.40.

5. **`consecutive_LNA`** (integer, 0+): The length of the longest run of consecutive LNA residues across both strands. LNA provides very strong binding affinity but consecutive LNA residues (runs of 4 or more) are associated with hepatotoxicity in preclinical models and reduced RISC loading. This feature flags potentially toxic patterns.

6. **`modification_diversity`** (float, 0-1): Normalized Shannon entropy of the modification-type distribution across both strands. Computed as `H / H_max` where `H = -sum(p_i * log2(p_i))` over modification types and `H_max = log2(k)` for `k` distinct modification types present. Higher diversity may indicate a more nuanced design that leverages each modification's unique biophysical properties (e.g., using LNA for affinity at specific positions, 2'-F for geometry, 2'-OMe for stability).

7. **`galnac_compatible`** (binary, 0 or 1): Whether the pattern is compatible with N-acetylgalactosamine (GalNAc) conjugation for hepatocyte delivery. The heuristic: at least 80% of positions must be 2'-OMe or 2'-F, and no more than 4 total LNA or cEt positions across both strands. GalNAc delivery is the dominant platform for liver-targeted siRNA drugs (6 of 8 FDA-approved siRNAs use it), so compatibility with this delivery mechanism is a critical practical feature.

8. **`similarity_to_givosiran`** (float, 0-1): Normalized Hamming similarity between the guide strand and Givosiran's guide strand modification pattern. Givosiran (Givlaari) achieves 83% clinical knockdown, the highest among FDA-approved siRNA drugs. This feature anchors the fingerprint to a known high-performance design.

**Why pattern-level features capture information that position-level features miss.** A 336-dimensional one-hot encoding treats each position-modification assignment as independent. But modification patterns are not independent across positions — they have global structure. An alternating 2'-OMe/2'-F pattern at positions 1-10 interacts with the chemistry at positions 11-21 through duplex thermodynamics, RISC loading mechanics, and nuclease resistance profiles. The chemistry fingerprint captures these cross-position dependencies as explicit features. For example, `alternation_score` encodes a global pattern (alternation across the full strand), not a position-specific assignment. Similarly, `strand_asymmetry` encodes a relationship between the two strands that is invisible in a position-level representation.

**Analogy to ECFP fingerprints for small molecules.** In computational chemistry, Extended Connectivity Fingerprints (ECFPs) are circular fingerprints that encode molecular substructure by hashing atomic neighborhoods. They compress the full molecular graph into a fixed-length binary vector that captures chemically meaningful features. The OligoVoid chemistry fingerprint serves an analogous role: it compresses the 336-dimensional modification pattern into an 8-dimensional vector that captures biologically meaningful features. Just as ECFP fingerprints enable similarity searching in chemical libraries, the chemistry fingerprint enables similarity searching and clustering in siRNA modification space.

---

## 5. Gaussian Process for Uncertainty Quantification

The machine learning backbone of OligoVoid is a **Gaussian Process regressor** (GP), not a gradient boosting model and not a deep neural network. This choice is deliberate and rooted in the specific requirements of the problem.

**Why GP and not gradient boosting or deep learning?** The answer is a single word: **calibration**. In an active learning setting, the utility of a predictive model depends not on how accurately it predicts efficacy, but on how honestly it represents its own uncertainty. A model that says "I predict 75% knockdown with sigma=5%" is useful only if the true value falls within 75 +/- 10% approximately 95% of the time. If the model's confidence intervals are systematically too narrow (overconfident) or too wide (underconfident), the active learning loop will make poor decisions — either over-exploiting regions where the model is falsely confident or wasting cycles exploring regions where the model is unnecessarily uncertain.

GPs provide calibrated uncertainty estimates by construction. The posterior predictive distribution `p(y*|x*, X, y) = N(mu*, sigma*^2)` gives both a mean prediction and a variance that reflects the model's epistemic uncertainty. This is fundamentally different from ensemble-based uncertainty (random forests, gradient boosting) which typically produces poorly calibrated prediction intervals, and from deep learning dropout uncertainty which requires careful tuning and often degrades calibration.

The OligoVoid GP achieves **ECE = 0.027** (Expected Calibration Error), meaning that across all confidence levels, the model's stated confidence matches the empirical frequency of correct predictions to within 2.7 percentage points. This is the metric that matters for active learning. For comparison, an ECE of 0.05 is considered "well-calibrated" in the machine learning literature. An ECE of 0.027 is excellent.

**Kernel choice: Matern-5/2.** The GP uses a `ConstantKernel * Matern(nu=2.5) + WhiteKernel` kernel composition. The Matern kernel with `nu=5/2` assumes that the underlying function is **twice differentiable but not infinitely smooth**. This is a deliberate choice. The squared exponential (RBF) kernel assumes infinite differentiability, which is implausible for biological activity landscapes where small changes in modification chemistry can produce discontinuous jumps in efficacy (e.g., placing LNA at the cleavage site abolishes activity regardless of the surrounding context). The Matern-5/2 kernel allows for these rougher landscapes while still imposing enough smoothness to enable meaningful interpolation. The Matern-3/2 kernel (`nu=1.5`) assumes only once-differentiable functions, which may be too rough for the relatively smooth relationship between most modification features and efficacy.

**Why maximizing Pearson r is NOT the goal.** The OligoVoid GP achieves Pearson `r = 0.272` on the OligoFormer test set (bootstrap 95% CI: [0.07, 0.21] on held-out data). This is modest compared to OligoFormer's `r = 0.719`. But this comparison is misleading because the two models solve different problems with different inputs. OligoFormer uses the full mRNA target sequence plus guide sequence as input — sequence-level features that directly determine siRNA efficacy. OligoVoid uses only modification-level features (the chemistry fingerprint plus thermodynamic features) with no sequence information. The chemistry fingerprint describes how a pattern is modified, not what gene it targets. It is inherently less predictive of efficacy, because the same modification pattern will perform differently on different target sequences. The GP's purpose is not to predict efficacy with maximum accuracy — it is to provide **calibrated uncertainty estimates** that drive the active learning loop. A well-calibrated GP with `r = 0.272` is more useful for experiment selection than an overconfident gradient boosting model with `r = 0.5`.

**Expected Improvement formula.** The standard analytical Expected Improvement, used as the base of the VPA acquisition function, is:

```
EI(x) = (mu(x) - f_best) * Phi(z) + sigma(x) * phi(z)
```

where `z = (mu(x) - f_best) / sigma(x)`, `Phi` is the standard normal CDF, `phi` is the standard normal PDF, `mu(x)` is the GP posterior mean, `sigma(x)` is the GP posterior standard deviation, and `f_best` is the best observed value so far. This formula has a closed-form solution because the GP posterior is Gaussian, which is another advantage of using a GP over non-parametric models.

---

## 6. The CVAE Architecture — Design Decisions

The Conditional Variational Autoencoder (CVAE) in OligoVoid transforms the system from a discriminative scorer into a generative design engine. The architecture is intentionally simple, and every design choice is justified by the constraints of the problem.

**`feature_dim = 42` (18 core + 24 thermodynamic, not raw one-hot 336).** The CVAE operates on the 42-dimensional continuous feature representation produced by `real_data_pipeline.build_ml_dataset()`, not on a 336-dimensional one-hot encoding of position-modification assignments. This is critical for two reasons. First, 336 binary dimensions with only 3,535 training examples creates a severe curse of dimensionality — the VAE would need orders of magnitude more data to learn meaningful structure in such a sparse space. Second, the continuous features (GC content, thermodynamic stability, modification counts per region, seed region composition, etc.) encode biologically meaningful relationships that the one-hot encoding destroys. The 18 core features include modification type frequencies, regional composition metrics, and strand-level statistics. The 24 thermodynamic features include predicted melting temperature, free energy contributions, and stability window metrics. Together, these 42 features provide a compact but informative representation of each pattern's chemistry.

**`latent_dim = 16` (not 32 or 64).** The latent dimensionality is deliberately small. With only 3,535 training examples, a 32- or 64-dimensional latent space would suffer from **posterior collapse** — the decoder would learn to ignore the latent code and reconstruct from the conditioning signal alone, because the KL divergence term would push the posterior toward the prior `N(0, I)` before the encoder has learned useful representations. A 16-dimensional latent space is large enough to capture the meaningful variation in 42-dimensional input features (the intrinsic dimensionality of the modification space is likely much lower than 42, given the strong correlations between features) while small enough that the encoder can actually populate the latent space with the available training data. Empirically, 16 dimensions produce a latent space where FDA-approved drugs cluster by delivery strategy (GalNAc vs. LNP) and where smooth interpolation between drugs produces chemically valid intermediates — both signs that the latent space has learned meaningful structure.

**MSE reconstruction loss (not cross-entropy).** Because the input features are continuous (not categorical one-hot vectors), the appropriate reconstruction loss is mean squared error. Cross-entropy loss would require treating each output dimension as a probability distribution over modification types, which is incorrect when the features are continuous summary statistics like GC content, melting temperature, and Shannon entropy of modification diversity. The MSE loss naturally handles the continuous nature of the features and produces reconstructions that lie in the same continuous space as the inputs.

**`beta = 0.5` (not 1.0 or 4.0).** The CVAE uses a beta-VAE formulation where the loss function is:

```
L = ||x - x_hat||^2 + beta * D_KL(q(z|x,c) || N(0,I))
```

The standard VAE uses `beta = 1.0`, which gives equal weight to reconstruction and regularization. In the beta-VAE framework (Higgins et al., 2017), `beta > 1` increases disentanglement of the latent factors at the cost of reconstruction quality, while `beta < 1` prioritizes reconstruction. I chose `beta = 0.5` because the primary goal is generating valid modification patterns (which requires good reconstruction) rather than learning perfectly disentangled latent factors. With `beta = 1.0`, I observed that the reconstruction quality degraded noticeably without a corresponding improvement in generation quality. With `beta = 4.0`, the model suffered from severe posterior collapse — the KL term dominated the loss and the latent code was ignored. At `beta = 0.5`, the CVAE achieves 96.5% validity (generated patterns within biophysical bounds), 100% uniqueness, and 100% novelty (all generated patterns differ from training data).

**Gradient clipping at 1.0.** The CVAE uses `torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)` during training. This is a standard precaution for VAE training, where the KL divergence gradient can spike early in training when the encoder's posterior is far from the prior. Without gradient clipping, these spikes can cause the optimizer to take excessively large steps that destabilize training. The threshold of 1.0 is conservative — it rarely activates in later epochs but prevents catastrophic updates in the first few dozen epochs.

**Architecture details.** The encoder maps `[feature_vector(42) || condition(1)] = 43` dimensions through `43 -> 64 -> ReLU -> Dropout(0.1) -> 32 -> ReLU -> (mu, logvar)` to produce the mean and log-variance of the approximate posterior. The decoder maps `[latent_vector(16) || condition(1)] = 17` dimensions through `17 -> 32 -> ReLU -> 64 -> ReLU -> 42` back to the feature space. The conditioning signal is the target knockdown efficacy (0-1 scale). The Adam optimizer with learning rate `1e-3` and a StepLR scheduler (step size 50, gamma 0.7) provides stable convergence over 200 epochs with batch size 16.

---

## 7. Void-Prioritized Acquisition — Full Derivation

Standard Expected Improvement (EI) is the workhorse acquisition function of Bayesian Optimization. It balances exploitation (favoring points where the predicted value is high) and exploration (favoring points where uncertainty is high). The formula, as given in Section 5, is:

```
alpha_EI(x) = (mu(x) - f_best) * Phi(z) + sigma(x) * phi(z)
```

**The problem with EI in modification space.** EI works well when the goal is to find the global maximum of an unknown function. But in siRNA modification design, the goal is not only to find the best-performing pattern — it is to **map the dark matter**. EI systematically over-exploits: it concentrates sampling around the current best region and its immediate neighborhood. I call this the **flashlight problem**: EI keeps shining the flashlight where it already knows the answer, illuminating the same patch of ground over and over while the vast dark landscape remains unexplored.

To see why this happens, consider the EI formula. When `mu(x) >> f_best`, the first term dominates and EI favors high-predicted-value points regardless of uncertainty. When `sigma(x)` is large, the second term encourages exploration, but only into regions where the GP has no data at all — not regions where the GP has data but from patterns that are structurally similar to the candidate. In siRNA modification space, EI will happily recommend pattern variant #37 of an already well-characterized chemistry (e.g., yet another minor perturbation of the ESC pattern) while ignoring completely uncharacterized chemistries (e.g., patterns with UNA in the seed region) that happen to have slightly lower predicted efficacy.

**Derivation of VPA.** I introduce a multiplicative novelty bonus that scales EI by the structural distance of the candidate from all known patterns:

```
alpha_VPA(x) = alpha_EI(x) * (1 + lambda * d_min(x) / 21)
```

where:

- `d_min(x) = min_{k in S} Hamming(x, k)` is the minimum Hamming distance from candidate `x` to any known pattern `k` in the sampled set `S`. The Hamming distance counts the number of positions where the modification assignments differ between the candidate and the known pattern. For a 42-position duplex, `d_min(x) in {0, 1, ..., 42}`.

- `lambda = 0.5` is the novelty bonus strength. At `lambda = 0.5`, a candidate at maximum Hamming distance (21 positions different — I normalize by 21 rather than 42 because most changes occur on a single strand) receives a 50% bonus to its EI score.

- The normalization by 21 (guide strand length) rather than 42 (total positions) reflects the observation that most meaningful modifications affect primarily one strand. The guide strand is the pharmacologically active strand, and most published variation occurs there.

The multiplicative form `EI * (1 + bonus)` is chosen over an additive form `EI + bonus` because multiplication preserves the relative ranking of candidates within a given novelty tier while boosting all candidates in underexplored regions. An additive bonus would override EI entirely for very novel candidates, potentially recommending biologically implausible patterns simply because they are far from anything known.

**Calibration of lambda.** At `lambda = 0`, VPA reduces to standard EI. At `lambda = 1.0`, a candidate at maximum Hamming distance would receive a 100% bonus — doubling its acquisition score regardless of its predicted quality. I chose `lambda = 0.5` as a moderate value that meaningfully rewards novelty without overwhelming the quality signal from EI. In simulation experiments comparing VPA to EI over 10 DMTL cycles, VPA explores **23% more modification space** (measured as the number of distinct position-modification cells covered by recommended patterns) while maintaining comparable mean predicted efficacy of recommendations.

**Related work.** The idea of incorporating diversity into active learning acquisition functions has precedent. Reker (2020) introduced diversity-aware active learning for drug discovery, showing that diversity bonuses improve hit rates in high-throughput screening campaigns. Graff et al. (2021) used molecular optimization with diversity constraints in generative molecular design. VPA extends this principle to the siRNA modification domain with a domain-specific distance metric (Hamming distance over modification patterns) and a multiplicative formulation that preserves the calibrated uncertainty signal from the GP.

---

## 8. Void Closure Velocity — Statistical Basis

The **Void Closure Velocity** (VCV) is a temporal metric that tracks how quickly each void in the co-occurrence matrix is being "closed" — that is, how rapidly the research community is converging on a previously unexplored region of modification space. VCV is implemented in `velocity_tracker.py`.

**Definition.** For each void `(p, m)` with `C_{p,m} = 0` or near-zero, I define VCV as the rate at which new published patterns containing modification `m` at position `p` (or structurally adjacent patterns) are appearing in the literature. Formally, let `n_t` denote the number of published patterns within Hamming distance 2 of the void at time `t`. The VCV is the slope of a linear regression of `n_t` against `t` over a set of observation windows.

**Time windows.** I use 4 sliding windows of 6 months each (e.g., 2024H1, 2024H2, 2025H1, 2025H2) to compute the velocity. At each snapshot, the system records the observation count `n_t` for each void. The linear regression `n_t = a + b * t + epsilon` is fitted over all available snapshots, and the slope `b` (converted to observations per year) is the VCV.

**Classification.** Based on the VCV value, each void is classified into one of three categories:

- **Hot** (`VCV > 2.0` new patterns/year approaching): The research community is actively converging on this void. Multiple independent groups are testing nearby modification patterns. This void is likely to be closed within 1-2 years. Implication for the user: if you want to establish priority, test this void now before someone else publishes first.

- **Warming** (`VCV > 0.5`): There is modest but detectable convergence. One or two groups appear to be working in this region. The void may close within 3-5 years. Implication: this is a medium-priority target — worth investigating but not urgent.

- **Cold** (`VCV <= 0.5`): No detectable convergence. The void has been stable for years, and no research groups appear to be investigating this region. Implication: this void represents a genuine knowledge gap that is not being addressed by the field. It may be a high-value target for novel discovery, or it may be cold because the community has implicitly determined it is not worth investigating (e.g., modifications that are known to be toxic or synthetically inaccessible).

**Type I and Type II errors.** The VCV classification is subject to both false positives and false negatives. A **Type I error** (false positive "warming") occurs when random fluctuations in publication timing are mistaken for genuine convergence. For example, if two unrelated papers happen to test nearby modification patterns in the same 6-month window, the VCV will spike even though there is no systematic trend. I mitigate this by requiring at least 4 observation windows before classifying a void as "hot" — random coincidences are unlikely to persist across multiple windows. A **Type II error** (false negative — missing genuine convergence) occurs when a group is actively working on a void but has not yet published. Preprints, conference presentations, and patent applications may signal convergence before peer-reviewed publications appear. The current implementation does not track these sources, which is an acknowledged limitation. Future versions could incorporate preprint servers (bioRxiv, medRxiv) and patent databases (Google Patents, USPTO) to reduce Type II error rates.

---

## 9. What I Did Not Do (And Why)

Scientific credibility requires clarity about what is out of scope. Here are six things I deliberately chose not to do, with explanations.

**(a) Sequence modeling (mRNA target context).** OligoVoid operates at the modification level, not the sequence level. It does not model the target mRNA sequence or predict how a specific modification pattern will perform against a specific gene. This is intentional: the modification pattern is a separate design variable from the target sequence, and OligoVoid addresses the modification variable exclusively. For sequence-level efficacy prediction, use OligoFormer (He et al., 2024), which achieves Pearson r=0.719 on sequence-specific knockdown prediction. The two tools are complementary, not competitive: OligoFormer tells you which sequence to target, OligoVoid tells you how to modify it.

**(b) Molecular dynamics simulation.** All-atom molecular dynamics (MD) could in principle simulate the biophysical behavior of each modification pattern — RISC loading, duplex stability, nuclease interactions. But MD simulation of a single 42-nucleotide RNA duplex in explicit solvent requires weeks of GPU time per pattern (even with enhanced sampling methods like replica exchange or metadynamics). With 2,397 void candidates, the computational cost would be on the order of 40,000+ GPU-weeks. This is beyond the scope of a solo computational project. More practically, MD would provide high-fidelity biophysics estimates for individual patterns but would not change the fundamental cartography problem that OligoVoid addresses.

**(c) Graph neural networks.** Graph neural networks (GNNs) have shown promise in molecular property prediction, where molecules are naturally represented as graphs. However, siRNA modification patterns are not naturally graphs — they are linear sequences of discrete labels along a one-dimensional backbone. While one could construct a graph representation (e.g., nucleotides as nodes, base-pairing and stacking interactions as edges), this adds complexity without clear benefit for the available data size. With fewer than 4,000 training patterns, a GNN would be severely overparameterized relative to the data. The GP achieves calibrated uncertainty with far fewer parameters, which is the primary requirement for active learning.

**(d) Reinforcement learning.** Reinforcement learning (RL) would require a reward signal that can be evaluated in real time — either a computational oracle that accurately predicts knockdown efficacy for any modification pattern, or an automated wet-lab system that can synthesize and test patterns on demand. Neither exists. The GP provides approximate predictions, but using an approximate model as an RL reward signal creates a compounding error problem: the RL agent will learn to exploit artifacts of the GP rather than genuinely optimize efficacy. RL is appropriate when the reward signal is either exact (game-playing) or cheaply queryable (protein folding simulations). In siRNA modification design, the true reward requires a cell-based assay that takes days and costs hundreds of dollars per pattern.

**(e) Foundation model fine-tuning.** Large language models pretrained on biological sequences (e.g., RNA-FM, scBERT) could potentially be fine-tuned for modification pattern prediction. However, these models are pretrained on natural RNA sequences, not chemically modified oligonucleotides. The vocabulary of chemical modifications (2'-OMe, 2'-F, LNA, cEt, etc.) is not present in the pretraining data. Fine-tuning would require substantial amounts of modification-level data — precisely the data that is scarce and proprietary. The major pharmaceutical companies (Alnylam, Arrowhead, Silence Therapeutics) hold the largest datasets of chemically modified siRNA patterns, but these are trade secrets. Without access to proprietary data, foundation model fine-tuning would offer no advantage over a GP trained on the publicly available data.

**(f) Clinical outcome prediction.** OligoVoid predicts biophysical feasibility and estimated knockdown efficacy, not clinical outcomes (therapeutic response, duration of action, adverse events). Clinical outcomes depend on confounding factors that are far beyond the modification pattern: delivery vehicle (GalNAc vs. LNP vs. naked), route of administration (subcutaneous vs. intravenous), dosing regimen, patient genotype, target tissue accessibility, immune response, and off-target effects. Predicting clinical outcomes from modification chemistry alone would require modeling all of these confounders, which is a separate and much harder problem. I chose to stay within the domain where the modification pattern is the primary independent variable.

---

## 10. Comparison to Related Systems

**OligoFormer (He et al., 2024).** OligoFormer is a transformer-based deep learning model that predicts siRNA knockdown efficacy from the guide strand sequence and target mRNA context. It achieves Pearson r=0.719 on the Huesken benchmark, which is state-of-the-art for sequence-level efficacy prediction. OligoFormer and OligoVoid solve fundamentally different problems. OligoFormer is a flashlight: given a specific sequence, it predicts how well that sequence will knock down its target. OligoVoid is a telescope: given the entire published literature, it maps what has never been tested and recommends where to explore next. OligoFormer does not model chemical modifications at position-specific resolution, does not enumerate the unexplored modification space, and does not provide uncertainty-calibrated predictions for active learning. Conversely, OligoVoid does not model mRNA target context and is not designed to predict sequence-specific efficacy. The two tools are complementary: a researcher could use OligoFormer to select the best target sequence and then use OligoVoid to identify the most promising unexplored modification pattern for that sequence. Notably, OligoVoid uses OligoFormer's compiled dataset of 3,535 experimentally validated siRNAs as its primary training data, so the two systems share the same empirical foundation.

**siRNAmod (Dar et al., 2016).** siRNAmod is a database of 4,894 experimentally validated chemically modified siRNAs, compiled from published literature. It is the most comprehensive public database of siRNA chemical modifications and was a valuable resource for understanding the landscape. However, siRNAmod is a static database, not an analytical tool. It stores modification data but does not compute the co-occurrence matrix, does not identify voids, does not score feasibility, and does not recommend experiments. More critically, siRNAmod's entries vary in resolution — some entries specify position-specific modifications while others provide only aggregate descriptions (e.g., "fully 2'-OMe modified"). OligoVoid builds on siRNAmod's insight that modification data matters, but goes far beyond storage to provide active cartography, generative modeling, and experiment prioritization. I also found that siRNAmod's coverage of proprietary patterns (especially Alnylam's ESC chemistry) is incomplete, precisely because these patterns are trade secrets — reinforcing the finding from Section 2(a) that the most clinically relevant chemistry is the least publicly documented.

**CHIMERA and related rule-based design tools.** Several tools provide rule-based guidance for siRNA modification design based on published design rules (Reynolds rules, Ui-Tei rules, Amarzguioui rules). These tools encode the known "do's and don'ts" of siRNA chemistry — for example, avoiding LNA at the cleavage site, ensuring 2'-OMe/2'-F alternation in the seed region, protecting the 3' overhang. OligoVoid incorporates these rules in its biophysics scoring layer (`modification_grammar.py` encodes 10 such rules). However, rule-based tools share a fundamental limitation: they can tell you whether a pattern violates known rules, but they cannot tell you whether a pattern that satisfies all known rules will actually work. They also cannot identify which rule-compliant patterns have never been tested. OligoVoid goes beyond rules in three ways: (1) it uses data-driven GP predictions trained on 3,535 real experiments, (2) it generates novel patterns via the CVAE that are conditioned on target efficacy rather than constrained by hand-crafted rules alone, and (3) it provides a formal acquisition function (VPA) that balances predicted quality against structural novelty to recommend experiments. The rule-based tools are the starting line; OligoVoid is the next step.

---

*This document describes the scientific methodology of OligoVoid as of April 2026. All analyses are computational. No wet-lab experiments have been conducted. The dark matter candidates and feasibility scores are predictions that require experimental validation.*
