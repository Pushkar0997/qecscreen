# Does a learned model beat Φ = kd²/n at finding the best BB codes? No. The project proceeds anyway.

*Published 2026-10-03 (Milestone 0 closeout, updated for broader readability without altering any recorded number, verdict, or reproducibility record).*

---

## Executive summary (for both non-specialists and QEC researchers)

Modern searches for better quantum error-correcting codes — including AI- and reinforcement-learning-driven search loops — generate thousands of candidate codes. Because running a realistic **circuit-level simulation** of every candidate is slow and expensive, researchers filter candidates first using a cheap algebraic shortcut:

$$\Phi = \frac{k \cdot d^2}{n}$$

Here `n` is the number of physical data qubits, `k` is the number of protected logical qubits, and `d` is the code's distance (roughly, how many simultaneous errors it takes to cause an undetectable failure). Higher `Φ` is commonly treated as a proxy for a better code.

**Milestone 0 (M0)** of `qecscreen` was designed as a fast, honest falsification test. Before investing months in a large multi-family dataset, we asked one pre-registered question:

> **Does a LightGBM model trained on 28 cheap structural and circuit features beat `Φ = kd²/n` at `Recall@30-of-top-10` — catching the 10 genuinely lowest-error codes inside its top 30 picks — on a strict construction-program-grouped split, by a margin that survives bootstrap resampling?**

**The answer is No.**
On 242 bivariate bicycle (BB) codes with at most 72 data qubits (`n ≤ 72`) simulated at physical error rate `p = 0.002`:
- The **LightGBM model** caught **2 of the top 10** codes (`Recall@30-of-top-10 = 0.200`, 95% bootstrap interval `[0.000, 0.600]`).
- The **incumbent proxy `Φ`** caught **0 of the top 10** (`0.000`, `[0.000, 0.000]`).
- Because the bootstrap confidence interval for `Model − Φ` (`0.200 [0.000, 0.600]`) includes zero, the headline test **FAILS**. We do not round an uncertain result up to a pass.

**Yet the project proceeds anyway.**
Our pre-registered **kill condition** was designed to stop the project if `Φ` already ranked codes well *and* the learned model's advantage vanished under resampling. Neither happened:
- Across all 242 codes, **`Φ`'s Spearman rank correlation** with the true measured error rate is only **0.242** `[0.118, 0.354]`.
- **LightGBM's Spearman rank correlation** is **0.871** `[0.838, 0.894]`.
- The model's overall ranking lead over `Φ` is **+0.629** `[0.521, 0.750]`, far away from zero.

**Official M0 verdict (`spec/evals.md §7`):** **PROCEED, with the headline criterion FAILED.** Cheap structural features clearly contain strong circuit-level signal that `Φ` misses, but M0's small single-family population had a structural bottleneck (all top-10 codes came from one single template) that prevented reliable top-10 generalization.

---

## 1. The question and why it matters

### The bottleneck in quantum code discovery

Quantum computers suffer from hardware noise: gates misfire, measurements flip, and idle qubits lose their quantum state. **Quantum error-correcting (QEC) codes** protect fragile quantum information by spreading `k` **logical qubits** across `n` physical data qubits and repeatedly running parity-check measurements (using extra **ancilla qubits**) to detect and fix errors on the fly.

Recently, **quantum LDPC codes** — especially **bivariate bicycle (BB) codes** — have attracted intense interest because they can encode many logical qubits with far lower hardware overhead than traditional surface codes. Automated discovery loops can now propose thousands of new candidate codes in hours.

The catch is **evaluation cost**:
- Computing algebraic parameters like `n`, `k`, and an upper bound on distance `d_upper` takes seconds.
- Measuring a code's actual **circuit-level logical error rate** — building the syndrome-extraction circuit, injecting noise on every gate and idle step, simulating thousands of noisy shots, and running a classical decoder on every shot — takes minutes to hours per code.

To cope with this cost gap, search loops **screen** candidates using `Φ = kd²/n` and only simulate the highest-`Φ` picks. But if `Φ` points search loops toward the wrong codes, huge amounts of compute are wasted — and genuinely strong codes get thrown away before they are ever simulated.

### What M0 was built to test

`qecscreen` tests whether cheap, fast-to-compute features (graph structure of the parity checks, qubit degrees, short cycles, spectral gap, and basic circuit gate counts) can rank codes closer to their **true circuit-level logical error rate** than `Φ`.

