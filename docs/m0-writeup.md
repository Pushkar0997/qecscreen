# Does a learned model beat Φ = kd²/n at finding the best BB codes? No. The project proceeds anyway.

**Draft for owner review. Not published.**

The pre-registered question was: does a LightGBM model on cheap structural features beat Φ = kd²/n at Recall@30-of-top-10, on a construction-program-grouped split, by a margin that survives bootstrap resampling? **No.** On 242 bivariate bicycle (BB) codes at n ≤ 72, the model's Recall@30-of-top-10 is 0.200 [0.000, 0.600] and Φ's is 0.000 [0.000, 0.000]. The difference, 0.200 [0.000, 0.600], has an interval that includes zero. The kill condition did not fire: it needs Φ's rank correlation to be already high and the model's advantage to vanish under resampling, and neither holds. Φ's Spearman is 0.242 [0.118, 0.354], and the model's lead over it is 0.629 [0.521, 0.750]. The verdict is **PROCEED, with the headline criterion failed.** It is not rounded up to a pass.

## The question and why it matters

Searches for good quantum LDPC codes, including AI-driven ones, have to rank very many candidate codes cheaply and spend real Monte Carlo simulation on only a few. The usual cheap score is Φ = kd²/n, built from the number of logical qubits k, the distance d and the block length n. If a cheap learned score finds the genuinely best codes more reliably than Φ, search loops waste less simulation. This project exists to test that, and M0 was designed to be able to kill it quickly. The criterion is Recall@30-of-top-10: of the 10 codes with the lowest measured logical error rate, how many appear in a method's 30 highest-ranked codes.

## Setup

The population is every admissible BB code with n ≤ 72 and d_upper ≥ 3 (d_upper is an upper bound on the distance d, so d ≤ d_upper), enumerated rather than sampled, from 11 polynomial templates: 244 codes. Two are excluded (D-036). Both are `mixed_3_5` codes with l = 2, where x³ = x makes a monomial of B repeat and cancel over GF(2). The pinned syndrome schedule cannot extract their checks and refuses to build them. Changing the schedule would change the protocol hash for rows already measured, so the dataset is **242 of 244 codes**.

Every code was measured under one protocol: uniform depolarizing noise at p = 0.002, Z-basis memory, r = d_upper rounds, decoded with a pinned BP+OSD decoder (ldpc 2.4.1). The label is the logical error rate per round per logical qubit (INV-4). A code is measured until it records at least 100 logical failures, up to a cap of 40,960 shots; a code that does not reach 100 failures is censored and ranks by its upper bound (D-035). One code was censored (0.4%). The decoding took 76.3 core-hours on free Kaggle CPUs, over three sessions. The model is LightGBM on 28 structural and circuit features, trained on the log10 of the measured rate, and evaluated leave-one-program-out: each of the 11 construction programs is held out once and the metrics are computed on the pooled out-of-fold predictions. M0 has one family, so there is no family holdout. The bootstrap resamples codes (1,000 resamples, 95% percentile intervals, paired over model and Φ).

## Results

| Leave-one-program-out, 242 codes | Model | Φ (from d_upper) | Model − Φ |
|---|---|---|---|
| Recall@30-of-top-10 | 0.200 [0.000, 0.600] | 0.000 [0.000, 0.000] | 0.200 [0.000, 0.600] |
| Recall, censored code excluded | 0.100 | 0.000 | — |
| Spearman with the measured ranking | 0.871 [0.838, 0.894] | 0.242 [0.118, 0.354] | 0.629 [0.521, 0.750] |
| Spearman, censored code excluded | 0.870 | 0.243 | — |
| Label-noise ceiling, Recall@30-of-top-10 | 1.000 [1.000, 1.000] | | |

The label-noise ceiling is the recall of the observed ranking against labels redrawn from their own binomial noise (1,000 draws). It is reported, not used for any decision.

## Why recall did not separate

All ten of the best codes are `pair_2_2` codes with k = 2. Under leave-one-program-out, the single fold that holds out `pair_2_2` produces every one of their predictions, so one fold decides the headline metric, and each bootstrap resample reuses that fold's predictions. That is why the interval spans 0 to 0.6 and why the point estimate moves from 0.200 to 0.100 when the censored code, the second-best by its upper bound, is dropped.

This is not label noise. The ceiling is 1.000: with labels redrawn from their sampling noise, the observed ranking recovers the top 10 every time. It is the model. Φ scores zero because every top-10 code has k = 2 and Φ ≤ 1.64, and for each of them at least 70 codes with higher k, and so higher Φ, rank above it.

## What the Spearman result means

Over the whole population the model's ordering tracks the measured ordering much more closely than Φ's does: 0.871 against 0.242, with a difference whose interval excludes zero. That is a statement about ranking all 242 codes. It is not a statement about finding the best 10, which is the question that was asked, and the two disagree here. The bootstrap holds the out-of-fold predictions fixed, so it measures variation across codes, not variation from refitting the model.

### Exploratory, post hoc: three single-feature scores

