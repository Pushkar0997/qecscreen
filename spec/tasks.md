# tasks.md — Backlog

One task = one change = one commit. Tick the box and add a one-line note when done.

Task ID format: `M<milestone>-<AREA>-<number>`. Commit format: `<type>(<scope>): <task-id> <summary>`.

Only M0 is decomposed. M1+ gets decomposed when M0 closes — decomposing further ahead produces fiction.

---

## M0 — Falsification

### SETUP

- [x] **M0-SETUP-01** Create `requirements.txt` with the pinned versions from `spec/architecture.md §1`; verify `pip install -r requirements.txt` succeeds in a clean Colab cell — **CLOSED, see `spec/evals.md §7`.** Every criterion in the §7 table is PASS: local venvs on 3.11.9/3.13.7, Colab and Kaggle both install clean with no manual fixes and no C toolchain invoked, `sinter`/`stim`/`ldpc`/`pymatching` resolve identically on both platforms (INV-6), and CI is GREEN on `cf1a1f3` (3/3, including the new 3.12 leg from D-020). The no-downgrade criterion — FAIL on both platforms earlier 2026-09-14 under the old `pyarrow<19` pin — re-measured PASS on a fresh factory-reset runtime against the new `pyarrow>=15` pin (D-019): zero uninstalls on either platform. `spec/evals.md §7` carries a standing note that this criterion is not permanently settled and should be re-checked before M1 bulk generation
- [x] **M0-SETUP-02** Add `pytest.ini` and `.github/workflows/ci.yml` running `pytest` on push; confirm the badge is green — `pytest.ini` already present; `ci.yml` added, YAML-validated, matrix on 3.11 + 3.13 because they resolve different `sinter` versions, install runs normally and fails the step if a C toolchain was actually invoked (compiler grep on the pip log, `cf5542e`; D-018) rather than being forced to `--only-binary=:all:`. Badge added to README but **green not yet confirmed** — needs a push, which is the owner's call
- [x] **M0-SETUP-03** Add `.gitignore` excluding `data/`, `*.parquet`, `__pycache__`, `.ipynb_checkpoints` — written as `data/*` plus `!data/LICENSE` so the CC-BY-4.0 dataset licence stays committable at M1; verified by creating and removing test files. `venv/` and `.pytest_cache/` deliberately omitted, they self-ignore
- [x] **M0-SETUP-04** Add `pyproject.toml` so Kaggle/Colab can `pip install git+https://github.com/Pushkar0997/qecscreen@<sha>` (D-028): src-layout, runtime dependencies read from `requirements.txt`, no new dependency. Verify with a clean-venv install from a local git URL — setuptools backend (build-time only), version from `qecscreen.__version__`. Fresh 3.13.7 venv, `pip install git+file:///D:/Coding_Work/qecscreen/qecscreen@a85b676…`: exit 0, all 11 requirements plus transitive resolved, `pip check` clean, `qecscreen` imported from site-packages, `provenance.record()` gave `commit_sha` = `a85b676936f0f51355b6a18f9466b4ddbde18681`, `x86_64/sse2`, stim 1.16.0, ldpc 2.4.1; `python -m qecscreen.selfcheck` passed
- [x] **M0-SETUP-05** `notebooks/template_run.ipynb` (six cells: install pinned by SHA with the token from Kaggle/Colab secrets, provenance, config, output path, one package call, artifact + summary) and `tests/test_notebook_contract.py` (no function/class/lambda in any code cell, no GitHub token in any notebook, template shape). Notebook rules in `spec/architecture.md §2` (D-028) — `verify_env_colab.ipynb`'s path-search cell flattened to comply, same search order; `notebooks/runs/` evidence exempt from the no-definition rule only

### CORE — protocol and linear algebra

