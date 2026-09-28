# architecture.md — qecscreen

## 1. Stack

| Layer | Choice | Version | Why |
|---|---|---|---|
| Language | Python | 3.11, 3.12 **and** 3.13 | Kaggle runs 3.12 (measured 3.12.13, D-020) and Colab runs 3.13 (measured 3.13.15); 3.11 is kept as the stack's lower-bound target. CI tests all three; code that works on only some is broken. |
| Circuit simulation | `stim` | ≥1.14,<2 | The field standard. Fast enough that decoding, not sampling, is the bottleneck. Upper-bounded because its version decides which bits a seeded sampler produces; the version is a per-row `stim_version` column, **not** a `protocol_hash` input (D-027). |
| (transitive) | `sinter` | ≥1.14,<2 | **Not on the label path (D-026), and its version never entered `protocol_hash`.** Sampling is our own seeded stim loop in `evaluate/run.py`. Installed only because `ldpc` depends on it (and imports it at import time). |
| Decoder | `ldpc` (Roffe) | ≥2.1,<3 | `BpOsdDecoder` is the qLDPC baseline everyone reports against. Comparability matters more than speed here. Upper-bounded: the version enters `protocol_hash`. |
| Arrays | `numpy` | ≥1.26,<3 | Upper bound because NumPy 3 will break dtype behaviour we rely on. |
| Tables / storage | `pandas` + `pyarrow` | ≥2.2,<3 / ≥15 | Parquet is columnar, compresses well, and HuggingFace Datasets reads it natively. `pandas` upper-bounded so the dev box is never newer than the machine that runs the generation (D-015). `pyarrow` has no upper bound (D-019, supersedes the `pyarrow` half of D-015): the `<19` cap tracked Colab's 2026-08-30 ambient version and was forcing a downgrade on both platforms by 2026-09-14. |
| Graphs | `networkx` | ≥3.2 | Tanner-graph features and edge colouring. Pure Python, installs anywhere. |
| Baseline model | `scikit-learn` + `lightgbm` | ≥1.4 / ≥4.3 | Gradient-boosted trees on ~20 features is the right M0 model. Trains in seconds on CPU. |
| Statistics | `scipy` | ≥1.12 | Spearman, Wilson intervals, bootstrap resampling. |
| GNN | `torch` + `torch-geometric` | pinned at M3 | Deliberately not pinned yet. Optional dependency, never imported by the data pipeline. |
| Tests | `pytest` | ≥8.0 | |
| Environment | `pip` + `requirements.txt` | — | Kaggle and Colab are pip environments; the project must install in one cell. |

Versions, not just names. Agents trained at different times generate different API shapes otherwise.

Upper bounds are added for two distinct reasons, and only for those two.

**Label-determining libraries** — `stim` and `ldpc` — are bounded because a major release could change decoding or sampling behaviour and silently invalidate every label already generated; the bound makes that fail at install time instead. `ldpc`'s version is a `protocol_hash` input (INV-6). `stim`'s is a per-row provenance column, not a hash input (D-027): it changes which bits are sampled, not the distribution. `sinter`'s version was never a hash input; an earlier version of this paragraph said otherwise.

**Data-path libraries newer here than in production** — `pandas` — is bounded to what the execution environments actually ship, so the dev box is never ahead of the machine doing the generation (D-015). `pyarrow` was bounded the same way but the cap is removed (D-019): both target platforms' ambient `pyarrow` moved past `<19` within three weeks, so a snapshot-of-a-base-image cap does not hold long enough to be worth the downgrade it forces. Everything else keeps lower bounds only, because Kaggle and Colab ship their own numpy/scipy/scikit-learn and a tighter pin would force a downgrade of a preinstalled stack, breaking the one-cell install.

**Three supported interpreters, because Kaggle's actual version was measured and it was not the one this section assumed (D-020).** Colab runs Python 3.13 and Kaggle runs 3.12 — measured 2026-09-14 at 3.13.15 and 3.12.13 respectively — and both will run this code, Kaggle for bulk generation, Colab for interactive work. 3.11 is kept as the stack's lower-bound target. CI tests all three. None of the three is "the" version; a change that works on only some is broken.

An earlier version of this section, and of `.github/workflows/ci.yml`, stated Kaggle runs 3.11. That was never measured — it was assumed by symmetry with the lower stack bound — and D-020 corrects it once Kaggle was actually run.

**Verified at M0-SETUP-01** — no compiler invoked, `pytest` green:

| Interpreter | Where | Resolves to |
|---|---|---|
| 3.11.9 | dev box, clean venv (stack's lower-bound target; neither platform actually runs this) | `stim` 1.16.0, `sinter` 1.16.0, `ldpc` 2.4.1 |
| 3.12.13 | Kaggle's actual version — measured live on Kaggle 2026-09-14, not a local dev venv | `stim` 1.16.0, `sinter` 1.16.0, `ldpc` 2.4.1, `pymatching` 2.4.0 |
| 3.13.7 | dev box, clean venv; Colab runs 3.13.15 | `stim` 1.16.0, `sinter` 1.16.0, `ldpc` 2.4.1 |

**On `sinter` 1.15 vs 1.16 — this is wheel availability, not interpreter version.** `sinter` 1.16.0 is **sdist-only** on PyPI; there is no wheel for any Python version. A plain `pip install` builds it from that sdist — it is pure Python, so no compiler is involved — and yields 1.16.0 on 3.11, 3.12 and 3.13 alike. Only a *wheels-only* install (`--only-binary=:all:`) falls back to `sinter` 1.15.0, and it does so on every interpreter. An earlier version of this section claimed 1.16.0 required Python ≥3.12; that was an artifact of measuring with `--only-binary=:all:` and is wrong. See AGENT_LOG (n).

Since D-026, `sinter` does not run the sampling loop; our seeded stim loop does. The `ldpc` version enters `protocol_hash` (INV-6). The `stim` version does not, although seeded shots are only bit-identical on the same stim version and CPU class (D-026). Both are stored per row instead, as `stim_version` and `cpu_class` (D-027).

`sinter` pulls `matplotlib`, and `ldpc` pulls `pymatching`. Neither is imported by this project; both are transitive and unpinned.

## 2. Structure

```
qecscreen/
├── src/qecscreen/
│   ├── protocol.py        ← Frozen constants + the LER formula + Wilson intervals.
│   │                        Nothing else may compute an LER. Changes need human approval.
│   ├── linalg.py          ← GF(2) linear algebra only. Exists so nobody reaches for
│   │                        numpy.linalg.matrix_rank, which is wrong here (INV-8).
│   ├── codes/             ← One module per construction program: bb.py, gb.py, hgp.py.
│   │                        Each exposes generate(params, seed) -> Code and a
│   │                        PROGRAM_ID constant. Adding a family = adding one file.
│   ├── circuits/          ← Code -> Stim circuit. Scheduling lives here.
│   ├── evaluate/          ← Sampling + decoding + censoring. The only place that
│   │                        produces true_* columns.
│   ├── features/          ← Cheap structural features. Must run in <1s per code,
│   │                        because the whole pitch is that screening is cheap.
│   ├── models/            ← baseline.py (LightGBM). gnn/ added at M3 and torch-only.
│   ├── splits.py          ← Grouped splitters. The ONLY sanctioned way to split (INV-2).
│   └── metrics.py         ← Recall@k, Spearman, bootstrap CIs.
├── scripts/               ← Runnable entry points. Every one is resumable from disk,
│                            because Kaggle sessions die at 12 hours.
├── tests/                 ← Mirrors src/. Invariant tests named test_inv_<n>_*.
├── data/                  ← Gitignored. Local Parquet. Releases go to Zenodo.
├── evidence/              ← Committed run outputs that are not dataset rows, e.g.
│                            calibration/<date>-<sha>/ (D-029). Kept unmodified,
│                            markers intact; refused by reject_calibration.
└── notebooks/             ← Kaggle/Colab runners. Thin: import and call, no logic.
                             template_run.ipynb is the six-cell shape (rules below).
                             calibrate.ipynb runs the decoder calibration (D-029).
```

The rule that matters: **logic never lives in a notebook or a script.** Notebooks die, are not tested, and cannot be reviewed in a diff. They import from `src/` and call one function.

### Notebook rules (D-028)

All sampling and decoding runs on Kaggle or Colab, in notebooks the owner runs. **Agents never execute notebooks**: they write and test the package, and the template that calls it.

1. **No definitions.** No code cell defines a function, a class or a lambda. Enforced by `tests/test_notebook_contract.py`, which parses every code cell (IPython `!`/`%` line magics blanked, cell magics refused) and runs in CI. Anything that needs a definition belongs in `src/qecscreen`, where it is tested.
2. **Six cells, in this order.** `notebooks/template_run.ipynb` is the shape every run notebook copies: (1) install pinned by SHA, (2) provenance, (3) config constants, (4) output path, (5) one package call, (6) write the artifact and print a summary. Only cells 3 and 5 change between runs.
3. **Install by a full 40-hex commit, never a branch or tag:** `pip install git+https://github.com/Pushkar0997/qecscreen@<sha>` (`pyproject.toml`; dependencies come from `requirements.txt`).
4. **Provenance is read back, not echoed.** Cell 2 calls `provenance.record()` (`commit_sha` from `resolved_commit()`, `stim_version`, `cpu_class`, `decoder_version`, `python_version`) and asserts `commit_sha` equals the pin (D-017). An artifact's provenance is that dict, whole.
5. **Credentials only from the platform's secret store.** The repo is public (D-030), so cell 1 needs no credential: it reads `GITHUB_TOKEN` from Kaggle Secrets or Colab `userdata` only if the secret exists, masks it in pip's output, and otherwise installs from the plain URL. A missing secret is not an error. A token never appears in a cell's source or output; the contract test scans every notebook for token-shaped strings.
6. **Constants are not retyped.** Protocol values come from `qecscreen.protocol`; cell 3 holds only run-level settings such as a run name.
7. **`notebooks/runs/` is evidence.** Executed copies are kept there, dated, and never edited, so rule 1 does not apply to them (rule 5's scan does).

## 3. Data model

One Parquet table. One row per `(code, protocol)` pair.

| Column | Type | Notes |
|---|---|---|
| `code_id` | str | `{program_id}-{sha256(params_json)[:12]}` |
| `construction_program_id` | str | `bb_v1_<template>`, `gb_v1_<template>`, … — one per polynomial template, not per family (D-022). **The grouping key for splits (INV-2)** |
| `family` | str | `BB`, `GB`, `HGP`, `TB` — the holdout key |
| `params_json` | str | Canonical JSON, sorted keys. With `seed`, regenerates the code (INV-7) |
| `seed` | int64 | Explicit, never implicit |
| `n`, `k` | int32 | `k` computed by GF(2) rank (INV-8) |
| `d_exact` | int32, nullable | Null unless provably exact (INV-5) |
| `d_upper` | int32 | Upper bound from decoder-assisted search |
| `phi_from_d_upper` | float64 | kd²/n. The incumbent baseline, stored so it is never recomputed differently |
| `n_ancilla`, `n_total` | int32 | Physical qubit budget |
| `protocol_hash` | str | SHA-256, see INV-6 |
| `commit_sha` | str | From `provenance.resolved_commit()`, never null (D-017). Not in the hash |
| `sampling_seed` | int64 | `protocol.sampling_seed(code_id, protocol_hash)` (D-027). Not the code's `seed` |
| `stim_version` | str | Installed stim. Provenance, not in the hash (D-027) |
| `cpu_class` | str | `<machine>/<stim SIMD backend>`, e.g. `x86_64/sse2`. Provenance, not in the hash (D-027) |
| `p` | float64 | Physical error rate, 6dp |
| `rounds` | int32 | `r` |
| `shots`, `failures` | int64 | Raw counts, always stored |
| `true_ler` | float64, nullable | Z-basis memory LER, per round per logical qubit (INV-4, D-025). Null if censored (INV-3) |
| `true_ler_ub` | float64 | Wilson upper bound; populated for every row including censored |
| `true_ler_ci_low`, `true_ler_ci_high` | float64 | |
| `censored` | bool | `failures < 100` |
| `decode_seconds` | float64 | Cost telemetry; needed for the compute arithmetic below |
| `schema_version` | int32 | |
| `created_at` | str | ISO 8601 UTC |

Feature columns live in a **separate** Parquet keyed on `code_id`, so features can be recomputed and versioned without touching measurements. Predictions live in a third. Three files, joined on `code_id`, is how INV-1 is enforced structurally rather than by discipline.

**Expensive to reverse:** the protocol definition and the LER normalisation. Changing either invalidates every label ever generated. Everything else is cheap.

## 4. Capability register

**Consult before building anything. Never build on an unsupported capability.**

| Capability | Status | Needed for / notes |
|---|---|---|
| Generate BB codes from `(l, m, A, B)` | M0 | The pilot family |
| GF(2) rank, `k` computation | M0 | |
| Distance upper bound via decoder-assisted search | M0 | Always `d_upper`, never `d_exact` |
| Stim circuit from a BB code, monomial-matching X-then-Z schedule, Z memory | M0 | D-025. Other families need a general schedule (M1) |
| BP+OSD decoding via `ldpc` | M0 | |
| Decoder calibration: BP+OSD vs BP+LSD on shared shots | M0 | `evaluate/calibrate.py` (D-029). Calibration output only, never labels: marked `"calibration": true`, refused by `evaluate.rows.reject_calibration` |
| Batched sampling with censoring rule | M0 | |
| ~20 cheap structural features incl. 4-cycle counts | M0 | The physically motivated hypothesis lives here |
| LightGBM ranking baseline | M0 | |
| Grouped / family-holdout splits | M0 | |
| Recall@k and Spearman with bootstrap CIs | M0 | |
| **Exact code distance** | **not supported** | Would need exhaustive search; exponential. May never be supported. Use `d_upper` and label it. |
| GB, HGP, TB families | **not supported** | M1 adds them. Do not assume they exist. |
| Multiple physical error rates per code | **not supported** | M1. M0 is single-p by design. |
| Zenodo / HuggingFace release | **not supported** | M1 |
| GNN over Tanner graphs | **not supported** | M3. Do not import torch before then. |
| Non-depolarizing noise (SI1000, biased, atom loss) | **not supported** | Backlog. Would change `protocol_hash` and require regeneration. |
| Logical operations beyond memory | **not supported** | Out of scope. Memory experiments only. |
| Real hardware execution | **not supported** | Permanently out of scope. |
| Any hosted service or API | **not supported** | Violates INV-9. Permanently out of scope. |

## 5. Scale assumptions

- Building for: ~2,000 labelled rows at M1, ~10,000 at most, ever.
- First thing to break as that grows: decode time, not storage. 10,000 rows of Parquet is ~50 MB.
- Revisit at: 20,000 rows, or when a single Parquet exceeds 500 MB.
- Deliberately not building: distributed job scheduling, a database, incremental online training. A directory of Parquet shards and a resume-from-disk script is correct at this scale, and anything more is over-engineering for a dataset that fits in RAM.

## 6. Compute budget — the arithmetic

CPU hours are the binding constraint. Written out so a change to any constant fails loudly.

Decoding dominates; sampling is negligible. Assume BP+OSD with `osd_order=10` on `n ≈ 100` costs **1–10 ms per shot**, call it 5 ms as the planning figure. This is an estimate, not a measurement.

**Replace it with a real number at M0-EVAL-05 — after the evaluation loop works and before the full 300-code run starts — and update this section in the same commit.** Every number below scales linearly with it, so the whole budget is provisional until that task closes.

Stopping rule: stop at 100 failures or 200,000 shots, whichever comes first.

| Regime | Per-shot failure prob | Shots to 100 failures | Time per code (1 core) |
|---|---|---|---|
| Near threshold, weak code | ~5% | ~2,000 | ~10 s |
| Typical pilot code at p=0.005 | ~0.5% | ~20,000 | ~100 s |
| Strong code | ~0.05% | 200,000 (capped) | ~17 min → **censored** |

**M0 budget:** 300 codes. Assume a mean of ~3 min/code including a tail of capped runs → ~15 core-hours → **~4 hours on Kaggle's 4 cores**. Fits comfortably in one 12-hour session with room to re-run.

**M1 budget:** ~2,000 rows across 3 families × 3 values of p. At the same mean → ~100 core-hours → **~25 Kaggle hours**, or roughly one week of the 30 h/week allowance. Acceptable. If the measured per-shot cost comes in at the 10 ms end, M1 doubles to two weeks and that is still acceptable — but if it comes in worse than 10 ms, **stop and reduce `osd_order` or switch to BP+LSD**, recording the protocol change as a new `protocol_hash`.

**Distance estimation (M0-CODES-04), measured, not estimated:** `estimate_d_upper` at its default `attempts=64` (D-021) takes ~0.10 s per call for the [[144,12,12]] gross code and ~0.05 s for the [[72,12,6]] reference code (20-seed average, dev box). This is a one-time cost per candidate code, not per shot, and is negligible next to the ~100 s/code decoding budget above — it does not move any number in this section. Recorded so it is a measurement rather than an unstated assumption.

Hard rule: if a projected run exceeds its milestone's stated budget, stop and report rather than starting it.

## 7. Security and privacy

Nothing stored about any person. No accounts, no telemetry, no analytics, no cookies, no network calls at import time (INV-9 test). The package needs no secret. **One may exist outside it:** a notebook's install cell uses a read-only GitHub token from Kaggle Secrets or Colab `userdata` as `GITHUB_TOKEN` if one is attached (D-028), and installs without it otherwise, since the repo is public (D-030). It never appears in a notebook's source or outputs, and no provenance value can carry it (`test_provenance.py`, `test_notebook_contract.py`). Any other task that appears to need an API key is a signal the design has gone wrong — stop and flag it.

Licence: Apache-2.0 for source (D-011), CC-BY-4.0 for the dataset. Permissive deliberately, to keep adoption friction at zero and commercial optionality open.