This subsection was not pre-registered, it was added after the verdict, and it is not part of the recorded verdict. I computed Spearman against the same truth ranking (D-035 rule, censored codes ranked by upper bound) for three one-feature scores, each oriented so that higher means predicted better. Point values only, no intervals, on the same 242 rows.

- Minus the mean check weight (lower weight predicted better): **0.719**.
- d_upper (higher predicted better): **0.310**.
- k (higher predicted better, the orientation Φ uses): **−0.026**. Reversing the orientation gives +0.026.

For comparison, the model is 0.871 and Φ is 0.242. Two readings are tempting and neither is supported. Mean check weight takes only five distinct values in this population and varies mostly between templates, so its 0.719 may largely reflect which template a code came from. And these numbers say nothing about the top 10, where recall was the pre-registered criterion. They show that single features can have a higher Spearman than Φ over the whole population, not that they find the best codes.

## Size scaling per template

A diagnostic fixed before the run asks whether, within each template, codes with larger d_upper have lower measured rates. Spearman of d_upper against the measured rate, per template: clear (strongly negative) for `pair_2_2` (−0.92), `quad_4_2` (−0.67), `bb288_3_3` (−0.79), `sym_3_3` (−0.79), `rare_2_3` (−1.00, 2 codes) and `rare_3_4` (−1.00, 3 codes); weak for `diag_3_3` (−0.56), `mod_2_3` (−0.52) and `sq_4_2` (−0.20). Two templates fail. `tri_3_3` is +0.32 on 7 codes, and `mixed_3_5` is 0.00, on 3 codes with two distinct d_upper values, and sits above threshold at p = 0.002, as the earlier calibration predicted. Several of these templates have only two distinct d_upper values or a handful of codes, so the readings are coarse. The failing templates stay in every metric above. Some of the ranking target is therefore "which code is more sub-threshold", and for `mixed_3_5` that picture does not apply.

## Limitations

- **Scope.** One code family (BB), one physical error rate (p = 0.002), n ≤ 72, Z-basis memory, one decoder, one syndrome schedule. Nothing here is a claim about other families, larger n or other p.
- **242 of 244.** Two codes are in no metric (D-036).
- **One censored code.** Its inclusion or exclusion moves the model's recall from 0.200 to 0.100.
- **One fold decides the top 10.** See above. With this structure, refit variance is probably the larger source of uncertainty, and it was not measured.
- **The bootstrap holds predictions fixed**, so it understates uncertainty about the model itself.
- **d_upper is an upper bound.** Distances come from a randomised search, so Φ is computed from d_upper (INV-5), and a code's true distance d may be lower than d_upper. The number of rounds r = d_upper inherits the same uncertainty.
- **The label is one noise model.** Rates are measured under uniform depolarizing noise with BP+OSD, and a different decoder or noise model could rank the codes differently. All of the labels are measurements; the model's outputs are predictions and appear only as such (INV-1).
- **Spearman is not the headline.** The pre-registered criterion is recall, and it failed.

## What M1 changes

These are plans, not results. M1 is intended to widen the population beyond n ≤ 72 and beyond BB, which needs its own cost measurement and a population definition that rejects polynomials with coinciding monomials before it is pinned. It is also intended to address the single-fold problem, so that the top of the ranking is not decided by one held-out program, and to measure refit variance. None of this has been run.

## Reproducibility

- Pilot code: `1131f1000fdf0708dc7ba46e63d8859140d2c2bb` (`1131f10`), the commit all 242 rows record. Verdict evidence was recorded at `ba19e507c7022f6edb80d16bf9deb9b5dd3be01d`; the repository is public at `Pushkar0997/qecscreen`.
- Final pilot archive: `evidence/pilot/final-1131f10/m0-pilot.tar`, sha256 `ccef076d29db82a25148f55fafe3f3e6c9cb5d15943817266daf015dbc511aa8`, unmodified.
- Protocol hash: `6230a7a8a31d8b202e5454c49cf7823b77f95d8452a7d27e273ce9a89fcb32fe`. Stim 1.16.0, ldpc 2.4.1, Python 3.13.7 (evaluation), x86_64/sse2.
- Evaluation outputs: `evidence/m0-verdict/2026-10-03-1131f10/m0_results.json` and `m0_results.txt`. The inputs are gitignored: `data/m0_measurements.parquet` (sha256 `5c644c28…`), `data/m0_features.parquet` (`49e28025…`), `data/m0_predictions.parquet` (`ba6f75f4…`).
- To rerun: install the repository at `1131f10`; from the repository root call `assemble_measurements("<path>/m0-pilot.tar", "data")` (`qecscreen.evaluate.pilot`), build the features with `compute_features` and `write_features` (`qecscreen.features.table`), then `run_m0_evaluation("data/m0_measurements.parquet", "data/m0_features.parquet", "evidence/<new-dir>")` (`qecscreen.verdict`). Seeds are pinned: bootstrap 20261001, label-noise ceiling 20261002. The decision record is in `spec/decisions.md` (D-031 to D-036) and the verdict in `spec/evals.md` §7.