- [x] **M0-CORE-01** Implement `src/qecscreen/protocol.py`: frozen constants from `CONTRACT.md`, `logical_error_rate`, `wilson_interval`, `protocol_hash`. No other module may compute an LER — constants and both formulas verified against `CONTRACT.md` and independently recomputed at 50 digits; `protocol_hash()` added; `decoder_version` now required and read from the installed `ldpc`; `rounds` replaced by `rounds_rule` in the hash per D-014, which unblocks `M0-RUN-04`
- [x] **M0-CORE-02** Write `tests/test_protocol.py` asserting the four LER golden values and two Wilson golden values from `CONTRACT.md` exactly — all six literals verified byte-identical across `CONTRACT.md`, `spec/evals.md` and the test, and independently recomputed at 50-digit precision; `math.isclose(rel_tol=1e-12)` per CONTRACT, which outranks the word "exactly" here
- [x] **M0-CORE-03** Implement `src/qecscreen/linalg.py`: `gf2_rank`, `gf2_rref`, `gf2_nullspace`, all on `uint8` — `gf2_rank`/`gf2_rref` verified against an independent implementation over 400 random matrices; `gf2_nullspace` added, returning a basis as rows (`gf2_nullspace_dim` kept). `_as_gf2` now rejects float and bool *before* casting, so `[[0.5, 0.0]]` raises instead of truncating to rank 0
- [x] **M0-CORE-04** Write `tests/test_linalg.py` including a matrix whose GF(2) rank differs from its real rank, asserting we get the GF(2) answer — `test_n06_gf2_rank_differs_from_real_rank` is exactly N-06: real rank 3, GF(2) rank 2, and it asserts the float answer is 3 so the test itself would fail if the premise ever stopped holding
- [x] **M0-CORE-05** Implement `src/qecscreen/provenance.py`: `resolved_commit()` reading `direct_url.json` from the installed distribution via `importlib.metadata`, returning the exact VCS commit_id, or `None` for an editable/local install. `CONTRACT.md` (D-017) already requires every row to carry `commit_sha` sourced from this function, so no measurement row can be written until it lands — `None` also for archive, index and not-installed; raises `ValueError` on a malformed file or a commit id that is not bare 40/64 hex, without echoing it. Also `stim_version()`, `cpu_class()` (`<machine>/<stim backend>`, D-027) and `record()`, the whole provenance dict an artifact carries (D-028: no URL, no env var)
- [x] **M0-CORE-06** Write `tests/test_provenance.py` covering both branches with a fake distribution. Do not skip the `None` case. — fake `qecscreen-0.0.1.dist-info` on `sys.path`, found by `importlib.metadata` normally. VCS (incl. a branch ref resolving to a commit, SHA-256 ids), editable, local dir, archive, index, not installed, 8 malformed cases, and the D-028 credential tests. 4 of 4 mutants caught

### CODES — BB generator

