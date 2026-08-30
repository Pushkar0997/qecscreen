# evals.md — Evaluation

## 1. How to run

```
pytest -q
```

Must pass before any commit is considered done and before any dataset release. Non-zero exit on failure.

Tolerances: golden LER and Wilson values are asserted with `math.isclose(rel_tol=1e-12)`. They are deterministic arithmetic, not simulation, so there is no reason to be loose.

Simulation-based assertions use explicit seeds and are asserted against ranges, never against exact stochastic outcomes.

## 2. Golden values

Literal. Copied from `CONTRACT.md`. If these two files ever disagree, `CONTRACT.md` wins and this file is stale.

`logical_error_rate(P_L, r, k)`:

| ID | Input | Expected |
|---|---|---|
| G-01 | `(0.5, 12, 12)` | `0.004801955655646228` |
| G-02 | `(0.01, 6, 6)` | `0.0002791370299384255` |
| G-03 | `(0.25, 4, 2)` | `0.0353213700396906` |
| G-04 | `(0.0, 12, 12)` | `0.0` |

`wilson_interval(failures, shots)`:

| ID | Input | Expected |
|---|---|---|
| G-05 | `(100, 10000)` | `(0.008229336148148417, 0.012146982255114645)` |
| G-06 | `(1, 1000)` | `(0.00017654637062607809, 0.0056425585979579355)` |

BB reference code, `l=6, m=6, A=x^3+y+y^2, B=y^3+x+x^2`:

| ID | Property | Expected |
|---|---|---|
| G-07 | `n` | `72` |
| G-08 | `k` | `12` |
| G-09 | `d_upper` | `6` |
| G-10 | all check weights | `6` |

G-07 through G-10 are the single most important tests in the project. If the generator does not reproduce the published reference code exactly, every label downstream is measuring something other than what it claims.

## 3. Invariant tests

One per invariant in `CONTRACT.md`.

| ID | Invariant | Assertion |
|---|---|---|
| INV-1-T | Surrogate ≠ truth | No returned frame contains a column that is neither `true_*`, `pred_*`, nor in the declared metadata schema. Source grep: no assignment of a `pred_`-derived value into a `true_` column |
| INV-2-T | Grouped splits | For every split produced by `qecscreen.splits`, `set(train.construction_program_id) ∩ set(test.construction_program_id) == ∅`. Source grep: `train_test_split` does not appear in `src/` |
| INV-3-T | Censoring | Every row with `failures < 100` has `censored == True` and `true_ler is None`. Every row with `censored == False` has `failures >= 100` and finite CI bounds |
| INV-4-T | LER formula | Golden values G-01..G-04. Source grep: `(1 - P_L) **` or equivalent appears only in `protocol.py` |
| INV-5-T | Distance provenance | No row has both `d_exact` and `d_upper` null. Where both present, `d_exact <= d_upper` |
| INV-6-T | Single protocol | `assert_single_protocol()` raises `ValueError` on a frame with two distinct `protocol_hash` values. Every ranking and training entry point calls it |
| INV-7-T | Regenerable | For 20 sampled rows, `regenerate(row)` yields bit-identical `H_X`, `H_Z` |
| INV-8-T | Validity | `H_X @ H_Z.T % 2 == 0` for every generated code. Source grep: `linalg.matrix_rank` does not appear in `src/` |
| INV-9-T | No network | Importing `qecscreen` opens no socket (monkeypatch `socket.socket` to raise, then import) |
| INV-10-T | Publish before polish | Not automatable. Manual item in `spec/smoke.md` |

The four **source-grep tests** matter more than they look. They catch the reasonable-looking mistake at the moment it is written, rather than three weeks later in a results table.

## 4. Negative tests

**More important than the positive tests.** These catch the regressions positive tests miss.

| ID | Assertion |
|---|---|
| N-01 | A code with `H_X @ H_Z.T % 2 != 0` is **rejected** by `validate()` with `ValueError`, not warned about |
| N-02 | Ranking a frame with two `protocol_hash` values **raises**, does not silently concatenate |
| N-03 | A row with 3 failures in 200,000 shots produces `censored=True` and `true_ler is None`, not `1.5e-5` |
| N-04 | Calling `grouped_kfold` on a frame missing `construction_program_id` **raises**, does not fall back to a random split |
| N-05 | `logical_error_rate(P_L=1.0, r, k)` raises rather than returning 1.0 — a code that fails every shot has an undefined per-round rate and silently returning 1.0 hides a broken circuit |
| N-06 | `gf2_rank` on a matrix with real-rank 3 and GF(2)-rank 2 returns 2 |
| N-07 | A feature function taking >1s on a 200-qubit code **fails the test**, because the entire pitch is that screening is cheap |
| N-08 | At `p=0`, the memory circuit produces **zero** detection events over 1,000 shots. Any non-zero count means the circuit is malformed |
| N-09 | Requesting a family that does not exist raises `KeyError` listing available families, rather than returning an empty frame |

N-08 is the one that catches a broken circuit builder, which is otherwise invisible — a wrong circuit still produces plausible-looking LERs.

## 5. Telemetry

`decode_seconds` is recorded per row. No other telemetry exists; there is no analytics, no tracking, and no network call anywhere in the project (INV-9).

## 6. Pre-release gate

- [ ] `pytest -q` passes, zero failures, zero new warnings
- [ ] All invariant tests in §3 pass
- [ ] All negative tests in §4 pass
- [ ] `spec/smoke.md` passes in full
- [ ] Dataset card censoring rate matches the actual frame
- [ ] No `TODO`, `FIXME` or placeholder value in any released Parquet or spec file

## 7. Recorded verdicts

Written **after** a milestone, not before. Criteria alone are aspiration; a verdict with evidence per line is what catches a milestone being 60% done and called finished.

**PASS only where a test or a recorded result backs it.** Not inspection, not "it obviously works."

**Never round up a PARTIAL.** This is the strongest temptation in the system — one criterion short, everything else green, the milestone obviously basically done. Record the PARTIAL. On this project specifically, the criterion most likely to be rounded up is the censoring rate, because a high one is annoying and means re-running the pilot.

### Template

```
### <YYYY-MM-DD> — M<n> verdict

| Criterion | Verdict | Evidence |
|---|---|---|
| <from the exit criteria> | PASS | <test name / recorded run> |
| <...> | PARTIAL | <exactly what is missing> |

**Closes?** <yes — or no, and precisely what would close it>
**Caveats carried forward:** <...>
```

### M0 verdict

*Not yet run.*

The M0 verdict must answer one question explicitly, in a sentence, at the top:

> Does a LightGBM model on cheap structural features beat Φ at Recall@30-of-top-10 on a construction-program-grouped split, by a margin that survives bootstrap resampling?

A **no** here is a valid, publishable, project-closing answer, and recording it honestly is worth more than five months of building on a false premise. See `spec/product.md §7`.
