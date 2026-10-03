# qecscreen

[![CI](https://github.com/Pushkar0997/qecscreen/actions/workflows/ci.yml/badge.svg)](https://github.com/Pushkar0997/qecscreen/actions/workflows/ci.yml)

## What this is

Searches for good quantum LDPC codes, including AI-driven ones, generate many
candidate codes and can afford circuit-level simulation for only a few. They
choose those few with a cheap score, usually Φ = kd²/n. qecscreen measures how
well such cheap scores find the codes that actually have the lowest
circuit-level logical error rate. It provides a set of **measured** labels (Stim
circuits decoded with BP+OSD, under one pinned and hashed protocol) and a
screening baseline (Φ and a LightGBM model on cheap structural features) scored
against those labels. It is for people who build or evaluate code-search loops,
and for anyone who wants circuit-level labels to test their own screening score
against.

## Status

**M0 closed on 2026-10-03.** Verdict: **PROCEED, with the headline criterion
FAILED** (`spec/evals.md §7`). The write-up is
[docs/m0-writeup.md](docs/m0-writeup.md). **M1 has not started.**

Everything below is about one population: 242 bivariate bicycle (BB) codes with
n ≤ 72, at physical error rate p = 0.002. Nothing here is a claim about other
code families, larger n, or other p.

## M0 results

The pre-registered question:

> Does a LightGBM model on cheap structural features beat Φ at
> Recall@30-of-top-10 on a construction-program-grouped split, by a margin that
> survives bootstrap resampling?

**No.** The model's margin over Φ at Recall@30-of-top-10 has a bootstrap
interval that includes zero. The kill condition (Φ's Spearman already high
*and* the model's advantage not surviving resampling) did not fire, so the
project proceeds, with the headline recorded as a fail.

Recall@30-of-top-10 is the share of the 10 codes with the lowest measured rate
that appear among a method's 30 highest-ranked codes. The split is
leave-one-program-out over the 11 construction programs (M0 has one family, so
there is no family holdout). Intervals are 95% percentile intervals from 1,000
bootstrap resamples of codes, paired over model and Φ (seed 20261001).

| 242 codes, leave-one-program-out | Model | Φ (from d_upper) | Model − Φ |
|---|---|---|---|
| Recall@30-of-top-10 | 0.200 [0.000, 0.600] | 0.000 [0.000, 0.000] | 0.200 [0.000, 0.600] |
| Recall, censored code excluded | 0.100 | 0.000 | — |
| Spearman with the measured ranking | 0.871 [0.838, 0.894] | 0.242 [0.118, 0.354] | 0.629 [0.521, 0.750] |
| Spearman, censored code excluded | 0.870 | 0.243 | — |
| Label-noise ceiling, Recall@30-of-top-10 | 1.000 [1.000, 1.000] | | |

The label-noise ceiling is the recall of the observed ranking against labels
redrawn from their own binomial noise: mean and [5th, 95th] percentile over
1,000 draws (seed 20261002). It is reported, not used for any decision. Source:
[`m0_results.txt`](evidence/m0-verdict/2026-10-03-1131f10/m0_results.txt).

**Why recall did not separate.** All ten of the best codes come from one
template, `pair_2_2`. Under leave-one-program-out, the single fold that holds
out `pair_2_2` produces every one of their predictions, so one fold decides the
headline metric, and every bootstrap resample reuses that fold's predictions.
That is why the interval runs from 0 to 0.6, and why the point estimate moves
from 0.200 to 0.100 when the one censored code (the second-best by its upper
bound) is dropped. It is not label noise: the ceiling is 1.000.

**Φ rewards k.** Every top-10 code has k = 2 and Φ ≤ 1.64. For each of them at
least 70 codes with both higher k and higher Φ rank above it in Φ's order.
Φ's Recall@30-of-top-10 is therefore exactly zero.

**Check weight alone reaches 0.719 (exploratory, post hoc).** After the verdict,
single-feature scores were ranked against the same truth: minus the mean check
weight has Spearman **0.719**, d_upper 0.310, and k −0.026 (point values, no
intervals; [write-up](docs/m0-writeup.md), not part of the verdict). Mean check
weight takes five distinct values here and varies mostly between templates, so
this may largely reflect template identity. It says nothing about the top 10.

**The cost asymmetry.** The codes a screen most needs to find are the most
expensive to measure. The ten best codes took 24,320 to 40,960 shots each
(40,960 is the cap, reached by the censored code), against a median of 1,024
over all 242. The whole pilot took 76.3 core-hours of decoding on free Kaggle
CPUs.

## The dataset

**Scope.** Every admissible BB code with n ≤ 72 and d_upper ≥ 3, enumerated
rather than sampled, from 11 polynomial templates: 244 codes. Two are excluded
(D-036): both are `mixed_3_5` codes with l = 2, where x³ = x makes a monomial of
B repeat and cancel over GF(2), so the pinned syndrome schedule cannot extract
their checks and refuses to build them. **242 of 244 codes have a row.** The
excluded ids and reasons are in the measurements file's Parquet schema metadata,
key `qecscreen.excluded_codes`.

**Protocol.** One protocol for every row, identified by `protocol_hash`
`6230a7a8a31d8b202e5454c49cf7823b77f95d8452a7d27e273ce9a89fcb32fe`
([CONTRACT.md, protocol v1](CONTRACT.md#exact-values--protocol-v1)):

- Noise: `uniform_depolarizing_v1` at **p = 0.002** (depolarizing idles,
  two-qubit depolarizing after every CX, reset and measurement errors at p;
  noiseless initial preparation and final readout).
- **Z-basis memory**, r = d_upper rounds of syndrome extraction, X-then-Z
  monomial-matching schedule.
- Decoder: BP+OSD from `ldpc` 2.4.1 (min-sum, 30 iterations, scaling 0.625,
  OSD-CS order 10), pinned. Sampling with Stim 1.16.0.

**The label.** `true_ler` is the logical error rate **per round, per logical
qubit**: `1 - (1 - P_L) ** (1 / (r * k))`, where P_L is the fraction of shots in
which any logical observable failed
([INV-4](CONTRACT.md#inv-4--ler-normalisation-is-pinned-to-exactly-one-formula)).
Each row also has its shots, failures and a 95% Wilson interval
(`true_ler_ci_low`, `true_ler_ci_high`).

**Censoring.** A code is sampled in batches of 256 shots until it records at
least 100 logical failures, up to 40,960 shots. Below 100 failures the row is
censored: `true_ler` is null and only the upper bound `true_ler_ub` is a
statement about it. **One code is censored** (0.4%; 93 failures in 40,960
shots). In ranking, a censored row ranks by its `true_ler_ub` (D-035), and every
ranking metric also reports its value with censored rows excluded.

**Distance.** `d_upper` is an upper bound from a randomised, decoder-assisted
search: the true distance is ≤ d_upper. `d_exact` is null on every row, because
no distance here was computed by an exact method. Φ is computed from d_upper and
named `phi_from_d_upper`.

**Three files, joined on `code_id`.** Committed byte-for-byte as a snapshot
(D-037) in
[`evidence/m0-verdict/2026-10-03-1131f10/data/`](evidence/m0-verdict/2026-10-03-1131f10/data/):

| File | Rows | sha256 | Holds |
|---|---|---|---|
| `m0_measurements.parquet` | 242 | `5c644c028ff81803e904bda86a2714f4f8169aa8de717462a735f603d650d696` | Measurements, `true_*` |
| `m0_features.parquet` | 242 | `49e28025ca8bbddf376613ed72382536ef569e94ebef1dfc154789c63b0632a6` | 28 cheap features, `feature_set` = `m0_features_v1` |
| `m0_predictions.parquet` | 242 | `ba6f75f41c3fbd0e858c7bb6dbe7f3e6facbabc7d1594a408f5564a5f3e5e5ea` | Out-of-fold model output, `pred_log10_ler`, `fold`, `model_version` |

Measurements are `true_*`, predictions are `pred_*`, and the two never share a
file or a column
([INV-1](CONTRACT.md#inv-1--the-surrogate-is-never-the-ground-truth)).

Columns of `m0_measurements.parquet` (from `spec/architecture.md §3`):

| Column | Type | Meaning |
|---|---|---|
| `code_id` | str | `{program_id}-{sha256(params_json)[:12]}`; the join key |
| `construction_program_id` | str | `bb_v1_<template>`; the grouping key for splits |
| `family` | str | `BB` for every M0 row |
| `params_json`, `seed` | str, int64 | Regenerate the code's check matrices |
| `n`, `k` | int32 | Block length; logical qubits (GF(2) rank) |
| `d_exact` | int32, nullable | Null unless provably exact; null on every M0 row |
| `d_upper` | int32 | Distance upper bound |
| `phi_from_d_upper` | float64 | kd²/n using d_upper |
| `n_ancilla`, `n_total` | int32 | Physical qubit budget |
| `protocol_hash` | str | SHA-256 of the protocol; one value in this file |
| `commit_sha` | str | Commit that produced the row (`1131f10…` for all 242) |
| `sampling_seed` | int64 | Seed given to the Stim sampler, derived from the row |
| `stim_version`, `cpu_class` | str | Provenance (`1.16.0`, `x86_64/sse2`) |
| `p` | float64 | Physical error rate (0.002) |
| `rounds` | int32 | r, equal to d_upper |
| `shots`, `failures` | int64 | Raw counts |
| `true_ler` | float64, nullable | Per-round, per-logical-qubit Z-memory LER; null if censored |
| `true_ler_ub` | float64 | Wilson upper bound, on every row |
| `true_ler_ci_low`, `true_ler_ci_high` | float64 | 95% Wilson interval |
| `censored` | bool | `failures < 100` |
| `decode_seconds` | float64 | Decoding time, cost telemetry |
| `schema_version` | int32 | 1 |
| `created_at` | str | ISO 8601, UTC |

## How to use it

Install from a clone. These are the commands CI runs on Python 3.11, 3.12 and
3.13 (CI runs the full suite, `pytest -m "slow or not slow"`; plain `pytest`
runs the default, faster subset):

```bash
git clone https://github.com/Pushkar0997/qecscreen
cd qecscreen
pip install -r requirements.txt
pip install .
python -m qecscreen.selfcheck
pytest
```

Runs on CPU only. No API keys and no paid services. Run the examples below from
the repository root: the snapshot is in the repository, not in the installed
package.

### a. Load the labels and rank the codes

```python
import pandas as pd

snap = "evidence/m0-verdict/2026-10-03-1131f10/data/"
m = pd.read_parquet(snap + "m0_measurements.parquet")

# Ranking value: true_ler, or true_ler_ub for a censored row (D-035). Lower = better.
m["rank_value"] = m["true_ler"].where(~m["censored"], m["true_ler_ub"])
top = m.sort_values("rank_value").head(10)
print(top[["code_id", "n", "k", "d_upper", "shots", "failures",
           "censored", "true_ler", "true_ler_ub"]].to_string(index=False))
print(len(m), "rows;", m["censored"].sum(), "censored;",
      m["protocol_hash"].nunique(), "protocol_hash")
```

Output from the committed snapshot: ten `bb_v1_pair_2_2` codes, all k = 2, the
censored one second, ending `242 rows; 1 censored; 1 protocol_hash`.

### b. Score your own ranking against the M0 labels

`qecscreen.metrics.recall_at_k` and `qecscreen.metrics.spearman` take the
measurements frame and the name of any numeric column you add to it, oriented
**higher = predicted better**. They need no other setup: the frame already
carries `protocol_hash`, `censored`, `true_ler` and `true_ler_ub`. Each returns
the value, the number of censored rows, and the value with them excluded.
`qecscreen.metrics.bootstrap_compare` gives the paired interval against Φ, the
same bootstrap as the table above, with your column as `model_col`. All three
are covered by `tests/test_metrics.py`. With a trivial score:

```python
import pandas as pd
from qecscreen.metrics import bootstrap_compare, recall_at_k, spearman

m = pd.read_parquet("evidence/m0-verdict/2026-10-03-1131f10/data/m0_measurements.parquet")

# Your score: any numeric column, higher = predicted better. Here, a trivial one:
# smaller block length predicted better.
m["my_score"] = -m["n"].astype("float64")

for name, metric in [("Recall@30-of-top-10", recall_at_k), ("Spearman", spearman)]:
    for col in ["my_score", "phi_from_d_upper"]:
        r = metric(m, col)
        print(f"{name:20} {col:17} {r.value:6.3f}  censored {r.n_censored}, "
              f"without them {r.value_censored_excluded:6.3f}")

# Paired bootstrap, your score minus Φ (1,000 resamples of codes).
b = bootstrap_compare(m, spearman, seed = 20261001, model_col = "my_score")
print(f"Spearman, my_score - phi: {b.difference.estimate:.3f} "
      f"[{b.difference.low:.3f}, {b.difference.high:.3f}]")

# INV-6 guard: rows under two protocol hashes are refused, not ranked.
other = m.head(5).assign(protocol_hash="0" * 64)
try:
    spearman(pd.concat([m, other]), "my_score")
except ValueError as e:
    print("refused:", str(e)[:44], "...")
```

Output from the committed snapshot:

```
Recall@30-of-top-10  my_score           0.000  censored 1, without them  0.000
Recall@30-of-top-10  phi_from_d_upper   0.000  censored 1, without them  0.000
Spearman             my_score          -0.043  censored 1, without them -0.033
Spearman             phi_from_d_upper   0.242  censored 1, without them  0.243
Spearman, my_score - phi: -0.285 [-0.428, -0.145]
refused: refusing to combine 2 distinct protocols: [' ...
```

Φ's lines match the verdict (0.000, and 0.242 / 0.243). To use features, merge
`m0_features.parquet` on `code_id`. If your score is fitted to these labels,
evaluate it out of fold with folds grouped by `construction_program_id`
(`qecscreen.splits.grouped_kfold`), never on rows it was trained on.

### c. Reproduce the M0 numbers

Run once by the maintainer; results and input hashes in `spec/evals.md §7`.
Not re-run for this README.

Install at commit `17263bf` or later (a clone of `main` qualifies), **not** at
`1131f10`. `1131f10` is the commit that ran the pilot and that every row
records, but at that commit assembly refuses the two D-036 codes and the
label-noise ceiling does not exist. The evaluation ran from source equal to
`17263bf`.

Save this as `rerun_m0.py` in the repository root:

```python
# lightgbm must load before pyarrow (Windows DLL clash, AGENT_LOG 2026-10-01).
from qecscreen.verdict import run_m0_evaluation
import pandas as pd
from qecscreen.evaluate.pilot import assemble_measurements
from qecscreen.features.table import compute_features, write_features

# Checks the tar against its sidecar sha256, writes data/m0_measurements.parquet (242 rows).
assemble_measurements("evidence/pilot/final-1131f10/m0-pilot.tar", "data")
# Features from the 242 measured codes (the full population includes the two unbuildable ones).
write_features(compute_features(pd.read_parquet("data/m0_measurements.parquet")), "data")
# Writes data/m0_predictions.parquet, then m0_results.json and .txt under evidence/.
run_m0_evaluation("data/m0_measurements.parquet", "data/m0_features.parquet", "evidence/m0-rerun")
```

Bash:

```bash
(cd evidence/pilot/final-1131f10 && sha256sum -c m0-pilot.tar.sha256)
python rerun_m0.py
```

PowerShell:

```powershell
(Get-FileHash evidence\pilot\final-1131f10\m0-pilot.tar -Algorithm SHA256).Hash.ToLower()
# expect ccef076d29db82a25148f55fafe3f3e6c9cb5d15943817266daf015dbc511aa8
python rerun_m0.py
```

The writers refuse to overwrite, so `data/` must not already hold the three
files, and the output directory must lie under `evidence/`. Compare the printed
table with the one above. Seeds are pinned (bootstrap 20261001, ceiling
20261002).

### d. Run your own pilot on Kaggle

`notebooks/pilot.ipynb` runs one session of the M0 pilot; the full runbook is
in [`spec/architecture.md §2`](spec/architecture.md#m0-pilot-runbook-d-033). In
short: install pinned to one full 40-character commit for every session;
session 1 is a 12-code, 3-hour probe whose cost report you check locally before
going on; later sessions attach the previous version's `m0-pilot.tar` as input
and resume from it; each session stops starting codes after 10.5 hours. When
242 of 244 are done, `assemble_measurements` writes the measurements file. The
M0 pilot took three sessions and 76.3 core-hours. The runner enumerates the
pinned M0 population and refuses any other, so it repeats M0; it does not yet
run a population of your choosing.

### e. Not supported yet

From the capability register (`spec/architecture.md §4`) and the backlog
(`spec/tasks.md`):

- **Other code families** (GB, HGP, TB). BB only. Planned for M1.
- **Other physical error rates.** One p, 0.002. Planned for M1.
- **Exact distance.** Only d_upper; may never be supported.
- **A scoring CLI or a `score(code)` function.** None exists. The benchmark CLI
  is planned for M2, a scoring function for M4.
- **A Zenodo or HuggingFace release, or a DOI.** Planned for M1. Until then the
  committed snapshot is the copy to use.

## Using it correctly

Each pitfall is an invariant in [CONTRACT.md](CONTRACT.md):

- **No random splits.** Siblings from one template are near-duplicates; split by
  `construction_program_id`
  ([INV-2](CONTRACT.md#inv-2--splits-are-by-construction-program-never-by-row)).
- **Never compare rows across protocol hashes.** Different noise or decoder
  moves rates more than codes do
  ([INV-6](CONTRACT.md#inv-6--every-row-stores-a-protocol-hash-and-rows-with-different-hashes-are-never-compared)).
- **d_upper is a bound.** The true distance is ≤ d_upper; say which you used
  ([INV-5](CONTRACT.md#inv-5--distance-is-labelled-as-bound-or-exact-never-conflated)).
- **Censored rows are bounds.** Use `true_ler_ub`, never a point estimate, and
  exclude them from regression targets
  ([INV-3](CONTRACT.md#inv-3--every-label-carries-its-shot-count-and-interval-and-thin-labels-are-censored-not-guessed)).
- **Predictions are not measurements.** `pred_log10_ler` is model output; never
  report it as a code's rate
  ([INV-1](CONTRACT.md#inv-1--the-surrogate-is-never-the-ground-truth)).

## Repository map

```
src/qecscreen/   the package: protocol (constants, LER formula), codes/, circuits/,
                 evaluate/ (sampling, decoding, pilot), features/, models/,
                 splits.py, metrics.py, verdict.py
notebooks/       thin Kaggle/Colab runners (pilot.ipynb, calibrate.ipynb); no logic
evidence/        committed run outputs: calibration/, pilot/ (the archives),
                 m0-verdict/ (results and the dataset snapshot)
spec/            plan, architecture, decisions (D-001…), evals (verdicts), tasks
docs/            the M0 write-up
```

`CONTRACT.md` holds the invariants and pinned values; `AGENTS.md` the working
rules; `tests/` mirrors `src/`.

## How this was built

The project is spec-driven: `CONTRACT.md` states the invariants and pinned
protocol values, each with the test that detects a violation, and every design
choice is a numbered decision in `spec/decisions.md` with the alternatives
rejected. Run outputs are committed under `evidence/` with their sha256 hashes,
and the verdict cites them. [NARRATIVE.md](NARRATIVE.md) tells the story in
plain language.

## Roadmap

These are plans, not results (`spec/plan.md`). M1 has not started.

- **M1, Dataset v0.1:** more families (GB, HGP), three qubit budgets and three
  values of p, ~2,000 rows, a Zenodo DOI.
- **M2, Benchmark and baselines:** frozen splits with family holdout as the
  headline, a scoring CLI, a preprint.
- **M3, GNN surrogate:** a Tanner-graph model compared with LightGBM and Φ on
  the same holdout.
- **M4, Package and outreach:** a pip-installable scoring function and a worked
  search-loop example.

## Citation, licence, contributing

- **Citation:** use [CITATION.cff](CITATION.cff) (GitHub's "Cite this
  repository" reads it).
- **Licence:** source under the **Apache License 2.0** ([LICENSE](LICENSE),
  [NOTICE](NOTICE)). The M0 dataset snapshot in
  [`evidence/m0-verdict/2026-10-03-1131f10/data/`](evidence/m0-verdict/2026-10-03-1131f10/data/)
  is licensed under CC-BY-4.0
  ([its LICENSE](evidence/m0-verdict/2026-10-03-1131f10/data/LICENSE)); the
  source stays Apache-2.0. Copyright 2026 Pushkar Kumar.
- **Contributing:** see [CONTRIBUTING.md](CONTRIBUTING.md). Every commit needs a
  DCO sign-off (`git commit -s`).