- [x] **M0-CODES-01** Implement `src/qecscreen/codes/bb.py`: `generate(l, m, a_exps, b_exps, seed)` returning `H_X`, `H_Z` per Bravyi et al. 2024 — `H_X = [A|B]`, `H_Z = [B^T|A^T]` where `A`/`B` are GF(2) sums of monomial permutation matrices over the commuting shifts of `Z_l x Z_m`; `seed` accepted for interface consistency with M0-CODES-05 but unused by this deterministic construction
- [x] **M0-CODES-02** Write `tests/test_bb_reference.py` asserting the `l=6, m=6, A=x^3+y+y^2, B=y^3+x+x^2` code gives `n=72`, `k=12`, all check weights 6 (G-07..G-10, distance excluded — that's M0-CODES-04) — passed on the first run against the published reference values, no expected value adjusted, no tolerance added. Also asserts CSS commutation, `(l*m, 2*l*m)` shape, and determinism (same args + seed → byte-identical `H_X`/`H_Z`). `k` computed via `qecscreen.linalg.logical_qubit_count`, never `numpy.linalg.matrix_rank`. **Strengthened** with the `l=12, m=6` [[144,12,12]] gross code (same `A`/`B`; G-11..G-13, `spec/evals.md`) — at `l=m=6` only `k` discriminates a correct generator from a broken one, and even that is weak because `x`/`y` are interchangeable there; `l != m` closes that gap. Passed unmodified on the first run: `n=144`, `k=12`, all weights 6
- [x] **M0-CODES-03** Implement `validate(h_x, h_z)` enforcing INV-8 in `src/qecscreen/codes/validate.py` (own module, not `codes/__init__.py` — it applies to any construction program's output, not just one, and isn't package re-export surface): dtype/value check, column-count match, CSS commutation, GF(2)-rank `k`, `k >= 1`, all delegated to `qecscreen.linalg` (no new GF(2) arithmetic). Raises `InvalidCodeError` (a `ValueError` subclass) on every failure, returns `(n, k)`. Never warns, never returns a bool
- [x] **M0-CODES-04** Implement `estimate_d_upper(h_x, h_z, seed, attempts)` in `src/qecscreen/codes/distance.py`: random-information-set search over the logical-operator space (`gf2_nullspace`), returns `(d_upper, method_name)`, `method_name="random_information_set_v1"`. An earlier greedy-descent method failed the gross-code reference check (14, not 12) even at 5,000 attempts — replaced, not tuned around; see D-021. `DEFAULT_ATTEMPTS=64`, measured at 16x the reliability threshold found by sweeping 30 seeds (D-021). Never populates or names the exact-distance column
- [x] **M0-CODES-05** Implement `sample_bb_params(n_codes, budget, seed)` in `src/qecscreen/codes/sample.py`: 10 polynomial templates, each `construction_program_id = f"bb_v1_{template_name}"` (D-022 — one per template, not per family). Every emitted code passes `qecscreen.codes.validate.validate` (reject-and-redraw on `k < 1`); `n = 2lm` capped at `budget`; deterministic (one seeded `numpy.random.Generator`, redraws just continue the same stream). Three candidate shapes were found to fail `validate()` for every `(l, m)` tested and were replaced, not shipped and hoped past — see D-022. **Follow-up (D-023):** `balanced=True` (now the default) splits `n_codes` evenly across templates with distinct `(l, m)` per template, redistributing any shortfall (visible via `BBSample.counts`/`exhausted`) — uniform template draws had put 263/300 codes in four templates; `balanced=False` keeps the original sampler exactly. **Correction (D-024):** `quad_2_4`/`mixed_5_3` were A/B swaps of `quad_4_2`/`mixed_3_5` (same program, two ids — INV-2 leak) and `quad_4_4` had `A == B` (d <= 2 for every code); all three removed, four added (`bb288_3_3`, `tri_3_3`, `diag_3_3`, `sq_4_2`; 11 total), `template_key` enforces uniqueness under A/B swap and monomial shift, and every emitted code must have `estimate_d_upper >= 3`. Template tests now compare generated codes, not ids

### CIRCUITS

- [x] **M0-CIRC-01** Implement the `bb_monomial_matching_xz_phased_v1` schedule (renamed `_v2` by the D-025 amendment, ancilla timing) in `src/qecscreen/circuits/schedule.py`: one CNOT layer per monomial of `A`/`B` (each a perfect matching), X phase then Z phase; return CNOT layers. Supersedes the original "networkx line-graph colouring" wording (D-025) — `bb_schedule()` returns `Schedule(x_layers, z_layers, method)`; 6+6 layers for the reference code, every layer a perfect matching, layers rebuilt edge-for-edge into `H_X`/`H_Z` or it raises
- [x] **M0-CIRC-02** Implement `build_memory_circuit(code, p, rounds)` in `src/qecscreen/circuits/build.py` emitting a Stim circuit with the exact `uniform_depolarizing_v1` noise from `CONTRACT.md` — Z memory, D-025 placement; `code` is a BB params mapping (`l`, `m`, `a_exps`, `b_exps`); observables from `z_logical_basis()`, deterministic
- [x] **M0-CIRC-03** Write `tests/test_circuit_sanity.py`: at `p=0`, the circuit produces zero detection events over 1,000 shots; detector and observable counts match expectations — written first; 19 tests incl. DEM build, sensitivity (N-10), per-tick noise placement and channel counts; 8 of 8 breaking builder mutants fail it (a benign within-phase reorder passes, as it should)

### EVAL — sampling and labels

- [x] **M0-EVAL-01** Implement `src/qecscreen/evaluate/run.py`: batched sample-and-decode with BP+OSD, stopping at `MIN_FAILURES` or `MAX_SHOTS` — **done on the seeded loop (D-026).** `sample_and_decode(circuit, *, seed, batch_size=SHOT_BATCH, max_shots=MAX_SHOTS)` uses one `compile_detector_sampler(seed=seed)` per code, fixed-size batches, and checks the stopping rule between batches. It returns a `RunResult` with shots, failures, `stopped_by`, OSD invocations, a sha256 of every sampled byte, and decode time. `CompiledBpOsd` is ldpc's `BpOsdDecoder` over CONTRACT's `dem_undecomposed_merge_by_symptom_v1` with exactly `DECODER_PARAMS` (now including `schedule`). `count_failures` implements INV-4 "any observable". sinter is off the label path: `BpOsdSinterDecoder` and `DECODER_KEY` were removed. Tests: determinism (same code, p, seed → identical shots and failures; a different seed → different shots), stop at `MIN_FAILURES` at the first batch boundary, stop at `max_shots` → censored, p=0 at CONTRACT defaults (200,000 shots, 0 failures), beats-trivial, monotonic in p through the loop. Parallelism across codes (one per process) is the caller's, in M0-RUN-01
- [x] **M0-EVAL-02** Implement the censoring rule (INV-3) and Wilson interval population; write `tests/test_inv_3_censoring.py` — `evaluate/label.py`: `make_label()` returns a `Label` of the schema's measurement columns. Wilson is taken on per-shot `P_L` and mapped through `logical_error_rate` (monotone), so `true_ler_ci_low/high` are in per-round per-qubit units and are populated on every row; `true_ler_ub == true_ler_ci_high`. Everything goes through `protocol.py`. The one local step is clamping the ~-1e-18 float residue that `wilson_interval(0, n)` returns for some `n` (17,314 values of `n` <= 200k), which `logical_error_rate` would otherwise reject
- [ ] **M0-EVAL-03** Implement `protocol_hash` computation and `assert_single_protocol()`; write `tests/test_inv_6_protocol.py`
- [ ] **M0-EVAL-04** Add resume-from-disk: write a Parquet shard per batch of codes, skip `code_id`s already present on restart
- [ ] **M0-EVAL-05** Measure real per-shot decode cost on 5 representative codes; **update `spec/architecture.md §6` in the same commit**

### FEATURES

- [ ] **M0-FEAT-01** Implement `src/qecscreen/features/structural.py`: `n`, `k`, `d_upper`, `phi_from_d_upper`, check-weight min/max/mean, qubit-degree min/max/mean, `n_ancilla`, `n_total`
- [ ] **M0-FEAT-02** Add Tanner-graph cycle features: 4-cycle count, 6-cycle count, girth. **This is the physically motivated hypothesis** — BP struggles with short cycles, so this is where signal Φ misses should live
- [ ] **M0-FEAT-03** Add circuit features from the schedule: colouring number, CNOT depth, two-qubit gate count
- [ ] **M0-FEAT-04** Add spectral feature: second-smallest Laplacian eigenvalue of the Tanner graph
- [ ] **M0-FEAT-05** Assert every feature computes in <1s per code; fail the test if not

### SPLIT and METRICS

- [ ] **M0-SPLIT-01** Implement `src/qecscreen/splits.py` with `grouped_kfold(df, n_splits)` grouping on `construction_program_id`; no other split function is exported
- [ ] **M0-SPLIT-02** Write `tests/test_inv_2_leakage.py` asserting empty program-ID intersection across every split produced
- [ ] **M0-METRIC-01** Implement `recall_at_k(true_ler, score, k, top_n=10)` and `spearman(true_ler, score)` in `metrics.py`
- [ ] **M0-METRIC-02** Implement bootstrap confidence intervals over codes for both metrics, 1,000 resamples, seeded

### RUN and RESULT

- [ ] **M0-RUN-01** Write `scripts/run_m0_pilot.py` end to end: sample params → generate → validate → build → evaluate → save shards
- [ ] **M0-RUN-02** Write `notebooks/m0_kaggle.ipynb` — imports and calls only, no logic
- [ ] **M0-RUN-03** Execute the pilot; generate ≥250 rows; record censoring rate
- [ ] **M0-RUN-04** Train LightGBM on grouped splits; produce the Φ-vs-model table with bootstrap CIs
- [ ] **M0-RUN-05** Record the M0 verdict in `spec/evals.md §7` with evidence per exit criterion. **Do not round up a PARTIAL**
- [ ] **M0-RUN-06** Write and publish the M0 write-up within 7 days of the verdict (INV-10)

---

## Backlog — unscheduled, do not start

- GB, HGP, TB code families — M1
- Multiple `p` values per code — M1
- Zenodo and HuggingFace release tooling — M1
- Frozen benchmark splits and the `benchmark` CLI — M2
- GNN over Tanner graphs, torch dependency — M3
- SI1000 and biased noise models — would change `protocol_hash`, needs full regeneration, deferred indefinitely
- BP+LSD as an alternative decoder — only if M0-EVAL-05 shows BP+OSD is too slow
- Exact distance computation — likely never; see the capability register
- Logical operations beyond memory experiments — out of scope
