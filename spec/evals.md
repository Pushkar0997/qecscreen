# evals.md — Evaluation

## 1. How to run

```
pytest -q                          # default: skips tests marked `slow`
pytest -q -m "slow or not slow"    # the full suite, what CI runs on every leg
```

The default run skips tests marked `slow` (the large admitted-sample draws in `test_sample.py`) so the edit-test loop stays short. **The full suite** must pass before any commit is considered done and before any dataset release; CI runs it on every interpreter and never skips. Non-zero exit on failure.

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

The interval is clamped to `[0, 1]` (D-026): `wilson_interval(0, n)[0] >= 0` for every `n`, and exactly `0.0` at `n = 21`, where the unclamped formula gives -1.4e-17 (`test_d026_wilson_clamped_at_zero_failures`, `test_d026_wilson_residue_case_is_exactly_zero`). G-05 and G-06 are interior and not affected.

`sampling_seed(code_id, protocol_hash)` (D-027):

| ID | Input | Expected |
|---|---|---|
| G-14 | `("bb_v1_ref-0123456789ab", "a" * 64)` | `6435667380748351026` |

Exact integer equality (`test_d027_sampling_seed_golden`), plus an independent re-derivation from the hex digest and tests that a different `code_id` or `protocol_hash` gives a different seed.

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
| N-03 | A row with 3 failures in `MAX_SHOTS` shots produces `censored=True` and `true_ler is None`, not 3/`MAX_SHOTS` or its per-round form (`test_n03_three_failures_at_max_shots_is_censored_not_a_rate`; 200,000 shots before D-031 cut `MAX_SHOTS` to 10,240, and 40,960 since D-034) |
| N-04 | Calling `grouped_kfold` on a frame missing `construction_program_id` **raises**, does not fall back to a random split |
| N-05 | `logical_error_rate(P_L=1.0, r, k)` raises rather than returning 1.0 — a code that fails every shot has an undefined per-round rate and silently returning 1.0 hides a broken circuit |
| N-06 | `gf2_rank` on a matrix with real-rank 3 and GF(2)-rank 2 returns 2 |
| N-07 | A feature function taking >1s on a 200-qubit code **fails the test**, because the entire pitch is that screening is cheap |
| N-08 | At `p=0`, the memory circuit produces **zero** detection events over 1,000 shots. Any non-zero count means the circuit is malformed |
| N-10 | At `p=0`, one injected X (Z) error on a data qubit between rounds fires **exactly** the Z (X) checks on that qubit in the next round, and nothing else. A circuit with no working detectors passes N-08; it does not pass this (`test_x_error_on_data_fires_its_z_checks`, `test_z_error_on_data_fires_its_x_checks`). And for **every** data qubit, the set of observables an injected X flips equals **exactly** the set of Z logicals with support on that qubit (`test_x_error_flips_exactly_the_observables_containing_it`). The exact-set sweep is what catches a deterministic but wrong observable, e.g. a logical multiplied by a stabiliser or by another logical: it still passes N-08 and the DEM build |
| N-11 | The same code, `p` and seed through `sample_and_decode` give **identical** shots (sha256 of every sampled byte) and failures, and a different seed gives different shots (`test_same_code_p_and_seed_give_identical_shots_and_failures`, `test_a_different_seed_gives_different_shots`). A sampler seeded from OS entropy, as sinter's are, fails this (D-026). Holds on one machine and stim version only; stim does not promise it across versions or SIMD widths |
| N-12 | A notebook code cell that defines a function, class or lambda fails `test_no_code_cell_defines_a_function_or_class` (architecture §2 notebook rules). Checked against the pre-D-028 `verify_env_colab.ipynb`, which it rejects at its two `def`s. `notebooks/runs/` evidence is exempt |
| N-13 | An install URL carrying a token never leaks into provenance: with a fake distribution whose `direct_url.json` URL holds a token, and the token also in the environment, `resolved_commit()` returns the bare commit and nothing in `provenance.record()` contains it (`test_every_provenance_value_is_free_of_the_credential`); a token in `commit_id` raises without echoing it. No notebook contains a token-shaped string (`test_no_notebook_contains_a_github_token`). D-028. Cell 1 of the template and `calibrate.ipynb`, executed against fake secret stores with pip recorded: no secret (neither platform, Kaggle or Colab) installs from the plain URL without raising; a secret installs from the token URL and is masked in the printed output (`test_install_cell_*`). D-030 |
| N-14 | Decoder-calibration output never becomes a dataset row, and its decoders are compared on shared shots (D-029). `reject_calibration` refuses the calibration directory, each of its files, and each record, summary or frame carrying `"calibration": true`, and passes a real label (`test_row_guard_rejects_calibration_output`, `test_row_guard_passes_non_calibration_input`); `run_calibration` refuses an out_dir under a directory named `data`. Every decoder's digest of the syndromes it was given equals the digest of an independent re-sample from the cell's `sampling_seed` (`test_every_decoder_decoded_exactly_the_seeded_shots`); a restart re-runs only missing cells. A fake decoder that sleeps forever on shot 150 is killed, its cell recorded as `killed` at batch 1, shot 50, with the batch-0 partial kept, and a restart does not retry it (`test_a_hung_decoder_is_killed_recorded_and_never_retried`). 4 of 4 mutants caught: no marker on a cell file, no resume check, LSD fed a second seeded stream, no `data/` guard |
| N-15 | A run killed mid-code resumes to exactly the uninterrupted run (M0-EVAL-04). Killed at batch b (first, second, middle, last), it resumes with identical shots, failures, OSD invocations and sample digest. The sha256 of every syndrome batch the decoder finished, across the killed and resumed runs, equals the uninterrupted run's, so no batch is skipped or decoded twice (`test_a_run_killed_mid_code_resumes_to_the_uninterrupted_result`). A code with a stored result is never re-run: no decode, no use of the circuit, no file rewritten (`test_a_completed_code_is_never_re_run`). Re-drawn shots that differ from a shard's digest, a gap in the shards, or a checkpoint from another seed, batch size or `max_shots` raise `CheckpointMismatchError` rather than splice two streams. 5 of 5 mutants caught: no re-draw, no digest check, completed code re-run, shards flushed only at the end, counts not restored. D-032: every shard records the `commit_sha`, `stim_version` and `cpu_class` of the process that wrote it; a resume by a process that differs in any of them raises `ProvenanceMismatchError` before anything is drawn (`test_a_resume_by_another_provenance_is_refused`), and a digest mismatch raises `SampleDigestMismatchError` |
| N-16 | A measurement row is built only from a finished checkpoint, with provenance from its shards (M0-RUN-01, `tests/test_rows.py`). `build_row` refuses: calibration input (a marked record, a marked JSON or Parquet file in the checkpoint directory, a marked row); a missing, empty or placeholder `commit_sha` (`None`, `""`, `unset`, 40 zeros, short or uppercase hex); shards that disagree on `commit_sha`, `stim_version` or `cpu_class`; an unfinished code; a checkpoint whose seed is not `sampling_seed(code_id, protocol_hash)` under the installed decoder version; a code record whose `n`/`k`/`d_upper` disagree with its parameters. With the building process reporting other provenance, the row still carries the shards'. Columns are exactly `spec/architecture.md §3`'s table, parsed from the file; none is `pred_*` (INV-1). INV-3 at 99 and 100 failures; LERs float64. INV-7: `codes.ids.regenerate(row)` reproduces `H_X`, `H_Z`, and refuses a `params_json` edited after its `code_id`. The committed calibration's `code_id`s equal `codes.ids`'s. 5 of 5 mutants caught: provenance from the building process, no mixed-shard check, no placeholder check, checkpoint directory not passed to `reject_calibration`, no provenance check on resume |
| N-17 | The M0 pilot survives being split across sessions (M0-RUN-01, D-033, `tests/test_pilot.py`, spawned workers on three [[12]] codes, 64-shot batches, 512-shot cap). A three-session chain through `PREVIOUS` (session 1 ends mid-code: two workers one batch each, the third code not started; session 2 finishes; session 3 starts nothing) gives rows equal to one uninterrupted run per code, `decode_seconds` and `created_at` excepted, and `assemble_measurements` writes exactly those rows to `data/m0_measurements.parquet` and will not overwrite it (`test_a_three_session_chain_equals_one_uninterrupted_run`). A worker terminated between batches resumes to the uninterrupted row (`test_a_terminated_worker_resumes_correctly`). Refused at session start: a manifest mismatch in ldpc version, commit or stim version, and another population (the manifest and the session's summaries unchanged); no resolved commit; `PREVIOUS` holding zero or two pilot directories; a previous output lacking a file its last session's inventory recorded; a copy that differs from its source; an enumeration that no longer gives the pinned population. A partial code written on another `cpu_class` is moved to `stale/<code_id>-x86_64_sse2-<utc>/` with its shards byte-identical, and restarted from batch 0 to the same counts; a tampered shard digest is moved aside as `digest` and restarted. A worker that dies is retried once, in the next session, then failed and not started again; assembly then refuses the unfinished code. Completed codes' files are identical after a session that starts nothing. `sample_and_decode`'s deadline: past it, one batch runs and is flushed, no result, and a resume gives the uninterrupted counts (`tests/test_evaluate_resume.py`). Slow: the population is the pinned 244 (digest `5008e14e…`) and equals `sample_bb_params(244, 72, CALIBRATION_CODE_SEED)`. 13 of 13 mutants caught: manifest check off, commit or population not checked, no inventory check, copy not verified, several pilot directories accepted, deadline ignored by the worker, workers started after the deadline, finished codes re-run, no `cpu_class` pre-check, stale code not re-queued, a death never failing a code, a died code retried in the same session |
| N-18 | Session 1 is the probe, and nothing runs after it without an approved cost report (D-033 amendment, `tests/test_pilot.py`). With no manifest, the session records its probe codes in the manifest and runs only them (`test_the_probe_runs_only_its_codes_and_its_work_counts`, slow; the next session runs the rest). A later session with `COST_GATE` unset, empty or blank is refused and writes nothing; with it, the gate is recorded in the manifest with the session number; a first session with `COST_GATE` set is refused as a likely forgotten `PREVIOUS` (`test_session_1_is_the_probe_and_every_later_session_needs_a_cost_gate`). Probe codes are evenly spaced ranks of `n * d_upper`, the largest and the smallest included (`test_probe_codes_are_evenly_spaced_ranks_including_the_largest`; on the real population, in the slow population test). `pilot_cost_report` on synthetic shards against the committed calibration: measured/projected ratios 2 and 3, median 2.5, max 3; re-projected core-hours equal the finished code's measured seconds, plus the partial code's measured seconds/shot times the model's run shots, plus every other code's projection times the ratio; 1 failure in enough shots that 100 would need more than `MAX_SHOTS` (256 at 10,240, 512 at 40,960; derived from the constant since D-034) projects censored and 105 in 512 does not; the probe codes listed by measured failure fraction; with `admissible_codes` and `sample_and_decode` patched to fail, so it neither enumerates nor decodes (`test_the_cost_report_on_synthetic_shards`). It refuses a pilot with no probe session. `_project_pilot(per_code=True)` is the fitted power law per code and sums to its total, and without the flag its output is unchanged. `notebooks/pilot.ipynb`: a runbook markdown cell, then six code cells with cells 1–2 identical to the template, no outputs, and the runbook's key steps also in `spec/architecture.md §2` (`test_pilot_notebook_follows_the_template_and_carries_the_runbook`); its install cell passes the D-030 tests with the other two notebooks. 7 of 7 mutants caught: no cost gate required, a probe with a gate allowed, the probe running every code, probe ranks missing the smallest code, the median case priced at the max ratio, a partial probe code priced at the model, probe censoring taken from the donor |
| N-19 | Assembly writes exactly the population minus `EXCLUDED_CODES` (D-036, `tests/test_pilot.py`, three [[12]] codes checkpointed in-process, one listed). A code that is unfinished and not listed is refused, by name (`test_assembly_refuses_an_unfinished_code_that_is_not_excluded`); exactly the listed code missing writes 2 rows, the excluded id and reason in the Parquet metadata (`test_assembly_accepts_exactly_the_excluded_codes_missing`); a listed code with a result is refused (`test_assembly_refuses_an_excluded_code_that_has_a_result`), as is a listed code outside the population. On the real pins, `DATASET_SIZE` = 242 = 244 − 2 and `run_m0_evaluation` expects 242 (`test_the_m0_dataset_is_242_rows_of_the_244_codes`); the slow population test checks both listed codes are in it and that `bb_schedule` refuses them. Each test fails when its logic is reverted (8 mutants, all caught, AGENT_LOG 2026-10-02) |
| N-09 | Requesting a family that does not exist raises `KeyError` listing available families, rather than returning an empty frame |

N-08 is the one that catches a broken circuit builder, which is otherwise invisible — a wrong circuit still produces plausible-looking LERs. It is `test_p0_zero_detection_events`, and it is necessary but not sufficient: N-10 exists because a circuit whose detectors detect nothing also has zero events at `p=0`. `test_detector_error_model_builds` (Stim refuses non-deterministic detectors) is what caught an interleaved X/Z schedule in mutation testing.

## 5. Telemetry

`decode_seconds` is recorded per row. No other telemetry exists; there is no analytics, no tracking, and no network call anywhere in the project (INV-9).

## 6. Pre-release gate

- [ ] `pytest -q -m "slow or not slow"` (the full suite) passes, zero failures, zero new warnings
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

### 2026-09-27 — M0-EVAL-07 decoder calibration (calibration result, not a milestone verdict)

Recorded here because it is a measurement that the decoder, `P_PILOT`, `SHOT_BATCH` and `MAX_SHOTS` decisions will rest on. It is **not** an M0 verdict and it moves no exit criterion. Nothing below is a label: every file is marked `"calibration": true`, and `reject_calibration` refuses the directory (D-029).

**Run.** `notebooks/calibrate.ipynb` on Kaggle at `7e91f82`, provenance read back: Python 3.12.13, stim 1.16.0, ldpc 2.4.1, `x86_64/sse2`. Grid and decoders as D-029. 4 workers on 4 cores, so every ms/shot below is one core under full load. **Evidence:** `evidence/calibration/2026-09-27-7e91f82/` holds 35 files: `plan.json`, `summary.json`, the artifact and 32 cell files. They are byte-identical to the Kaggle output zip. `summarize()` on this directory at the current commit reproduces the stored `summary.json`, apart from the last digits of the power-law fit.

**Cells.** 32 in all:
- 27 completed: 11 stopped at `MIN_FAILURES` on every decoder, 16 at the 20-min wall cap, 0 at `max_shots`.
- 1 killed: [[112,6,≤14]] at p=0.003.
- 4 died: [[140,6,≤16]] at every p.

Most large-code cells have ≤ 24 shots, so their intervals are wide. Every per-round rate below is the INV-4 Z-memory rate per round per logical qubit. The 95% Wilson interval is mapped through `logical_error_rate`. Point estimates are shown even where INV-3 would censor a label.

#### Size scaling per template (BP+OSD)

| Template | p | Smaller code: fail/shots, rate [95%] | Larger code(s) | Reading |
|---|---|---|---|---|
| sym_3_3 | 0.001 | [[72]] 13/670, 2.7e-4 [1.6e-4, 4.7e-4] | [[144]] 0/24, ≤ 1.0e-3 | unresolved |
| sym_3_3 | 0.0015 | [[72]] 27/556, 6.9e-4 [4.7e-4, 1.0e-3] | [[144]] 2/21, 7.0e-4 [1.9e-4, 2.4e-3] | unresolved; equal point estimates |
| sym_3_3 | 0.002 | [[72]] 87/486, 2.7e-3 [2.2e-3, 3.4e-3] | [[144]] 1/20, 3.6e-4 [6.2e-5, 1.9e-3] | **sub-threshold**, intervals separate |
| sym_3_3 | 0.003 | [[72]] 100/283, 6.0e-3 [4.9e-3, 7.3e-3] | [[144]] 9/11, 1.2e-2 [5.1e-3, 2.0e-2] | larger code's point estimate higher; intervals overlap |
| pair_2_2 | 0.001 | [[12]] 100/20521, 8.1e-4 [6.7e-4, 9.9e-4] | [[136]] 0/238, ≤ 7.3e-4 | consistent with sub-threshold; intervals overlap |
| pair_2_2 | 0.0015 | [[12]] 100/11244, 1.5e-3 [1.2e-3, 1.8e-3] | [[136]] 0/179, ≤ 9.7e-4 | **sub-threshold**, separate |
| pair_2_2 | 0.002 | [[12]] 100/5229, 3.2e-3 [2.6e-3, 3.9e-3] | [[136]] 0/164, ≤ 1.05e-3 | **sub-threshold**, separate |
| pair_2_2 | 0.003 | [[12]] 100/3015, 5.6e-3 [4.6e-3, 6.8e-3] | [[136]] 5/159, 1.5e-3 [6.2e-4, 3.4e-3] | **sub-threshold**, separate |
| mixed_3_5 | 0.001 | [[42]] 100/595, 5.1e-3 [4.2e-3, 6.2e-3] | [[112]] 3/9, 4.8e-3 [1.5e-3, 1.2e-2]; [[140]] died | no improvement; every interval above p |
| mixed_3_5 | 0.0015 | [[42]] 100/279, 1.2e-2 [1.0e-2, 1.5e-2] | [[112]] 5/8, 1.2e-2 [4.3e-3, 2.3e-2]; [[140]] died after 3 shots (2 OSD failures) | no improvement; every interval above p |
| mixed_3_5 | 0.002 | [[42]] 100/192, 2.0e-2 [1.6e-2, 2.4e-2] | [[112]] 5/7, 1.5e-2 [5.3e-3, 2.9e-2]; [[140]] died | no improvement; every interval above p |
| mixed_3_5 | 0.003 | [[42]] 100/119, 5.0e-2 [3.9e-2, 6.1e-2] | [[112]] killed (3/3 failed before the kill); [[140]] died | no larger-code data |

What each template shows:
- **pair_2_2** shows sub-threshold behaviour at p = 0.0015, 0.002 and 0.003. At 0.001 it is consistent with it but not separated.
- **sym_3_3** shows it at p = 0.002 only, and on 20 gross shots. At 0.0015 the two point estimates are equal. At 0.003 the gross estimate is higher.
- **mixed_3_5** shows it at no p. Its [[42]] and [[112]] point estimates agree within 30% at every p where both exist. Every completed mixed_3_5 interval lies wholly above p, so the encoded qubit does worse per round than an unprotected one.

The threshold is therefore template-dependent. `quad_4_2` has one calibration code, and the other 7 templates have none, so no size-scaling reading exists for them.

#### BP+LSD vs BP+OSD, paired (same shots, 27 completed cells)

"Disc." is the discordant shots: only LSD fails / only OSD fails. p is McNemar's exact test. The ratio is LSD failures / OSD failures. ms/shot is `decode()` wall time per shot, one core.

| p | Code | Shots (stop) | OSD fail | LSD-0 fail | Disc. | p | LSD-0/OSD | LSD-4 fail | Disc. | p | LSD-4/OSD | OSD ms | LSD-0 ms | LSD-4 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.001 | [[12,2,≤3]] pair_2_2 | 20521 (min_f) | 100 | 231 | 149/18 | 7.5e-27 | 2.31 | 225 | 139/14 | 4.7e-27 | 2.25 | 0.2 | 0.2 | 0.2 |
| 0.001 | [[42,6,≤6]] mixed_3_5 | 595 (min_f) | 100 | 174 | 75/1 | 2.0e-21 | 1.74 | 147 | 57/10 | 4.0e-9 | 1.47 | 1,100 | 154 | 154 |
| 0.001 | [[48,4,≤8]] quad_4_2 | 1084 (wall) | 19 | 48 | 31/2 | 1.3e-7 | 2.53 | 40 | 23/2 | 1.9e-5 | 2.11 | 944 | 79 | 81 |
| 0.001 | [[72,12,≤6]] sym_3_3 | 670 (wall) | 13 | 25 | 12/0 | 4.9e-4 | 1.92 | 23 | 10/0 | 2.0e-3 | 1.77 | 1,589 | 98 | 101 |
| 0.001 | [[112,6,≤14]] mixed_3_5 | 9 (wall) | 3 | 2 | 0/1 | 1 | 0.67 | 3 | 0/0 | 1 | 1.00 | 124,625 | 3,949 | 3,952 |
| 0.001 | [[136,2,≤11]] pair_2_2 | 238 (wall) | 0 | 0 | 0/0 | 1 | – | 0 | 0/0 | 1 | – | 4,875 | 85 | 86 |
| 0.001 | [[144,12,≤12]] sym_3_3 | 24 (wall) | 0 | 0 | 0/0 | 1 | – | 0 | 0/0 | 1 | – | 48,179 | 1,135 | 1,136 |
| 0.0015 | [[12,2,≤3]] pair_2_2 | 11244 (min_f) | 100 | 230 | 145/15 | 6.8e-28 | 2.30 | 216 | 129/13 | 3.5e-25 | 2.16 | 0.3 | 0.3 | 0.3 |
| 0.0015 | [[42,6,≤6]] mixed_3_5 | 279 (min_f) | 100 | 143 | 46/3 | 7.0e-11 | 1.43 | 133 | 38/5 | 2.5e-7 | 1.33 | 1,479 | 256 | 258 |
| 0.0015 | [[48,4,≤8]] quad_4_2 | 854 (wall) | 57 | 114 | 60/3 | 9.0e-15 | 2.00 | 97 | 45/5 | 4.2e-9 | 1.70 | 1,183 | 110 | 111 |
| 0.0015 | [[72,12,≤6]] sym_3_3 | 556 (wall) | 27 | 51 | 24/0 | 1.2e-7 | 1.89 | 43 | 18/2 | 4.0e-4 | 1.59 | 1,889 | 132 | 134 |
| 0.0015 | [[112,6,≤14]] mixed_3_5 | 8 (wall) | 5 | 5 | 0/0 | 1 | 1.00 | 5 | 0/0 | 1 | 1.00 | 129,728 | 8,608 | 8,482 |
| 0.0015 | [[136,2,≤11]] pair_2_2 | 179 (wall) | 0 | 0 | 0/0 | 1 | – | 0 | 0/0 | 1 | – | 6,485 | 107 | 107 |
| 0.0015 | [[144,12,≤12]] sym_3_3 | 21 (wall) | 2 | 2 | 0/0 | 1 | 1.00 | 2 | 0/0 | 1 | 1.00 | 52,955 | 1,925 | 1,905 |
| 0.002 | [[12,2,≤3]] pair_2_2 | 5229 (min_f) | 100 | 173 | 86/13 | 2.3e-14 | 1.73 | 162 | 77/15 | 3.3e-11 | 1.62 | 0.5 | 0.3 | 0.3 |
| 0.002 | [[42,6,≤6]] mixed_3_5 | 192 (min_f) | 100 | 133 | 36/3 | 3.6e-8 | 1.33 | 123 | 25/2 | 5.6e-6 | 1.23 | 1,688 | 348 | 352 |
| 0.002 | [[48,4,≤8]] quad_4_2 | 571 (min_f) | 100 | 159 | 65/6 | 1.3e-13 | 1.59 | 136 | 44/8 | 4.0e-7 | 1.36 | 1,304 | 151 | 154 |
| 0.002 | [[72,12,≤6]] sym_3_3 | 486 (wall) | 87 | 121 | 38/4 | 5.7e-8 | 1.39 | 115 | 30/2 | 2.5e-7 | 1.32 | 2,068 | 198 | 198 |
| 0.002 | [[112,6,≤14]] mixed_3_5 | 7 (wall) | 5 | 4 | 0/1 | 1 | 0.80 | 5 | 0/0 | 1 | 1.00 | 154,093 | 10,351 | 10,466 |
| 0.002 | [[136,2,≤11]] pair_2_2 | 164 (wall) | 0 | 0 | 0/0 | 1 | – | 0 | 0/0 | 1 | – | 7,085 | 114 | 117 |
| 0.002 | [[144,12,≤12]] sym_3_3 | 20 (wall) | 1 | 3 | 2/0 | 0.5 | 3.00 | 2 | 1/0 | 1 | 2.00 | 55,580 | 2,558 | 2,599 |
| 0.003 | [[12,2,≤3]] pair_2_2 | 3015 (min_f) | 100 | 175 | 86/11 | 1.4e-15 | 1.75 | 150 | 69/19 | 7.8e-8 | 1.50 | 0.8 | 0.4 | 0.4 |
| 0.003 | [[42,6,≤6]] mixed_3_5 | 119 (min_f) | 100 | 101 | 2/1 | 1 | 1.01 | 101 | 2/1 | 1 | 1.01 | 1,892 | 592 | 594 |
| 0.003 | [[48,4,≤8]] quad_4_2 | 242 (min_f) | 100 | 129 | 34/5 | 2.4e-6 | 1.29 | 123 | 27/4 | 3.4e-5 | 1.23 | 1,382 | 297 | 299 |
| 0.003 | [[72,12,≤6]] sym_3_3 | 283 (min_f) | 100 | 137 | 38/1 | 1.5e-10 | 1.37 | 120 | 25/5 | 3.2e-4 | 1.20 | 2,303 | 371 | 371 |
| 0.003 | [[136,2,≤11]] pair_2_2 | 159 (wall) | 5 | 4 | 1/2 | 1 | 0.80 | 4 | 1/2 | 1 | 0.80 | 7,172 | 172 | 181 |
| 0.003 | [[144,12,≤12]] sym_3_3 | 11 (wall) | 9 | 9 | 0/0 | 1 | 1.00 | 9 | 0/0 | 1 | 1.00 | 77,820 | 18,117 | 18,160 |

**Failures.** BP+LSD fails more often than BP+OSD in 15 of the 27 cells, both orders, at McNemar p ≤ 2e-3. Those are every cell on [[12]], [[42]], [[48]] and [[72]] except [[42]] at p=0.003. No cell shows LSD significantly better. The other 12 cells cannot resolve a difference: the large codes have ≤ 238 shots, and [[42]] at p=0.003 has 3 discordant shots.

**The ratio is not constant.** Across those 15 cells, LSD-0/OSD runs from 1.29 to 2.53, and LSD-4/OSD from 1.20 to 2.25. It depends on the code, and within every code it falls as p rises:
- [[12]]: 2.31 → 1.75
- [[42]]: 1.74 → 1.01
- [[48]]: 2.53 → 1.29
- [[72]]: 1.92 → 1.37

A fixed correction factor between the two decoders' labels would be wrong. LSD-4 fails no more often than LSD-0 in every resolved cell.

**Cost.** OSD vs LSD ms/shot per code, over the four p (LSD-0; LSD-4 is within 6% of it everywhere):

| Code | OSD ms/shot | LSD-0 ms/shot | OSD / LSD |
|---|---|---|---|
| [[12,2,≤3]] | 0.2–0.8 | 0.2–0.4 | 1–2× |
| [[42,6,≤6]] | 1,100–1,892 | 154–592 | 3–7× |
| [[48,4,≤8]] | 944–1,382 | 79–297 | 5–12× |
| [[72,12,≤6]] | 1,589–2,303 | 98–371 | 6–16× |
| [[136,2,≤11]] | 4,875–7,172 | 85–172 | 42–62× |
| [[112,6,≤14]] | 124,625–154,093 (225,348 at p=0.003, 3 shots before the kill) | 3,949–10,351 (54,191) | 15–32× |
| [[144,12,≤12]] | 48,179–77,820 | 1,135–18,117 | 4–42× |
| [[140,6,≤16]] | 344,149 (p=0.0015, 3 shots before dying) | 16,735 | 21× |

LSD's cost rises steeply with p on the large codes: gross costs 1.1 s at p=0.001 and 18 s at p=0.003. In the pinned BP+OSD, one gross shot costs 48–78 s. The (mm) planning figure was ~13–25 s.

**[[140,6,≤16]] died in all four cells** with exit code −9 at 4 workers. That is a SIGKILL the calibration's parent did not send, because its own kill is recorded as `killed`. The owner reads it as the kernel's out-of-memory kill. Three of the cells died before their first `decode()` call (`batch_index` null, no partial). The p=0.0015 cell died during shot 3's BP+OSD decode, after 3 shots.

**The killed [[112,6,≤14]] cell at p=0.003 is explained by its per-shot timings. There is no evidence of a hang on a real shot.**
- Setup, the time to build the circuit, DEM and decoders, was 24–26 s in this code's three completed cells.
- The kept partial covers 3 shots at 225 s (OSD) + 54 s + 54 s (LSD) per shot, 1,001 s of decoding in all. So shot 3 started at about 1,026 s, before the 1,200 s cap. The cap is checked between shots, not between decoders.
- At the same rates, shot 3's OSD and LSD-0 end at about 1,305 s, and its LSD-4 at about 1,360 s. The hard kill at 1,320 s (cap + 120 s margin) fell inside LSD-4, which is exactly where it was recorded.

The 120 s margin was sized for "one shot per decoder past the cap (~1 min on the largest code)". On this code one shot for all three decoders takes ~5.5 min. The syndrome-in-span check that D-029's amendment describes was not run, since nothing points to a hang.

**Closes?** M0-EVAL-07 is done: the run is recorded. Choosing the decoder, `P_PILOT`, `SHOT_BATCH` and `MAX_SHOTS` is the owner's decision, and CONTRACT changes need approval.
**Caveats carried forward:**
- The large-code cells rest on 7–24 shots (gross, [[112]]) or zero failures ([[136]]).
- The size-scaling readings cover three templates of 11.
- Every ms/shot is from a Kaggle CPU under 4 concurrent workers.

#### 2026-09-28 — Re-projection of the pilot from this calibration (owner's grid; no recommendation)

**Evidence:** `evidence/reprojection/2026-09-28/`, which holds `reproject.py` (exactly what produced the numbers) and `reprojection.json`. Nothing was decoded. The script calls `summarize()` on the calibration directory with other `population`, `max_shots` and `shot_batch` values.

**Setup:**
- **Decoder:** pinned BP+OSD only.
- **Grid:** p ∈ {0.0015, 0.002}, budget (max n) ∈ {48, 60, 72, 96}, MAX_SHOTS ∈ {10,000, 20,000, 50,000}, shot batch 256.
- **Population:** every admitted code at the budget. That is every `(template, l, m)` on the balanced sampler's grid that passes `validate` and has `estimate_d_upper(seed=0) ≥ 3`. It was checked to equal `sample_bb_params(<that many>, budget, CALIBRATION_CODE_SEED)`. Budget 96 has more than 300 codes, so the 300-code balanced draw is projected too.

**Models, unchanged from D-029:**
- **Cost:** seconds/shot is the power law in `n·d_upper`, fitted at each p over the 7 completed calibration codes. The slope is 2.92 at p=0.0015 and 2.84 at p=0.002, so cost goes roughly as (n·d_upper)³.
- **Failures:** each code takes the failure fraction of the calibration code nearest in `d_upper`, then `n`:
  - d_upper 3–4 take [[12,2,≤3]].
  - d_upper 5–6 take [[42,6,≤6]] or [[72,12,≤6]], whichever is nearer in `n`.
  - d_upper 7 is equally near d = 6 and d = 8, so it takes whichever of [[42]], [[72]] and [[48,4,≤8]] is nearest in `n`.
  - d_upper 8–9 take [[48,4,≤8]].
  - d_upper 10 takes [[136,2,≤11]], which has 0 failures, so "unknown".
- **Censored:** a code is censored if its shots to 100 failures exceed MAX_SHOTS. Unknown codes are costed at MAX_SHOTS.
- **Wall-hours:** `max(core-h / 4, longest single code)`, because one code runs per process.

**Above threshold at p** is read from the size-scaling table above. A template qualifies if it has at least two completed codes, its larger code's interval does not lie wholly below its smaller code's, and every completed code's interval lies wholly above p. At both p only **mixed_3_5** qualifies. pair_2_2 and sym_3_3 do not. The other 8 templates have no reading, and the last column reports their share.

Admitted codes per template:

| Budget | Codes | d_upper | Top third | sym_3_3 | pair_2_2 | quad_4_2 | rare_3_4 | rare_2_3 | mixed_3_5 | mod_2_3 | bb288_3_3 | tri_3_3 | diag_3_3 | sq_4_2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 48 | 116 | 3–8 | d ≥ 4 | 2 | 33 | 36 | 1 | 1 | 2 | 10 | 2 | 2 | 8 | 19 |
| 60 | 175 | 3–8 | d ≥ 4 | 4 | 48 | 51 | 2 | 1 | 4 | 15 | 4 | 4 | 12 | 30 |
| 72 | 244 | 3–9 | d ≥ 5 | 7 | 65 | 68 | 3 | 2 | 5 | 21 | 7 | 7 | 17 | 42 |
| 96 | 373 | 3–10 | d ≥ 5 | 9 | 99 | 102 | 5 | 4 | 8 | 32 | 9 | 9 | 29 | 67 |
| 96, 300 drawn | 300 | 3–10 | d ≥ 6 | 9 | 65 | 65 | 5 | 4 | 8 | 32 | 9 | 9 | 29 | 65 |

Projection:

| Budget | p | MAX_SHOTS | Codes | Core-h | Wall-h, 4 cores | Longest code, core-h | Censored overall (+unknown) | Censored, top third (+unknown) | From above-threshold templates | From templates with no reading |
|---|---|---|---|---|---|---|---|---|---|---|
| 48 | 0.0015 | 10,000 | 116 | 12.5 | 3.1 | 0.4 | 97 = 84% (+0) | 20/39 = 51% (+0) | 1.7% | 68.1% |
| 48 | 0.0015 | 20,000 | 116 | 13.9 | 3.5 | 0.4 | 0% (+0) | 0/39 (+0) | 1.7% | 68.1% |
| 48 | 0.0015 | 50,000 | 116 | 13.9 | 3.5 | 0.4 | 0% (+0) | 0/39 (+0) | 1.7% | 68.1% |
| 48 | 0.002 | 10,000 | 116 | 8.4 | 2.1 | 0.2 | 0% (+0) | 0/39 (+0) | 1.7% | 68.1% |
| 48 | 0.002 | 20,000 | 116 | 8.4 | 2.1 | 0.2 | 0% (+0) | 0/39 (+0) | 1.7% | 68.1% |
| 48 | 0.002 | 50,000 | 116 | 8.4 | 2.1 | 0.2 | 0% (+0) | 0/39 (+0) | 1.7% | 68.1% |
| 60 | 0.0015 | 10,000 | 175 | 33.4 | 8.3 | 0.7 | 128 = 73% (+0) | 12/59 = 20% (+0) | 2.3% | 68.0% |
| 60 | 0.0015 | 20,000 | 175 | 36.6 | 9.1 | 0.7 | 0% (+0) | 0/59 (+0) | 2.3% | 68.0% |
| 60 | 0.0015 | 50,000 | 175 | 36.6 | 9.1 | 0.7 | 0% (+0) | 0/59 (+0) | 2.3% | 68.0% |
| 60 | 0.002 | 10,000 | 175 | 21.2 | 5.3 | 0.4 | 0% (+0) | 0/59 (+0) | 2.3% | 68.0% |
| 60 | 0.002 | 20,000 | 175 | 21.2 | 5.3 | 0.4 | 0% (+0) | 0/59 (+0) | 2.3% | 68.0% |
| 60 | 0.002 | 50,000 | 175 | 21.2 | 5.3 | 0.4 | 0% (+0) | 0/59 (+0) | 2.3% | 68.0% |
| 72 | 0.0015 | 10,000 | 244 | 90.8 | 22.7 | 1.6 | 162 = 66% (+0) | 0/82 (+0) | 2.0% | 68.4% |
| 72 | 0.0015 | 20,000 | 244 | 97.4 | 24.4 | 1.6 | 0% (+0) | 0/82 (+0) | 2.0% | 68.4% |
| 72 | 0.0015 | 50,000 | 244 | 97.4 | 24.4 | 1.6 | 0% (+0) | 0/82 (+0) | 2.0% | 68.4% |
| 72 | 0.002 | 10,000 | 244 | 52.5 | 13.1 | 0.9 | 0% (+0) | 0/82 (+0) | 2.0% | 68.4% |
| 72 | 0.002 | 20,000 | 244 | 52.5 | 13.1 | 0.9 | 0% (+0) | 0/82 (+0) | 2.0% | 68.4% |
| 72 | 0.002 | 50,000 | 244 | 52.5 | 13.1 | 0.9 | 0% (+0) | 0/82 (+0) | 2.0% | 68.4% |
| 96 | 0.0015 | 10,000 | 373 | 417.9 | 104.5 | 29.4 | 227 = 61% (+5) | 0/125 (+5) | 2.1% | 68.9% |
| 96 | 0.0015 | 20,000 | 373 | 561.8 | 140.4 | 58.8 | 0% (+5) | 0/125 (+5) | 2.1% | 68.9% |
| 96 | 0.0015 | 50,000 | 373 | 935.2 | 233.8 | 146.9 | 0% (+5) | 0/125 (+5) | 2.1% | 68.9% |
| 96 | 0.002 | 10,000 | 373 | 302.8 | 75.7 | 32.6 | 0% (+5) | 0/125 (+5) | 2.1% | 68.9% |
| 96 | 0.002 | 20,000 | 373 | 441.5 | 110.4 | 65.2 | 0% (+5) | 0/125 (+5) | 2.1% | 68.9% |
| 96 | 0.002 | 50,000 | 373 | 857.7 | 214.4 | 163.1 | 0% (+5) | 0/125 (+5) | 2.1% | 68.9% |
| 96, 300 drawn | 0.0015 | 10,000 | 300 | 352.5 | 88.1 | 29.4 | 181 = 60% (+4) | 0/100 (+4) | 2.7% | 72.7% |
| 96, 300 drawn | 0.0015 | 20,000 | 300 | 472.4 | 118.1 | 58.8 | 0% (+4) | 0/100 (+4) | 2.7% | 72.7% |
| 96, 300 drawn | 0.0015 | 50,000 | 300 | 783.4 | 195.8 | 146.9 | 0% (+4) | 0/100 (+4) | 2.7% | 72.7% |
| 96, 300 drawn | 0.002 | 10,000 | 300 | 254.2 | 63.6 | 32.6 | 0% (+4) | 0/100 (+4) | 2.7% | 72.7% |
| 96, 300 drawn | 0.002 | 20,000 | 300 | 369.6 | 92.4 | 65.2 | 0% (+4) | 0/100 (+4) | 2.7% | 72.7% |
| 96, 300 drawn | 0.002 | 50,000 | 300 | 715.7 | 178.9 | 163.1 | 0% (+4) | 0/100 (+4) | 2.7% | 72.7% |

**Where the cost model interpolates.** The fit codes' `n·d_upper` values, which are the same set at both p:

| Fit code | [[12]] | [[42]] | [[48]] | [[72]] | [[136]] | [[112]] | [[144]] |
|---|---|---|---|---|---|---|---|
| n·d_upper | 36 | 252 | 384 | 432 | 1,496 | 1,568 | 1,728 |

**No code at any budget lies outside 36–1,728.** Codes per bracket (a single name means an exact match):

| Budget | [[12]] | [[12]]–[[42]] | [[42]] | [[42]]–[[48]] | [[48]] | [[48]]–[[72]] | [[72]] | [[72]]–[[136]] |
|---|---|---|---|---|---|---|---|---|
| 48 | 3 | 104 | 1 | 6 | 2 | 0 | 0 | 0 |
| 60 | 3 | 138 | 1 | 25 | 2 | 1 | 0 | 5 |
| 72 | 3 | 147 | 1 | 54 | 4 | 3 | 16 | 16 |
| 96 | 3 | 151 | 9 | 93 | 18 | 5 | 16 | 78 |
| 96, 300 drawn | 2 | 117 | 8 | 72 | 14 | 4 | 16 | 67 |

**Read these with the models' limits in view:**
- **The power law misses the fit codes themselves by 0.17–7×.** Predicted / measured BP+OSD ms/shot:

  | p | [[12]] | [[42]] | [[48]] | [[72]] | [[136]] | [[112]] | [[144]] |
  |---|---|---|---|---|---|---|---|
  | 0.0015 | 2.94 | 0.17 | 0.75 | 0.66 | 7.18 | 0.41 | 1.34 |
  | 0.002 | 2.72 | 0.19 | 0.80 | 0.70 | 7.03 | 0.37 | 1.35 |

  At every budget, most codes lie between [[12]] and [[42]], and [[42]]'s measured cost is 5.3–5.7× the fit there. `n·d_upper` does not separate [[136,2]] (weight-4 checks, 31,960 DEM mechanisms) from [[112,6]] (weight-8, 88,704).
- **The censoring columns follow the donor codes.** Every d_upper 3–4 code borrows [[12]]'s 11,244 shots to 100 failures at p=0.0015. So the 10,000-shot rows at that p censor all of them, and at 20,000 shots none. The top third's censoring falls as the budget grows, because more of it moves past d_upper 4 to donors that fail more often.
- The "+unknown" codes are d_upper-10 codes borrowing [[136]]'s zero failures.
- The "above-threshold" column counts mixed_3_5 codes only. But [[42,6,≤6]] is a mixed_3_5 code whose every interval lies above p, and it is also the failure-fraction donor for many d_upper 5–7 codes of other templates.

#### 2026-09-29 — The pilot's probe, session 1 at `27873ec` (calibration-type result, not a verdict)

Recorded as a measurement that `MAX_SHOTS` and the M0 budget rest on (D-034). It is not an M0 verdict, moves no exit criterion, and none of its rows is a label: the pilot restarts fresh at `MAX_SHOTS` = 40,960, and `assemble_measurements` refuses this pilot (its manifest records 10,240, and 232 codes are unstarted).

**Run.** `notebooks/pilot.ipynb` session 1 on Kaggle at `27873ec`: the probe, 12 codes at evenly spaced ranks of `n·d_upper` over the 244-code population, 3 h, 4 workers, `MAX_SHOTS` = 10,240. All 12 codes finished. **Evidence:** `evidence/pilot/probe1-27873ec/` holds `m0-pilot.tar` and `m0-pilot.tar.sha256` as downloaded, sha256 `e30a07195a235184ff1eb3475cbdb859a2ba0b4b3dff036d148b1f377bddaf62` (checked against the sidecar when committed).

**The cost report, as the owner ran it at `27873ec`** (`pilot_cost_report` on the tar against `evidence/calibration/2026-09-27-7e91f82`):

```
probe codes (measured vs projected BP+OSD s/shot; measured vs donor failure fraction):
  bb_v1_quad_4_2-03c24c84c800 [[70,2,<=9]] 1280 shots: s/shot 3.8 vs 4.26 (x0.893); failure fraction 0.0805 vs 0.175 (bb_v1_quad_4_2-c7c6d07a81bf)
  bb_v1_pair_2_2-721eb061d211 [[72,2,<=6]] 10240 shots: s/shot 0.33 vs 1.46 (x0.226); failure fraction 0.00479 vs 0.179 (ref72)
  bb_v1_rare_3_4-6793f7622e98 [[70,6,<=5]] 512 shots: s/shot 2.74 vs 0.801 (x3.42); failure fraction 0.23 vs 0.179 (ref72)
  bb_v1_pair_2_2-570f19471ff8 [[48,2,<=6]] 10240 shots: s/shot 0.141 vs 0.46 (x0.305); failure fraction 0.00381 vs 0.521 (bb_v1_mixed_3_5-cf5649b397df)
  bb_v1_pair_2_2-42a40c4140d4 [[64,2,<=4]] 10240 shots: s/shot 0.0951 vs 0.329 (x0.289); failure fraction 0.00967 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_quad_4_2-e3d9e7ce1e14 [[60,2,<=4]] 768 shots: s/shot 0.509 vs 0.274 (x1.86); failure fraction 0.176 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_diag_3_3-0127099528eb [[48,4,<=4]] 768 shots: s/shot 0.312 vs 0.145 (x2.15); failure fraction 0.145 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_quad_4_2-31b1559a4450 [[42,2,<=4]] 1024 shots: s/shot 0.229 vs 0.0995 (x2.3); failure fraction 0.107 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_sq_4_2-1f7815221846 [[48,2,<=3]] 1280 shots: s/shot 0.153 vs 0.0642 (x2.38); failure fraction 0.0805 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_mod_2_3-8e06f820914a [[30,4,<=4]] 2304 shots: s/shot 0.0476 vs 0.0382 (x1.24); failure fraction 0.0464 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_quad_4_2-9c1e1f44b1c1 [[24,2,<=4]] 1024 shots: s/shot 0.0564 vs 0.0203 (x2.78); failure fraction 0.106 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_sq_4_2-729429a7ebad [[12,2,<=3]] 1536 shots: s/shot 0.00488 vs 0.00125 (x3.91); failure fraction 0.0729 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
ratio measured/projected over 12 codes: median 2, max 3.91, min 0.226
core-hours: projected 52.5; re-projected at the median ratio 103.0 (architecture §6: 52.5), at the max ratio 197.9 (ceiling 158.0)
censored at MAX_SHOTS: overall 3/244 (+0 unknown); top third by d_upper 2/82 (+0); lowest-failure-fraction third of the probe 3/4 (+0)
```

Re-run on the committed tar after D-034, the output is identical except that "architecture §6" reads 110.0 (`PROJECTED_CORE_HOURS`). The projections that depend on `MAX_SHOTS` do not move: the three censored probe codes are finished, so they are read as censored from their own counts, and the D-029 model projects no other code near either cap.

**What it shows:**
- **Three of 12 codes were censored at 10,240 shots, all pair_2_2**, at failure fractions 0.0038–0.0097 (39–99 failures). They are the probe's three lowest-failure codes, the ones Recall@30-of-top-10 depends on. At 40,960 all three would reach 100 failures: they need about 26,200, 20,900 and 10,300 shots.
- **The borrowed failure fractions were off by up to 137×** (0.00381 measured against the donor's 0.521 for [[48,2,≤6]]). So the D-029 model's "0% censored" was void.
- **Measured seconds/shot ran 0.23–3.9× the model.** The three lowest ratios (0.23–0.31) are the three low-failure pair_2_2 codes; the other nine run 0.89–3.9.

**The owner's cost reading (D-034):** the 12 probe codes took **3.69 core-hours** of decoding. They are evenly spaced ranks of `n·d_upper`, so the population is ~244/12 of that: **~75 core-hours at `MAX_SHOTS` = 10,240**. At 40,960, adding the extra shots the three censored codes need at their measured rates: **~110 core-hours, estimated**, under the 158 ceiling (`spec/architecture.md §6`). The agent's check: the per-code shots × seconds/shot above sum to 13,300 s = 3.69 h; the three codes' extra shots to 100 failures add ~5,800 s, and (13,300 + 5,800) × 244/12 s = ~108 core-hours.

**The report's ratio re-projection (103 / 198 core-hours) is not used.** It multiplies each unmeasured code's D-029 projection by one ratio. That projection is seconds/shot × shots, and the shots come from the borrowed failure fractions, which the probe showed are off by up to 137× in both directions. A ratio fitted on seconds/shot does not correct the shot count. And the ratios are not one scale: they run 0.23–3.9, and the three lowest belong to the three low-failure codes, so the median and the maximum stand for different parts of the population, not for a central and a worst case. The probe itself is a stratified sample of the population by `n·d_upper`, so scaling its measured total is the more direct estimate. Both are extrapolations from 12 codes.

**Closes?** Nothing. It changes `MAX_SHOTS` (D-034, CONTRACT). M0-RUN-03 restarts from session 1 at the new cap.
**Caveats carried forward:**
- 12 codes; the ~110 assumes the rest of the population censors at 10,240 as often as the probe (3 of 12) and at the same kind of failure fraction. A code with a failure fraction below ~0.0024 still censors at 40,960, at up to 40,960 × its seconds/shot.
- All seconds/shot are one core of a 4-core Kaggle CPU under 4 workers.

#### 2026-09-30 — M0 pilot probe 2 at 1131f10 (cost gate approved)

This title is the `COST_GATE` string session 2 uses. It is the cost gate for the restarted pilot (D-034), not an M0 verdict, and it moves no exit criterion.

**Run.** `notebooks/pilot.ipynb` session 1 of the restarted pilot on Kaggle at `1131f10`: the probe, the same 12 codes as probe 1, `MAX_SHOTS` = 40,960. The manifest in the tar records `commit_sha` `1131f1000fdf0708dc7ba46e63d8859140d2c2bb` and `max_shots` 40960. **Evidence:** `evidence/pilot/probe2-1131f10/` holds `m0-pilot.tar` and `m0-pilot.tar.sha256` as downloaded, sha256 `55cf7b737e3f8cc030150139a4b2ca352c763722cb0d6e5217c743b9d6dafe74`, checked with `sha256sum -c` when committed.

**The cost report, as the owner ran it** (`pilot_cost_report` on the tar against `evidence/calibration/2026-09-27-7e91f82`):

```
probe codes (measured vs projected BP+OSD s/shot; measured vs donor failure fraction):
  bb_v1_quad_4_2-03c24c84c800 [[70,2,<=9]] 1280 shots: s/shot 4.27 vs 4.26 (x1); failure fraction 0.0805 vs 0.175 (bb_v1_quad_4_2-c7c6d07a81bf)
  bb_v1_pair_2_2-721eb061d211 [[72,2,<=6]] 20480 shots: s/shot 0.303 vs 1.46 (x0.208); failure fraction 0.00488 vs 0.179 (ref72)
  bb_v1_rare_3_4-6793f7622e98 [[70,6,<=5]] 512 shots: s/shot 2.8 vs 0.801 (x3.49); failure fraction 0.23 vs 0.179 (ref72)
  bb_v1_pair_2_2-570f19471ff8 [[48,2,<=6]] 24576 shots: s/shot 0.144 vs 0.46 (x0.314); failure fraction 0.00407 vs 0.521 (bb_v1_mixed_3_5-cf5649b397df)
  bb_v1_pair_2_2-42a40c4140d4 [[64,2,<=4]] 10496 shots: s/shot 0.0987 vs 0.329 (x0.3); failure fraction 0.00953 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_quad_4_2-e3d9e7ce1e14 [[60,2,<=4]] 768 shots: s/shot 0.521 vs 0.274 (x1.9); failure fraction 0.176 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_diag_3_3-0127099528eb [[48,4,<=4]] 768 shots: s/shot 0.331 vs 0.145 (x2.28); failure fraction 0.145 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_quad_4_2-31b1559a4450 [[42,2,<=4]] 1024 shots: s/shot 0.239 vs 0.0995 (x2.4); failure fraction 0.107 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_sq_4_2-1f7815221846 [[48,2,<=3]] 1280 shots: s/shot 0.154 vs 0.0642 (x2.4); failure fraction 0.0805 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_mod_2_3-8e06f820914a [[30,4,<=4]] 2304 shots: s/shot 0.0479 vs 0.0382 (x1.25); failure fraction 0.0464 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_quad_4_2-9c1e1f44b1c1 [[24,2,<=4]] 1024 shots: s/shot 0.0669 vs 0.0203 (x3.3); failure fraction 0.106 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
  bb_v1_sq_4_2-729429a7ebad [[12,2,<=3]] 1536 shots: s/shot 0.00496 vs 0.00125 (x3.98); failure fraction 0.0729 vs 0.0191 (bb_v1_pair_2_2-afbf55db2c35)
ratio measured/projected over 12 codes: median 2.09, max 3.98, min 0.208
core-hours: projected 52.5; re-projected at the median ratio 108.9 (architecture §6: 110.0), at the max ratio 202.7 (ceiling 158.0)
censored at MAX_SHOTS: overall 0/244 (+0 unknown); top third by d_upper 0/82 (+0); lowest-failure-fraction third of the probe 0/4 (+0)
```

**What it shows:**
- **12 of 12 codes finished, 0 censored.** The three pair_2_2 codes that censored at 10,240 in probe 1 finished at **20,480, 24,576 and 10,496 shots** ([[72,2,≤6]], [[48,2,≤6]], [[64,2,≤4]]). Probe 1 estimated about 20,900, 26,200 and 10,300.
- **Measured decode: ~5.3 core-hours.** Checked as Σ shots × s/shot over the 12 lines above: 18,962 s = 5.27 h. Scaled × 244/12, as for probe 1: **~107 core-hours**, against the ~110 estimate (D-034, `spec/architecture.md §6`) and the 158 ceiling.
- **"overall 0/244" is not a measurement.** 12 of the 244 codes were run. For the other 232 the report reads censoring from the D-029 model's donor failure fractions, which probe 1 showed are off by up to 137×. Only "0/12 of the probe" is measured.

**Approved by the owner as the cost gate for session 2 onward.**

**Closes?** Nothing. It opens M0-RUN-03's later sessions.
**Caveats carried forward:**
- ~107 is 12 codes scaled by 244/12. A code whose failure fraction is below ~0.0024 still censors at 40,960, at up to 40,960 × its seconds/shot. None of the 12 does.
- All seconds/shot are one core of a 4-core Kaggle CPU under 4 workers.

---

#### 2026-10-02 — M0 pilot session 3 at 1131f10 (closeout, D-036; not a verdict)

**Run.** `notebooks/pilot.ipynb` session 3 on Kaggle at `1131f1000fdf0708dc7ba46e63d8859140d2c2bb`, `COST_GATE` the probe 2 entry above.

**Summary.** Session 3 = **242 done, 0 partial, 2 not started, 0 failed, 0 row errors, of 244**. Died: 2, `bb_v1_mixed_3_5-be2d62a58d7d` and `bb_v1_mixed_3_5-41659195d87b`, `ValueError` in `bb_schedule`: B repeats a monomial (x³ = x at l = 2). Decode core-hours: **28.94 this session, 76.30 cumulative** (vs 115–120 estimated). Checked against `session_003.json` in the tar.

**Censored at the 40,960 cap: one code**, `bb_v1_pair_2_2-4faad046f1a9`, **93 failures** in 40,960 shots (confirmed against the assembled rows). Censoring rate 1/242 = 0.4%.

**Final archive:** `m0-pilot.tar` sha256 `ccef076d29db82a25148f55fafe3f3e6c9cb5d15943817266daf015dbc511aa8`, equal to its sidecar. Pilot SHA `1131f1000fdf0708dc7ba46e63d8859140d2c2bb`.

**Session 4 not run, per D-036.** The two codes are excluded as unbuildable under the pinned schedule; the dataset is 242 of 244 rows. Assembly on this tar (in a scratch `data/`) gives 242 rows under one protocol hash, `6230a7a8…cb32fe`.

**Closes?** Nothing by itself. No M0 verdict is recorded here.

---

### M0 verdict

#### 2026-10-03 — M0 verdict (owner's decision)

**No.** At Recall@30-of-top-10, leave-one-program-out, the model scores **0.200 [0.000, 0.600]** and Φ **0.000 [0.000, 0.000]**; model − Φ is **0.200 [0.000, 0.600]**, and the interval includes 0. With the censored code excluded: model 0.100, Φ 0.000.

**Kill condition (`spec/plan.md` M0, `spec/product.md §7`): not met.** It needs both "Φ's Spearman is already high" and "the model's advantage does not survive resampling". Φ's Spearman is **0.242 [0.118, 0.354]**, which is not high. The model's Spearman is **0.871 [0.838, 0.894]**, and model − Φ is **0.629 [0.521, 0.750]**, which excludes 0.

**Verdict: PROCEED, headline criterion FAIL.** The model ranks the whole population far better than Φ, but it does not find the top 10 better than Φ by a margin that survives resampling. This is not rounded up to a pass.

**Why recall did not separate.** All ten true top-10 codes are `bb_v1_pair_2_2`. Under leave-one-program-out, the fold that holds out pair_2_2 produces every one of their predictions, so one fold decides the headline metric, and each bootstrap resample of codes reuses that fold's predictions. The top 10 itself is not noise: the label-noise ceiling (recall of the observed ranking against Beta-redrawn labels) is **1.000 [1.000, 1.000]**. Φ scores 0 because every top-10 code has k = 2 and Φ ≤ 1.64. Each of them sits below more than 30 higher-k codes in Φ's order (at least 70 for every one; checked against `data/m0_measurements.parquet` and `data/m0_features.parquet`, a lookup, not a new metric).

**Evidence.** `evidence/m0-verdict/2026-10-03-1131f10/`, committed as produced by `qecscreen.verdict.run_m0_evaluation`, run by the owner:
- Both files were produced on Windows with CRLF line ends. This repository's git runs with `core.autocrlf=true`, so the stored blobs have LF line ends, and a Linux checkout gives the LF bytes. Both hashes are recorded:
- `m0_results.json`: sha256 `4145cfe4c981f81180e1176950bd3f57898d0a69df757eeb670e4b2da83cb067` as produced, `01c4fd0408dc45976c093b84604037ac73ea8a3170b0df81e71f0de365ae8b6a` as stored (CRs removed).
- `m0_results.txt`: sha256 `b182c70beada75f3456636c7654089a94a9ea978f439708c78de02502cf1d44b` as produced, `88b7db51b43f516da13710011a5d764b4f9429c9ca79e41907403b3c31e043a9` as stored (CRs removed).
- Inputs, gitignored, hashes only (each equal to the hash `m0_results.json` records): `data/m0_measurements.parquet` `5c644c028ff81803e904bda86a2714f4f8169aa8de717462a735f603d650d696`, `data/m0_features.parquet` `49e28025ca8bbddf376613ed72382536ef569e94ebef1dfc154789c63b0632a6`, `data/m0_predictions.parquet` `ba6f75f41c3fbd0e858c7bb6dbe7f3e6facbabc7d1594a408f5564a5f3e5e5ea`.
- Protocol hash `6230a7a8a31d8b202e5454c49cf7823b77f95d8452a7d27e273ce9a89fcb32fe`; model `m0_lightgbm_v1`; bootstrap 1,000 resamples, seed 20261001; label-noise ceiling 1,000 draws, seed 20261002. Pilot archive `evidence/pilot/final-1131f10/`.

**Size scaling (D-031), the owner's reading.** Spearman of `d_upper` against `true_ler` within each template, from `m0_results.json` (rows with intervals in `m0_results.txt`):
- **Clear:** pair_2_2 (−0.92), quad_4_2 (−0.67), bb288_3_3 (−0.79), sym_3_3 (−0.79), rare_2_3 (−1.00, 2 codes), rare_3_4 (−1.00, 3 codes).
- **Weak:** diag_3_3 (−0.56), mod_2_3 (−0.52), sq_4_2 (−0.20).
- **Fails:** tri_3_3 (+0.32); mixed_3_5 (0.00), which is above threshold at `P_PILOT`, as the calibration predicted.

The failing templates are reported here, not dropped. They are in every metric above.

| Criterion (`spec/plan.md` M0) | Verdict | Evidence |
|---|---|---|
| `pytest` passes, including every invariant test in §3 | PASS | The full suite (`-m "slow or not slow"`) is green on every leg of CI run 37092886336 on `345c174`. That commit carries every source and test file this verdict rests on; this commit changes neither. The default suite also passes locally for this commit, and CI for the pushed SHA is in `AGENT_LOG.md` |
| BB generator reproduces `n=72, k=12, d_upper=6` for the reference parameters | PASS | `tests/test_bb_reference.py` (n, k, weights) and `tests/test_distance.py::test_reference_code_hits_published_distance` (`d_upper == 6`), in the same CI run |
| Measured per-shot decode cost recorded, `spec/architecture.md §6` updated | PASS | Already ticked: M0-EVAL-05, the Kaggle calibration (§7 above) |
| One row for each of 242 of 244 codes (D-036), each with shots, failures, Wilson interval and `protocol_hash` | PASS | `data/m0_measurements.parquet` (sha256 above): 242 rows, 242 distinct `code_id`, one `protocol_hash`, no null in `shots`, `failures`, `true_ler_ci_low`, `true_ler_ci_high` or `protocol_hash`. The two excluded ids are recorded in its schema metadata (D-036) |
| Censoring rate reported; re-run if > 40% | PASS | 1 of 242 censored, 0.4% (`bb_v1_pair_2_2-4faad046f1a9`, 93 failures in 40,960 shots); `m0_results.json` `n_censored` 1, `censoring_rate` 0.00413 |
| Results table: Recall@30 and Spearman, Φ vs LightGBM, construction-program-grouped split, bootstrap CIs | PASS | `m0_results.txt` / `.json`, leave-one-program-out over 11 programs (M0 has one family, so there is no family holdout; the note is in the files) |
| Verdict, proceed or kill, recorded here with evidence per criterion | PASS | This entry |
| Write-up published within 7 days of the verdict (INV-10) | PASS | https://github.com/Pushkar0997/qecscreen/blob/main/docs/m0-writeup.md, published 2026-10-03 in commit `8d19b89588427f4503d5ef45b3c075447c2ba67d`, the same day as the verdict (INV-10, `spec/smoke.md §6`) |

**Closes?** **Yes, M0 closed** (2026-10-03). Every criterion in this table is PASS, and the write-up's URL is in the last row (M0-RUN-06). The verdict above is unchanged: PROCEED, headline criterion FAIL. Starting M1 is the owner's call.

**Caveats carried forward:**
- **242 of 244 codes (D-036).** Two mixed_3_5 codes cannot be built under the pinned schedule and are in no metric.
- **1 censored code (0.4%).** It is the #2 code by ranking value (its `true_ler_ub`, D-035), which is why the model's recall drops from 0.200 to 0.100 with it excluded.
- **The bootstrap resamples codes with the out-of-fold predictions fixed.** It measures sampling variance over codes, not the variance of refitting the model. With one fold deciding the top 10, refit variance is likely the larger of the two, and it is not measured.
- **`d_upper` is an upper bound**, so Φ is `phi_from_d_upper` (INV-5).
- **Scope:** BB only, n ≤ 72, p = 0.002, Z-basis memory, the pinned BP+OSD and schedule. The verdict is a claim about this population only. Larger n, other families and other p are M1's questions.

**The question this section was set to answer** (written before the run):

The M0 verdict must answer one question explicitly, in a sentence, at the top:

> Does a LightGBM model on cheap structural features beat Φ at Recall@30-of-top-10 on a construction-program-grouped split, by a margin that survives bootstrap resampling?

A **no** here is a valid, publishable, project-closing answer, and recording it honestly is worth more than five months of building on a false premise. See `spec/product.md §7`.

**Required diagnostic (D-031): size scaling in the pilot's own labels.** For each template, report whether its codes with larger `d_upper` have lower LER at `P_PILOT` in the pilot's labels. That means the M0 rows, not the calibration. Give the evidence: the template's non-censored rows ordered by `d_upper`, with their `true_ler` and 95% intervals, and the reading. Censored rows count as upper bounds (INV-3), never as point estimates.
- **Templates that fail it are reported, not dropped.** They stay in the population and in every metric, and the verdict names them. The exception is the two codes D-036 excludes as unbuildable: the metrics are over 242 of 244 codes. mixed_3_5 is expected to fail: the calibration put it above threshold at 0.002.
- A template with fewer than two distinct `d_upper` values among its non-censored rows has no reading. Report that too, rather than a pass or a fail.
- This diagnostic is not an exit criterion, and it does not decide proceed or kill. It says how much of the ranking target is "which code is more sub-threshold", and the verdict must be read with it in view.
