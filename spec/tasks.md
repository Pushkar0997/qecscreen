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

### CORE — protocol and linear algebra

- [x] **M0-CORE-01** Implement `src/qecscreen/protocol.py`: frozen constants from `CONTRACT.md`, `logical_error_rate`, `wilson_interval`, `protocol_hash`. No other module may compute an LER — constants and both formulas verified against `CONTRACT.md` and independently recomputed at 50 digits; `protocol_hash()` added; `decoder_version` now required and read from the installed `ldpc`; `rounds` replaced by `rounds_rule` in the hash per D-014, which unblocks `M0-RUN-04`
- [x] **M0-CORE-02** Write `tests/test_protocol.py` asserting the four LER golden values and two Wilson golden values from `CONTRACT.md` exactly — all six literals verified byte-identical across `CONTRACT.md`, `spec/evals.md` and the test, and independently recomputed at 50-digit precision; `math.isclose(rel_tol=1e-12)` per CONTRACT, which outranks the word "exactly" here
- [x] **M0-CORE-03** Implement `src/qecscreen/linalg.py`: `gf2_rank`, `gf2_rref`, `gf2_nullspace`, all on `uint8` — `gf2_rank`/`gf2_rref` verified against an independent implementation over 400 random matrices; `gf2_nullspace` added, returning a basis as rows (`gf2_nullspace_dim` kept). `_as_gf2` now rejects float and bool *before* casting, so `[[0.5, 0.0]]` raises instead of truncating to rank 0
- [x] **M0-CORE-04** Write `tests/test_linalg.py` including a matrix whose GF(2) rank differs from its real rank, asserting we get the GF(2) answer — `test_n06_gf2_rank_differs_from_real_rank` is exactly N-06: real rank 3, GF(2) rank 2, and it asserts the float answer is 3 so the test itself would fail if the premise ever stopped holding
- [ ] **M0-CORE-05** Implement `src/qecscreen/provenance.py`: `resolved_commit()` reading `direct_url.json` from the installed distribution via `importlib.metadata`, returning the exact VCS commit_id, or `None` for an editable/local install. `CONTRACT.md` (D-017) already requires every row to carry `commit_sha` sourced from this function, so no measurement row can be written until it lands.
- [ ] **M0-CORE-06** Write `tests/test_provenance.py` covering both branches with a fake distribution. Do not skip the `None` case.

### CODES — BB generator

- [ ] **M0-CODES-01** Implement `src/qecscreen/codes/bb.py`: `generate(l, m, a_exps, b_exps, seed)` returning `H_X`, `H_Z` per Bravyi et al. 2024
- [ ] **M0-CODES-02** Write `tests/test_bb_reference.py` asserting the `l=6, m=6, A=x^3+y+y^2, B=y^3+x+x^2` code gives `n=72`, `k=12`, all check weights 6
- [ ] **M0-CODES-03** Implement `validate(code)` enforcing INV-8: commutation and GF(2) rank; raise on failure, never warn
- [ ] **M0-CODES-04** Implement `d_upper` estimation by decoder-assisted random search; return `(d_upper, method_name)`, never populate `d_exact`
- [ ] **M0-CODES-05** Implement `sample_bb_params(n_codes, budget, seed)` producing a diverse candidate set across ≥8 distinct polynomial templates; record `construction_program_id` per template

### CIRCUITS

- [ ] **M0-CIRC-01** Implement Tanner-graph edge colouring in `src/qecscreen/circuits/schedule.py` using `networkx` line-graph colouring; return CNOT layers
- [ ] **M0-CIRC-02** Implement `build_memory_circuit(code, p, rounds)` in `src/qecscreen/circuits/build.py` emitting a Stim circuit with the exact `uniform_depolarizing_v1` noise from `CONTRACT.md`
- [ ] **M0-CIRC-03** Write `tests/test_circuit_sanity.py`: at `p=0`, the circuit produces zero detection events over 1,000 shots; detector and observable counts match expectations

### EVAL — sampling and labels

- [ ] **M0-EVAL-01** Implement `src/qecscreen/evaluate/run.py`: batched sample-and-decode with BP+OSD, stopping at `MIN_FAILURES` or `MAX_SHOTS`
- [ ] **M0-EVAL-02** Implement the censoring rule (INV-3) and Wilson interval population; write `tests/test_inv_3_censoring.py`
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
