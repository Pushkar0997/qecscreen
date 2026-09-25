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

BB "gross" code, `l=12, m=6` (note `l != m`), the **same** `A=x^3+y+y^2, B=y^3+x+x^2`:

| ID | Property | Expected |
|---|---|---|
| G-11 | `n` | `144` |
| G-12 | `k` | `12` |
| G-13 | all check weights | `6` |

At `l=m=6`, three of G-07/G-09/G-10's four properties are structurally guaranteed for any `A`/`B` at all — `n=2lm` is arithmetic, check weight is `wt(A)+wt(B)` by construction, and CSS commutation follows from `x` and `y` always commuting. Only `k` discriminates, and even `k` is weak there: `x` and `y` are interchangeable at `l=m`, so a generator bug that swaps them, or flattens the `(a,b)` index wrong, produces an equivalent code with the same `n`, `k` and weights and passes anyway. G-11..G-13 use `l != m` specifically to break that symmetry, so the same class of bug now shows up as a wrong `n`, `k` or weight instead of passing silently. No `d_upper` entry is recorded for the gross code — distance for either reference code is out of scope for the generator tests (M0-CODES-04).

## 3. Invariant tests

One per invariant in `CONTRACT.md`.

| ID | Invariant | Assertion |
|---|---|---|
| INV-1-T | Surrogate ≠ truth | No returned frame contains a column that is neither `true_*`, `pred_*`, nor in the declared metadata schema. Source grep: no assignment of a `pred_`-derived value into a `true_` column |
| INV-2-T | Grouped splits | For every split produced by `qecscreen.splits`, `set(train.construction_program_id) ∩ set(test.construction_program_id) == ∅`. Source grep: `train_test_split` does not appear in `src/` |
| INV-3-T | Censoring | Every row with `failures < 100` has `censored == True` and `true_ler is None`. Every row with `censored == False` has `failures >= 100` and finite CI bounds |
| INV-4-T | LER formula | Golden values G-01..G-04. Source grep over `src/`, excluding `protocol.py`, for five patterns: `(1 - <anything>) **`; `... ** (1 / ...)`, which catches a base containing its own parentheses; `np.power`/`numpy.power`/`math.pow` with a `1 - ` first argument; `expm1(`; `log1p(`. **The grep is itself tested** against seven known violation spellings and one benign file — `test_inv4_grep_catches_known_violations` |
| INV-5-T | Distance provenance | No row has both `d_exact` and `d_upper` null. Where both present, `d_exact <= d_upper` |
| INV-6-T | Single protocol | `assert_single_protocol()` raises `ValueError` on a frame with two distinct `protocol_hash` values. Every ranking and training entry point calls it |
| INV-7-T | Regenerable | For 20 sampled rows, `regenerate(row)` yields bit-identical `H_X`, `H_Z` |
| INV-8-T | Validity | `H_X @ H_Z.T % 2 == 0` for every generated code. Source grep: `linalg.matrix_rank` does not appear in `src/` |
| INV-9-T | No network | Importing `qecscreen` opens no socket (monkeypatch `socket.socket` to raise, then import) |
| INV-10-T | Publish before polish | Not automatable. Manual item in `spec/smoke.md` |

The four **source-grep tests** matter more than they look. They catch the reasonable-looking mistake at the moment it is written, rather than three weeks later in a results table.

They also have a failure mode of their own: a grep that matches nothing passes whether or not it would ever fire, so a weak pattern is indistinguishable from a clean codebase. The INV-4 grep was exactly that — it required a lowercase `p` in the base variable name, so it missed `(1 - P_L) **`, this file's own notation. **A guard nobody has tested is a guard that does not exist**, so INV-4-T now asserts against known violations in a temp file. Any grep test added here should do the same.

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
| N-10 | At `p=0`, one injected X (Z) error on a data qubit between rounds fires **exactly** the Z (X) checks on that qubit in the next round, and nothing else. A circuit with no working detectors passes N-08; it does not pass this (`test_x_error_on_data_fires_its_z_checks`, `test_z_error_on_data_fires_its_x_checks`) |
| N-09 | Requesting a family that does not exist raises `KeyError` listing available families, rather than returning an empty frame |

N-08 is the one that catches a broken circuit builder, which is otherwise invisible — a wrong circuit still produces plausible-looking LERs. It is `test_p0_zero_detection_events`, and it is necessary but not sufficient: N-10 exists because a circuit whose detectors detect nothing also has zero events at `p=0`. `test_detector_error_model_builds` (Stim refuses non-deterministic detectors) is what caught an interleaved X/Z schedule in mutation testing.

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

### 2026-08-30 — M0-SETUP-01 environment verification (interim, not a milestone verdict)

Recorded here rather than in `AGENT_LOG.md` alone because a criterion is **unmet** and the log is not where unmet criteria go to be found.