M0 was intentionally built to be **falsifiable**:
- **Headline metric (`Recall@30-of-top-10`):** Imagine you have 242 candidate codes and only enough compute to run full simulations on 30 of them. If you pick the 30 codes ranked highest by a screening method, what fraction of the **10 truly lowest-error codes** make it into your 30? (`0.0` = none; `1.0` = all 10.)
- **Secondary metric (`Spearman rank correlation`):** Over the entire set of 242 codes, how closely does a method's ranking from best to worst match the true measured ranking? (`1.0` = exact match; `0.0` = uncorrelated.)

---

## 2. Experimental setup (how the data was measured and scored)

### The code population (242 of 244 codes)

Rather than hand-picking or randomly sampling codes, we exhaustively enumerated every admissible **bivariate bicycle (BB) code** with:
- at most 72 physical data qubits (`n ≤ 72`), and
- distance upper bound `d_upper ≥ 3` (where `d_upper` comes from a randomized, decoder-assisted search, so the true code distance satisfies `true distance ≤ d_upper`),

drawn from **11 polynomial templates** (construction programs). That enumeration produced **244 codes**.

**Why 2 codes were excluded (`D-036`):**
Two codes in the `mixed_3_5` template have cyclic parameter `l = 2`, where cyclic wrap-around makes `x³ = x`. As a result, two monomial terms in polynomial `B` coincide and cancel each other out over binary arithmetic (GF(2)). Although the remaining check matrix still defines a valid code mathematically, our pinned syndrome-extraction schedule expects distinct monomials and deliberately refuses to build a circuit that would extract the wrong checks. Changing the schedule mid-pilot would have invalidated the protocol hash of codes already measured, so those 2 codes were excluded and logged in the dataset's metadata. Every number in M0 therefore covers **242 of 244 codes**.

### The simulation and decoding protocol

Every one of the 242 codes was measured under one exact, hashed protocol (`protocol_hash` `6230a7a8a31d8b202e5454c49cf7823b77f95d8452a7d27e273ce9a89fcb32fe`):

