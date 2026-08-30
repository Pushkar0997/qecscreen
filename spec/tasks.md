# tasks.md — Backlog

One task = one change = one commit. Tick the box and add a one-line note when done.

Task ID format: `M<milestone>-<AREA>-<number>`. Commit format: `<type>(<scope>): <task-id> <summary>`.

Only M0 is decomposed. M1+ gets decomposed when M0 closes — decomposing further ahead produces fiction.

---

## M0 — Falsification

### SETUP

- [x] **M0-SETUP-01** Create `requirements.txt` with the pinned versions from `spec/architecture.md §1`; verify `pip install -r requirements.txt` succeeds in a clean Colab cell — verified in a clean local venv on 3.11.9 and 3.13.7, wheels only, no compiler; `stim`/`sinter`/`ldpc` upper-bounded because they enter `protocol_hash`. **Not** verified in an actual Colab cell — no network sandbox for it this session
- [ ] **M0-SETUP-02** Add `pytest.ini` and `.github/workflows/ci.yml` running `pytest` on push; confirm the badge is green
- [ ] **M0-SETUP-03** Add `.gitignore` excluding `data/`, `*.parquet`, `__pycache__`, `.ipynb_checkpoints`

### CORE — protocol and linear algebra

- [ ] **M0-CORE-01** Implement `src/qecscreen/protocol.py`: frozen constants from `CONTRACT.md`, `logical_error_rate`, `wilson_interval`, `protocol_hash`. No other module may compute an LER
- [ ] **M0-CORE-02** Write `tests/test_protocol.py` asserting the four LER golden values and two Wilson golden values from `CONTRACT.md` exactly
- [ ] **M0-CORE-03** Implement `src/qecscreen/linalg.py`: `gf2_rank`, `gf2_rref`, `gf2_nullspace`, all on `uint8`
- [ ] **M0-CORE-04** Write `tests/test_linalg.py` including a matrix whose GF(2) rank differs from its real rank, asserting we get the GF(2) answer

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
