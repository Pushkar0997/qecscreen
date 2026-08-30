# architecture.md — qecscreen

## 1. Stack

| Layer | Choice | Version | Why |
|---|---|---|---|
| Language | Python | 3.11 | Matches Kaggle and Colab defaults; every QEC library targets it. |
| Circuit simulation | `stim` | ≥1.14 | The field standard. Fast enough that decoding, not sampling, is the bottleneck. |
| Sampling orchestration | `sinter` | ≥1.14 | Ships with Stim, does parallel batched Monte Carlo with stopping rules. Saves writing a job runner. |
| Decoder | `ldpc` (Roffe) | ≥2.1 | `BpOsdDecoder` is the qLDPC baseline everyone reports against. Comparability matters more than speed here. |
| Arrays | `numpy` | ≥1.26,<3 | Upper bound because NumPy 3 will break dtype behaviour we rely on. |
| Tables / storage | `pandas` + `pyarrow` | ≥2.2 / ≥15 | Parquet is columnar, compresses well, and HuggingFace Datasets reads it natively. |
| Graphs | `networkx` | ≥3.2 | Tanner-graph features and edge colouring. Pure Python, installs anywhere. |
| Baseline model | `scikit-learn` + `lightgbm` | ≥1.4 / ≥4.3 | Gradient-boosted trees on ~20 features is the right M0 model. Trains in seconds on CPU. |
| Statistics | `scipy` | ≥1.12 | Spearman, Wilson intervals, bootstrap resampling. |
| GNN | `torch` + `torch-geometric` | pinned at M3 | Deliberately not pinned yet. Optional dependency, never imported by the data pipeline. |
| Tests | `pytest` | ≥8.0 | |
| Environment | `pip` + `requirements.txt` | — | Kaggle and Colab are pip environments; the project must install in one cell. |

Versions, not just names. Agents trained at different times generate different API shapes otherwise.

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
└── notebooks/             ← Kaggle/Colab runners. Thin: import and call, no logic.
```

The rule that matters: **logic never lives in a notebook or a script.** Notebooks die, are not tested, and cannot be reviewed in a diff. They import from `src/` and call one function.

## 3. Data model

One Parquet table. One row per `(code, protocol)` pair.

| Column | Type | Notes |
|---|---|---|
| `code_id` | str | `{program_id}-{sha256(params_json)[:12]}` |
| `construction_program_id` | str | `bb_v1`, `gb_v1`, … — **the grouping key for splits (INV-2)** |
| `family` | str | `BB`, `GB`, `HGP`, `TB` — the holdout key |
| `params_json` | str | Canonical JSON, sorted keys. With `seed`, regenerates the code (INV-7) |
| `seed` | int64 | Explicit, never implicit |
| `n`, `k` | int32 | `k` computed by GF(2) rank (INV-8) |
| `d_exact` | int32, nullable | Null unless provably exact (INV-5) |
| `d_upper` | int32 | Upper bound from decoder-assisted search |
| `phi_from_d_upper` | float64 | kd²/n. The incumbent baseline, stored so it is never recomputed differently |
| `n_ancilla`, `n_total` | int32 | Physical qubit budget |
| `protocol_hash` | str | SHA-256, see INV-6 |
| `p` | float64 | Physical error rate, 6dp |
| `rounds` | int32 | `r` |
| `shots`, `failures` | int64 | Raw counts, always stored |
| `true_ler` | float64, nullable | Null if censored (INV-3) |
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
| Stim circuit from a CSS code, edge-coloured schedule | M0 | |
| BP+OSD decoding via `ldpc` | M0 | |
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

Hard rule: if a projected run exceeds its milestone's stated budget, stop and report rather than starting it.

## 7. Security and privacy

Nothing stored about any person. No accounts, no telemetry, no analytics, no cookies, no network calls at import time (INV-9 test). Secrets: none exist. If a task appears to need an API key, that is a signal the design has gone wrong — stop and flag it.

Licence: MIT for source, CC-BY-4.0 for the dataset. Permissive deliberately, to keep adoption friction at zero and commercial optionality open.