- **Noise model:** Uniform depolarizing circuit noise (`uniform_depolarizing_v1`) at physical error rate **`p = 0.002`** — every idle qubit, two-qubit CX gate, reset, and measurement can fail at rate `p` (initial state preparation and final data readout are noiseless).
- **Memory experiment:** **Z-basis quantum memory**, run for `r = d_upper` rounds of syndrome extraction using a pinned X-then-Z monomial-matching gate schedule (`bb_monomial_matching_xz_phased_v2`).
- **Simulator & decoder:** `Stim 1.16.0` for circuit sampling, decoded with `ldpc 2.4.1` **BP+OSD** (Belief Propagation + Ordered Statistics Decoding; min-sum, 30 iterations, scaling 0.625, OSD-CS order 10).
- **Target label (`true_ler`):** Logical error rate **per round, per logical qubit**, defined by one pinned formula ([INV-4](../CONTRACT.md#inv-4--ler-normalisation-is-pinned-to-exactly-one-formula)):

  $$\text{LER} = 1 - (1 - P_L)^{\frac{1}{r \cdot k}}$$

  where `P_L` is the fraction of shots in which any logical observable failed. Normalizing by `r` and `k` puts codes with different numbers of logical qubits and different round counts on a fair, comparable scale.

### Adaptive shot budget, censoring, and compute cost

Low-error codes need far more simulated shots to observe enough failures for a reliable rate estimate. To avoid wasting compute on weak codes while keeping error bars tight on strong ones:
- Each code is simulated in batches of **256 shots** until it accumulates at least **100 logical failures**, up to a cap of **40,960 shots**.
- **Censoring (`INV-3`, `D-035`):** If a code hits 40,960 shots with fewer than 100 failures, its error rate is too thin to quote as a point estimate. We mark `censored = True`, set `true_ler` to `null`, exclude it from ML training targets, and rank it using its conservative 95% Wilson upper bound (`true_ler_ub`).
- In M0, **only 1 code was censored (0.4%)**: `bb_v1_pair_2_2-4faad046f1a9`, which recorded 93 failures in 40,960 shots (making it the #2 best code by `true_ler_ub`).
- **Compute asymmetry:** Across all 242 codes, the median code needed just **1,024 shots**. By contrast, the **10 best codes required 24,320 to 40,960 shots each**. In total, M0 decoding took **76.3 CPU core-hours** on free Kaggle CPUs across three resumable sessions.

### The baseline model and evaluation split

- **Model:** A default, untuned **LightGBM** gradient-boosted tree regressor (`m0_lightgbm_v1`) trained to predict `log10(true_ler)` from **28 cheap structural and circuit features** (including `n`, `k`, `d_upper`, `Φ`, check weights, qubit degrees, 4- and 6-cycles in the Tanner graph, girth, spectral gap `lambda2`, connected components, CX gate counts, and circuit depth in ticks). Censored rows are excluded from training but still predicted and ranked.
- **Fairness split (leave-one-program-out):** Randomly splitting individual codes into train and test sets is banned (`INV-2`) because codes from the same polynomial template are near-duplicates — a model could memorize template patterns instead of learning physics. Instead, we used **leave-one-program-out** cross-validation across the 11 construction programs: each template is held out completely while the model trains on the other 10, and metrics are computed on the pooled out-of-fold predictions. *(Note: because M0 contains only one code family — BB — there is no cross-family holdout yet.)*
- **Uncertainty intervals:** Paired **bootstrap resampling over codes** (1,000 resamples, 95% percentile intervals, pinned seed `20261001`), comparing the model and `Φ` on the exact same resampled code sets.

---

## 3. Results

| Metric (Leave-one-program-out, 242 codes) | LightGBM Model | `Φ` (from `d_upper`) | Model − `Φ` |
|---|---|---|---|
| **Recall@30-of-top-10** *(headline)* | **0.200** `[0.000, 0.600]` | **0.000** `[0.000, 0.000]` | **0.200** `[0.000, 0.600]` |
| Recall@30-of-top-10, censored code excluded | 0.100 | 0.000 | — |
| **Spearman with the measured ranking** | **0.871** `[0.838, 0.894]` | **0.242** `[0.118, 0.354]` | **0.629** `[0.521, 0.750]` |
| Spearman, censored code excluded | 0.870 | 0.243 | — |
| **Label-noise ceiling** (Recall@30-of-top-10) | 1.000 `[1.000, 1.000]` | — | — |

*What is the label-noise ceiling?* Each code's logical error rate is estimated from a finite number of Monte Carlo shots, so it has some binomial sampling noise. To check whether that noise could shuffle the true top 10, we redrew every code's error rate 1,000 times from its Beta posterior (`Beta(failures + 0.5, shots - failures + 0.5)`, seed `20261002`) and checked how often the observed ranking still recovered each draw's top 10 within its top 30. The result is a flat **1.000 `[1.000, 1.000]`** — meaning the measured top 10 is completely stable. This diagnostic is reported for transparency and does not decide any pass/fail criterion.

---

## 4. Deep dive: why Recall@30 failed while Spearman succeeded

At first glance, the table looks contradictory: how can a model achieve a very strong **0.871** rank correlation over all 242 codes, yet catch only **2 of the top 10** codes? Two distinct mechanisms explain the gap.

### 1. Why the model's Recall@30 was weak and noisy (one fold decided everything)

All **10 of the lowest-error codes** in the M0 dataset belong to **one single template**, `pair_2_2` (which has very low check weight — only 4 data qubits per check — and `k = 2`).

Under leave-one-program-out cross-validation:
- When `pair_2_2` is held out as the test fold, the model trains exclusively on the other 10 templates — which all have higher check weights and much higher error rates.
- That **single fold** then generates the predictions for **all 10 of the true top-10 codes**.
- Consequently, one single out-of-distribution extrapolation decides the entire headline metric, and every bootstrap resample reuses that same fold's predictions.

That structural concentration explains both why the bootstrap interval is huge (`[0.000, 0.600]`) and why dropping the single censored code (the #2 best code overall) cuts the point estimate in half from `0.200` (2/10) to `0.100` (1/10). Because the label-noise ceiling is `1.000`, we know the miss is genuinely the model struggling to extrapolate to an unseen low-weight template — not noisy simulation labels.

### 2. Why `Φ = kd²/n` scored exactly zero on Recall@30

`Φ` puts `k` (number of logical qubits) directly in the numerator. In M0, every single top-10 code has **`k = 2`** and a small proxy value **`Φ ≤ 1.64`**.

Meanwhile, many other BB templates encode `k = 4, 6, 8, or 12` logical qubits — giving them much higher `Φ` — even though their heavier parity checks cause far more gate errors during syndrome extraction. As a result, for *every single one* of the true top-10 codes, **at least 70 codes with both higher `k` and higher `Φ`** rank ahead of it in `Φ`'s list. None of the top 10 ever get anywhere near `Φ`'s top 30, so `Φ`'s Recall@30-of-top-10 is **0.000**.

### 3. What the 0.871 Spearman correlation actually means (and doesn't mean)

Over the entire population of 242 codes, LightGBM's predicted ranking tracks the true measured ranking far more closely than `Φ` (`0.871` vs `0.242`, a lead of `+0.629` whose confidence interval `[0.521, 0.750]` sits well above zero).

Read that honestly:
- **What it proves:** Cheap structural and circuit features carry strong, real predictive signal about circuit-level error rates that `Φ` misses. That justifies continuing to M1.
- **What it does NOT prove:** It does *not* prove that LightGBM reliably spots the very best codes in an unseen template or unseen code family. Ranking the whole field and picking the top 10 winners are two different tasks, and here they disagreed.
- **Bootstrap caveat:** Because our bootstrap resamples codes while holding the out-of-fold predictions fixed, it measures variation across codes — *not* the extra variance from refitting the model.

### 4. Exploratory, post-hoc check: three single-feature scores

> **Disclosure:** This analysis was **not pre-registered**. It was run after the verdict was recorded and is not part of the official M0 verdict.

To understand *what* was driving the global ranking, we computed Spearman correlation against the exact same measured ranking (using the D-035 rule for the censored row) for three individual features on their own, oriented so that **higher = predicted better** (point values only, no intervals, on the same 242 rows):

| Single-feature score (higher = predicted better) | Spearman correlation | Intuition |
|---|---|---|
| **Minus mean check weight (`-check_weight_mean`)** | **0.719** | Fewer qubits per check → shallower circuits and fewer noisy CX gates |
| **Distance upper bound (`d_upper`)** | **0.310** | Higher distance helps, but ignores circuit weight and noise |
| **Logical qubits (`k`)** *(as `Φ` uses it)* | **−0.026** | Essentially no helpful correlation (reversing orientation gives `+0.026`) |
| *For comparison: `Φ = kd²/n`* | *0.242* | *Dragged down by rewarding `k` and ignoring check weight* |
| *For comparison: LightGBM (28 features)* | *0.871* | *Combines check weight, distance, graph, and circuit features* |

**Two tempting conclusions to avoid:**
1. Do not assume check weight is a magic universal score. In M0, `check_weight_mean` takes only **five distinct values** and varies mostly *between* polynomial templates — so its `0.719` Spearman correlation may largely reflect identifying which template a code belongs to.
2. These single-feature correlations say nothing about catching the **top 10**, which was the pre-registered criterion. They simply show why a multi-feature model can crush `Φ` globally while still needing much broader data to generalize to top-tier codes.

---

## 5. Diagnostic: does larger distance actually lower error rates within each template?

In quantum error correction, increasing a code's distance `d` only reduces its logical error rate if the physical error rate `p` is **below the code family's threshold**. If a code sits *above* threshold at `p = 0.002`, making it bigger actually makes it *worse* (or flat), because the extra noisy gates overwhelm the extra error-correcting distance.

Before running M0, we fixed a diagnostic (`D-031`) to check **size scaling inside each of the 11 templates**: the Spearman correlation between `d_upper` and `true_ler` within each template. A **strongly negative** number means the template behaves cleanly below threshold (larger `d_upper` → lower error rate):

- **Clear sub-threshold scaling (6 templates):** `pair_2_2` (**−0.92**), `bb288_3_3` (**−0.79**), `sym_3_3` (**−0.79**), `quad_4_2` (**−0.67**), `rare_2_3` (**−1.00**, 2 codes), and `rare_3_4` (**−1.00**, 3 codes).
- **Weak scaling (3 templates):** `diag_3_3` (**−0.56**), `mod_2_3` (**−0.52**), and `sq_4_2` (**−0.20**).
- **Failing scaling (2 templates):** `tri_3_3` (**+0.32**, 7 codes) and `mixed_3_5` (**0.00**, 3 codes with 2 distinct `d_upper` values), which sits **above threshold** at `p = 0.002` — matching what our earlier calibration predicted.

Several templates have only a handful of codes or two distinct `d_upper` values, so these per-template readings are coarse. Crucially, **we did not drop the failing templates** — they remain in every metric above. That means part of what any screening model learns at `p = 0.002` is simply *"which templates are safely below threshold at this noise level?"*

---

## 6. Limitations and honest caveats

- **Narrow scope:** One code family (BB), one physical error rate (`p = 0.002`), small block lengths (`n ≤ 72`), Z-basis memory only, one decoder (`BP+OSD`), and one syndrome schedule. Do not extrapolate these numbers to other code families, larger `n`, or other `p`.
- **242 of 244 codes:** Two `mixed_3_5` codes were unbuildable under the pinned schedule (`D-036`) and appear in no metric.
- **Sensitivity to the single censored code:** Including or excluding the 1 censored code (`0.4%`) moves the model's Recall@30-of-top-10 from `0.200` to `0.100`.
- **Single-fold concentration:** Because all 10 top codes come from `pair_2_2`, one held-out fold decides the headline metric. Under this structure, refit variance is likely larger than code-resampling variance, and refit variance was not measured.
- **Fixed-prediction bootstrap:** The bootstrap resamples codes without refitting LightGBM, so it understates uncertainty in the learned model itself.
- **`d_upper` is an upper bound (`INV-5`):** Distances come from randomized decoder-assisted search, so a code's true distance may be smaller than `d_upper`. Both `phi_from_d_upper` and the round count `r = d_upper` inherit that uncertainty.
- **Protocol dependence (`INV-1`, `INV-6`):** Labels come from uniform depolarizing noise decoded with BP+OSD. A different hardware noise model (e.g., biased noise or erasure) or decoder could rank codes differently. All dataset labels are real measurements; model outputs are always kept separate as predictions.
- **Spearman is not the headline:** The pre-registered headline criterion was Recall@30-of-top-10, and it failed.

---

## 7. What M1 is planned to change

> These are **plans, not results**. M1 has not started yet.

M1 (**Dataset v0.1**) is designed to directly fix M0's structural bottlenecks:
1. **Multiple code families and larger codes:** Expand beyond small `n ≤ 72` BB codes to include Generalized Bicycle (GB) and Hypergraph Product (HGP) codes across multiple qubit budgets and multiple physical error rates `p` (after measuring real per-shot decode cost for each new regime).
2. **Cleaner enumeration before pinning:** Reject polynomials with colliding/cancelling monomials during enumeration, before a population hash is frozen.
3. **Eliminate the single-fold bottleneck:** Build a diverse multi-family population so the top of the ranking is never controlled by one template, enable true **held-out code family** evaluation (M2), and measure refit variance explicitly.

---

## 8. Reproducibility record

Every number in this write-up can be audited or regenerated from the committed evidence:

- **Pilot source commit:** `1131f1000fdf0708dc7ba46e63d8859140d2c2bb` (`1131f10`) — recorded in every one of the 242 measurement rows.
- **Evaluation source commit:** Ran from a local editable install of working tree `345c174ff059d9785735c4b1ea1dd67af8910fd1` (`345c174`), whose source equals CI-verified commit `17263bf013c2e3fd87903f483053077c6e58a112` (`17263bf`); that is why `commit_sha` is `null` in `m0_results.json`. Verdict evidence was committed at `ba19e507c7022f6edb80d16bf9deb9b5dd3be01d`. Repository: `https://github.com/Pushkar0997/qecscreen`.
- **Final pilot archive:** `evidence/pilot/final-1131f10/m0-pilot.tar`, SHA-256 `ccef076d29db82a25148f55fafe3f3e6c9cb5d15943817266daf015dbc511aa8` (unmodified).
- **Protocol & environment:** `protocol_hash` `6230a7a8a31d8b202e5454c49cf7823b77f95d8452a7d27e273ce9a89fcb32fe`; `Stim 1.16.0`, `ldpc 2.4.1`, Python `3.13.7` (evaluation), `x86_64/sse2`.
- **Evaluation outputs & committed dataset snapshot:** `evidence/m0-verdict/2026-10-03-1131f10/m0_results.json` and `m0_results.txt`, alongside the byte-for-byte snapshot (`D-037`) in `evidence/m0-verdict/2026-10-03-1131f10/data/`:
  - `m0_measurements.parquet` — SHA-256 `5c644c028ff81803e904bda86a2714f4f8169aa8de717462a735f603d650d696`
  - `m0_features.parquet` — SHA-256 `49e28025ca8bbddf376613ed72382536ef569e94ebef1dfc154789c63b0632a6`
  - `m0_predictions.parquet` — SHA-256 `ba6f75f41c3fbd0e858c7bb6dbe7f3e6facbabc7d1594a408f5564a5f3e5e5ea`
- **To rerun from scratch:** Install the repository at `17263bf` or later (not `1131f10`, where assembly refuses the two D-036 codes and the label-noise ceiling does not exist). From the repository root, call `assemble_measurements("<path>/m0-pilot.tar", "data")` (`qecscreen.evaluate.pilot`), build features with `compute_features` and `write_features` (`qecscreen.features.table`), and call `run_m0_evaluation("data/m0_measurements.parquet", "data/m0_features.parquet", "evidence/<new-dir>")` (`qecscreen.verdict`; import `qecscreen.verdict` before `pandas`/`pyarrow` on Windows to avoid a LightGBM/PyArrow DLL clash). Seeds are pinned (`20261001` for bootstrap, `20261002` for the label-noise ceiling). Full decision record: `spec/decisions.md` (D-031 to D-037); formal verdict: `spec/evals.md §7`.