| Criterion | Verdict | Evidence |
|---|---|---|
| `pip install -r requirements.txt` succeeds in a clean local venv | PASS | Fresh venvs on 3.11.9 and 3.13.7, wheels only, no compiler |
| `pytest` passes on both pinned interpreters | PASS | 42 passed on 3.13.7 and on 3.11.9 |
| `pip install` succeeds in a fresh Colab cell (`spec/smoke.md §1`) | PASS | `notebooks/runs/2026-08-30-verify-env-colab.ipynb`, cell 4, `pip exit code: 0` |
| No downgrade of Colab's preinstalled stack | PASS | Re-measured 2026-09-14 on a factory-reset runtime against the new `pyarrow>=15` pin (D-019), install log captured: **zero uninstalls**. `pyarrow` 23.0.1 reported "Requirement already satisfied", left untouched. Only four packages installed: `ldpc` 2.4.1, `pymatching` 2.4.0, `sinter` 1.16.0, `stim` 1.16.0. Supersedes the FAIL recorded earlier the same day against the old `pyarrow<19` pin |
| …with **no manual fixes** (`spec/smoke.md §1`) | PASS | Corrected 2026-09-14: re-measured with `requirements.txt` written inline via `%%writefile` and a single `pip install -r requirements.txt`, no manual fix cells, on fresh Colab and Kaggle runtimes. `pyparsing` resolved to 3.3.2 without the `<3.2` pin the 2026-08-30 session applied manually, and `matplotlib` resolved to 3.10.0 without the manual `-U` upgrade; both imported clean. The two manual cells recorded on 2026-08-30 were **not required** — this corrects that session's assumption, it is not a change to the criterion |
| No C toolchain invoked during install (`spec/smoke.md §1`, D-018) | PASS | `Building wheel for sinter (setup.py)` occurred, but `sinter` 1.16.0 is sdist-only and pure Python — no compiler ran. Criterion restated per D-018 to match what it was always a proxy for; mechanically checked by the CI compiler grep (`cf5542e`), not by wheel availability. Reconfirmed by CI GREEN on `285a27b` against the same `requirements.txt` |
| Same on Kaggle (`spec/smoke.md §1`) | PASS | Fresh, factory-reset Kaggle runtime, 2026-09-14 (`stim` confirmed not preinstalled): `requirements.txt` written inline, single `pip install -r requirements.txt`, no manual fix cells. Resolved: python **3.12.13** (corrects the prior session's claim of 3.13.15 — Kaggle does not run the same interpreter as Colab), pyparsing 3.3.2, matplotlib 3.10.0, sinter 1.16.0, stim 1.16.0, ldpc 2.4.1, pymatching 2.4.0. The `protocol_hash`-relevant set (`sinter`/`stim`/`ldpc`/`pymatching`, INV-6) matches Colab's resolution; the interpreter does not, and INV-6 does not require it to. `sinter`/`stim` need no compiler for the same reason as Colab (D-018) |
| No downgrade of Kaggle's preinstalled stack | PASS | Re-measured 2026-09-14 on a factory-reset runtime against the new `pyarrow>=15` pin (D-019), install log captured: **zero uninstalls**. `pyarrow` 24.0.0 reported "Requirement already satisfied", left untouched. Only four packages installed: `ldpc` 2.4.1, `pymatching` 2.4.0, `sinter` 1.16.0, `stim` 1.16.0. Supersedes the FAIL recorded earlier the same day |
| CI (`.github/workflows/ci.yml`) | PASS | GREEN on `cf1a1f3` — the first run including the new 3.12 matrix leg (D-020) — 3/3 checks passed (3.11 + 3.12 + 3.13) |
| Cross-platform decoder/simulator versions match (INV-6) | PASS | `sinter` 1.16.0, `stim` 1.16.0, `ldpc` 2.4.1, `pymatching` 2.4.0 resolve identically on Colab and Kaggle. This is what makes measurement rows generated on either platform comparable under INV-6 — the decoder/simulator versions that determine measured behaviour agree across platforms |

**Closes?** **Yes.** Every criterion in this table is now PASS, including the no-downgrade rows, re-measured 2026-09-14 on factory-reset Colab and Kaggle runtimes against the new `pyarrow>=15` pin (D-019) with zero uninstalls on either platform.

**Not permanently settled:** the no-downgrade criterion depends on base images this project does not control, and it has already flipped once without any change to this repository — PASS on 2026-08-30, FAIL on 2026-09-14, PASS again the same day only after `pyarrow`'s upper bound was removed. Treat this record as valid as of 2026-09-14, not as a fact that holds indefinitely. Re-run it — with the install log captured, not just post-install versions — before the M1 bulk generation rather than trusting it from this record alone.

**Caveats carried forward:** `numpy` and `pandas` are not identical across the two target platforms — `numpy` 2.1.3 (Colab) vs 2.0.2 (Kaggle); `pandas` 2.2.3 (Colab) vs 2.3.3 (Kaggle). Neither enters `protocol_hash` (INV-6 covers noise model, `p`, rounds rule, decoder name/version/parameters, scheduling and schema version, not these). The interpreter also differs — Colab 3.13.15, Kaggle 3.12.13 — which is why both are pinned targets (D-020) rather than treated as interchangeable.

---

### M0 verdict

*Not yet run.*

The M0 verdict must answer one question explicitly, in a sentence, at the top:

> Does a LightGBM model on cheap structural features beat Φ at Recall@30-of-top-10 on a construction-program-grouped split, by a margin that survives bootstrap resampling?

A **no** here is a valid, publishable, project-closing answer, and recording it honestly is worth more than five months of building on a false premise. See `spec/product.md §7`.
