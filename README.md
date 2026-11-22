# qecscreen

[![CI](https://github.com/Pushkar0997/qecscreen/actions/workflows/ci.yml/badge.svg)](https://github.com/Pushkar0997/qecscreen/actions/workflows/ci.yml)

**Can we predict which quantum error-correcting codes actually work well in practice — without spending hundreds of hours simulating every candidate?**

`qecscreen` is an open benchmark, dataset, and baseline suite for testing cheap **screening scores** used in quantum error correction (QEC) code search. It pairs real circuit-level simulations with simple structural models so researchers, students, and ML engineers can see what actually separates strong quantum codes from weak ones.

---

## Start here: the plain-English explanation

If you are new to quantum error correction — or coming from software engineering or machine learning — here is the whole problem in 60 seconds (or jump straight to our illustrated [Visual Beginner's Guide](docs/explainer.md) with ASCII diagrams):

1. **Quantum computers are noisy.** Physical quantum bits (qubits) make errors constantly. To run real computations, we group many noisy physical qubits together using a **quantum error-correcting code** (QEC code) to protect a smaller number of reliable **logical qubits**.
2. **Finding good codes is a needle-in-a-haystack search.** Researchers and AI-driven search loops now generate thousands of candidate **quantum LDPC codes** (a promising family of codes that need far fewer physical qubits than older designs).
3. **Testing a candidate properly is slow.** To know how well a code really protects information on noisy hardware, you have to build its full error-checking circuit and simulate thousands of noisy runs (**circuit-level Monte Carlo simulation**). Testing just 242 small codes in our first milestone took **76.3 CPU core-hours**.
4. **So search loops use a quick shortcut — and that shortcut may be broken.** Because full simulation is too expensive to run on every candidate, search loops screen candidates first with a back-of-the-envelope formula:

   $$\Phi = \frac{k \cdot d^2}{n}$$

   where `n` is the number of physical data qubits, `k` is the number of protected logical qubits, and `d` is the code's **distance** (roughly, how many simultaneous errors it takes to fool the code). Higher `Φ` is assumed to mean a better code.
5. **The problem:** `Φ` only looks at static math properties. It ignores how messy the error-checking circuit is to execute on real noisy gates and how hard it is for a **decoder** (the classical algorithm that fixes errors) to interpret the syndrome measurements. A code can look great under `Φ` and still fail badly when simulated at the circuit level.

**What `qecscreen` does:** Instead of guessing whether `Φ` works, `qecscreen` measures the real **circuit-level logical error rate** (how often a protected logical qubit actually fails under realistic gate noise) using a pinned, reproducible simulation pipeline (`Stim` + `BP+OSD`). It then tests whether a fast machine-learning model (LightGBM) trained on cheap graph and circuit features can rank candidate codes better than `Φ` — and publishes the measured dataset so anyone can test their own screening score against the same ground truth.

---

## Status at a glance

**Milestone 0 (M0) closed on 2026-10-03.**
- **Verdict:** **PROCEED, with the headline criterion FAILED** (`spec/evals.md §7`).
- **Visual beginner's guide:** [docs/explainer.md](docs/explainer.md) (step-by-step diagrams of codes, Tanner graphs, circuits, decoders, and screening).
- **Full M0 write-up:** [docs/m0-writeup.md](docs/m0-writeup.md) (written for both newcomers and specialists).
- **Project story:** [NARRATIVE.md](NARRATIVE.md) (plain-language lab history).
- **Next milestone:** **M1 has not started yet.**

> **Important scope boundary:** Every result below covers **one specific population** — 242 **bivariate bicycle (BB)** quantum codes with at most 72 data qubits (`n ≤ 72`) tested at one physical gate error rate (`p = 0.002`). Nothing here is a claim about other code families, larger codes, or other noise levels.

---

## Key concepts explained (mini glossary)

You do not need a PhD in QEC to read the rest of this page. Here is every technical term used in the results below:

| Term | Plain-English meaning | Technical detail in `qecscreen` |
|---|---|---|
| **Quantum LDPC code** | An error-correcting code where each error check only touches a small, fixed number of qubits ("low-density parity-check"). | Defined by two binary parity-check matrices `H_X` and `H_Z` over GF(2). |
| **Bivariate bicycle (BB) code** | A well-known, hardware-friendly family of quantum LDPC codes built from two compact polynomials (e.g., IBM's gross code belongs to this family). | M0 enumerates all admissible BB codes with `n ≤ 72` and `d_upper ≥ 3` across 11 polynomial templates. |
| **`n`, `k`, and `d_upper`** | `n` = physical data qubits used; `k` = logical qubits protected; `d` = code distance (minimum error weight that causes an undetectable failure). | Exact distance is computationally hard; `d_upper` is an **upper bound** from a randomized search (`true distance ≤ d_upper`). `d_exact` is null on every M0 row. |
| **Proxy score `Φ = kd²/n`** | The standard quick formula used to estimate code quality without running a full circuit simulation. | Computed using `d_upper` and stored as `phi_from_d_upper`. |
| **Circuit-level LER (`true_ler`)** | The real measured failure rate: how likely a logical qubit is to suffer an error during one round of error checking, assuming every gate, reset, idle step, and measurement can fail. | Normalized per round, per logical qubit: `1 - (1 - P_L) ** (1 / (r * k))` ([INV-4](CONTRACT.md#inv-4--ler-normalisation-is-pinned-to-exactly-one-formula)). Lower is better. |
| **Stim & BP+OSD** | **Stim** simulates noisy quantum circuits rapidly; **BP+OSD** is the classical decoder that looks at error signals (syndromes) and tries to deduce what went wrong. | Pinned to `Stim 1.16.0` and `ldpc 2.4.1` (`BpOsdDecoder`, min-sum, 30 iterations, scaling 0.625, OSD-CS order 10). |
| **Censored code** | A code that performed so well that it did not reach 100 failures even at our maximum simulation budget (40,960 runs). We know its failure rate is very low, so we record an **upper bound** (`true_ler_ub`) instead of guessing a noisy point estimate. | `censored = True` when `failures < 100`. Only 1 of 242 M0 codes is censored (93 failures in 40,960 shots). |
| **Leave-one-program-out split** | A strict fairness test for ML: instead of randomly hiding individual codes (which leaks near-identical siblings from the same recipe into training), we hold out an entire **construction template** at a time and force the model to predict on a recipe it has never seen. | 11 construction programs (`construction_program_id`) → 11 folds. Random row splits are banned ([INV-2](CONTRACT.md#inv-2--splits-are-by-construction-program-never-by-row)). |
| **Recall@30-of-top-10** | "If you can only afford to simulate your top 30 picks, how many of the true top 10 best codes did you catch?" Ranges from `0.0` (caught none) to `1.0` (caught all 10). | M0's pre-registered headline metric. |
| **Spearman correlation** | Measures how well a score ranks *all* 242 codes from best to worst overall (`1.0` = perfect ordering, `0.0` = random, `-1.0` = backwards). | Secondary ranking metric; used in M0's kill condition. |
| **Bootstrap 95% CI** | A statistical confidence range (`[low, high]`) built by resampling codes 1,000 times. If the range for `Model − Φ` includes `0.0`, the difference could be due to chance. | Paired over codes, 1,000 resamples, pinned seed `20261001`. |
| **Label-noise ceiling** | A sanity check: if we redraw each code's error rate within its own measurement uncertainty, could even the true ranking still recover the top 10? A ceiling of `1.000` proves the measurements are sharp enough — any miss is the model's fault, not noisy labels. | 1,000 Beta-binomial draws, pinned seed `20261002`. Reported only; decides nothing. |

---

## M0 results: what we tested and what happened

Before running a single simulation, we pre-registered one clear pass/fail question:

> **Does a fast LightGBM model using 28 cheap structural and circuit features beat `Φ = kd²/n` at finding the true top 10 codes inside its top 30 picks (`Recall@30-of-top-10`), on a strict template-grouped split, by a margin that survives bootstrap resampling?**

### The short answer: **No — yet the project proceeds anyway.**

Here is why both halves of that verdict matter:

1. **Headline criterion FAILED (finding the very best 10 codes):**
   The LightGBM model caught **2 of the top 10** codes (`0.200`), while `Φ` caught **0 of 10** (`0.000`). However, the 95% bootstrap confidence interval for the difference `Model − Φ` is `[0.000, 0.600]`, which touches zero. Because we do not round up uncertain results, the headline test is recorded as a **FAIL**.
2. **Kill condition NOT met (ranking all 242 codes overall):**
   Our pre-registered rule to shut the project down required `Φ` to already rank codes well *and* the model's advantage to disappear. The exact opposite happened across the full dataset: `Φ`'s overall Spearman rank correlation with the true circuit-level error rate is only **0.242**, whereas LightGBM achieves **0.871** — a lead of **+0.629** (`[0.521, 0.750]`) that clearly survives resampling.

In plain words: **cheap structural features clearly carry real signal that `Φ` misses**, so the core hypothesis is alive — but M0's small single-family setup was not enough to prove reliable top-10 discovery on unseen templates.

### Full M0 scoreboard

All numbers come from leave-one-program-out evaluation across the 11 BB templates (242 codes; M0 has one code family, so there is no cross-family holdout yet). Intervals are 95% paired bootstrap intervals over codes (1,000 resamples, seed `20261001`). Source: [`m0_results.txt`](evidence/m0-verdict/2026-10-03-1131f10/m0_results.txt).

| Metric (242 codes, leave-one-program-out) | LightGBM Model | `Φ` (from `d_upper`) | Model − `Φ` | What it tells us |
|---|---|---|---|---|
| **Recall@30-of-top-10** *(headline)* | 0.200 `[0.000, 0.600]` | 0.000 `[0.000, 0.000]` | 0.200 `[0.000, 0.600]` | Interval includes 0 → **headline FAIL** |
| Recall, censored code excluded | 0.100 | 0.000 | — | Drops from 2/10 to 1/10 without the #2 code |
| **Spearman rank correlation** | 0.871 `[0.838, 0.894]` | 0.242 `[0.118, 0.354]` | 0.629 `[0.521, 0.750]` | Strong global ordering signal → **kill condition not met** |
| Spearman, censored code excluded | 0.870 | 0.243 | — | Essentially unchanged |
| **Label-noise ceiling** (Recall@30-of-top-10) | 1.000 `[1.000, 1.000]` | — | — | Labels are clean; model error, not noise |

### Four takeaways from M0

- **Why Recall@30 was so noisy (the single-fold bottleneck):** All 10 of the genuinely best codes in M0 came from **one single template**, `pair_2_2`. Under leave-one-program-out evaluation, the single fold that held out `pair_2_2` had to predict every single top-10 code without ever seeing a `pair_2_2` example during training. That means **one fold decided the entire headline metric**, making the confidence interval wide (`[0.000, 0.600]`) and causing the point estimate to drop from `0.200` to `0.100` if the one censored code (ranked #2) is excluded. It was *not* caused by measurement noise — the label-noise ceiling is a perfect `1.000`.
- **Why `Φ = kd²/n` scored exactly zero on Recall@30:** Every top-10 code encodes only `k = 2` logical qubits and has a modest proxy score (`Φ ≤ 1.64`). Because `Φ` strongly rewards larger `k`, at least **70 codes with both higher `k` and higher `Φ`** ranked ahead of every single top-10 code — even though those higher-`k` codes suffered much worse circuit-level error rates.
- **Simple check weight gets surprisingly far (exploratory, post hoc):** After recording the verdict, we checked how well individual features ranked all 242 codes on their own (point values only, no intervals; see [docs/m0-writeup.md](docs/m0-writeup.md), not part of the verdict). Predicting lower error rates for codes with lower **mean check weight** (`-check_weight_mean`, meaning each error check involves fewer qubits and therefore fewer noisy two-qubit gates) reached a Spearman correlation of **0.719**, compared to **0.310** for `d_upper` alone and **−0.026** for `k` alone. Be careful over-interpreting this: mean check weight takes only five distinct values in M0 and mostly reflects which template a code came from, and it says nothing about catching the top 10.
- **The cost asymmetry makes screening valuable:** The exact codes a researcher wants to discover — the ones with the lowest logical error rates — are the hardest and most expensive to verify, because you must run far more shots to observe 100 failures. The top 10 codes required **24,320 to 40,960 shots each** (hitting the 40,960 cap on the censored code), compared to a median of just **1,024 shots** across all 242 codes. Spending simulation budget on bad candidates wastes huge amounts of compute.

---

## The M0 dataset (qecscreen-bench M0 snapshot)

Anyone can download and analyze the measured M0 dataset directly from this repository — no quantum hardware, no paid compute, and no re-simulation required.

### How the dataset was built

- **Code population:** Every admissible bivariate bicycle (BB) code with `n ≤ 72` and `d_upper ≥ 3` across 11 polynomial templates — **244 codes enumerated exhaustively** (not randomly sampled).
- **2 excluded codes (D-036):** Two `mixed_3_5` codes with `l = 2` were excluded because cyclic wrap-around (`x³ = x`) causes two monomial terms in polynomial `B` to collide and cancel over GF(2). The pinned syndrome-extraction schedule refuses to build a circuit that would measure the wrong checks. **242 of 244 codes have a measured row.** The two excluded IDs and reasons are stored in the measurements Parquet file's schema metadata (`qecscreen.excluded_codes`).
- **One pinned simulation protocol:** Every single row shares `protocol_hash` `6230a7a8a31d8b202e5454c49cf7823b77f95d8452a7d27e273ce9a89fcb32fe` ([CONTRACT.md, protocol v1](CONTRACT.md#exact-values--protocol-v1)):
  - **Noise model:** `uniform_depolarizing_v1` at physical error rate **`p = 0.002`** (depolarizing errors on idle qubits, two-qubit depolarizing errors after every CX gate, and reset/measurement errors at `p`; noiseless initial state preparation and final data readout).
  - **Experiment:** **Z-basis quantum memory**, run for `r = d_upper` rounds of syndrome extraction using a pinned X-then-Z monomial-matching gate schedule (`bb_monomial_matching_xz_phased_v2`).
  - **Simulator & decoder:** `Stim 1.16.0` paired with `ldpc 2.4.1` **BP+OSD** (min-sum, 30 iterations, scaling 0.625, OSD-CS order 10).
- **Label definition & uncertainty:** `true_ler` is the logical error rate **per round, per logical qubit**:
  `1 - (1 - P_L) ** (1 / (r * k))`, where `P_L` is the fraction of shots in which any logical observable failed ([INV-4](CONTRACT.md#inv-4--ler-normalisation-is-pinned-to-exactly-one-formula)). Every row also stores raw `shots`, `failures`, and a 95% Wilson confidence interval (`true_ler_ci_low`, `true_ler_ci_high`).
- **Adaptive sampling & censoring:** Each code is sampled in batches of 256 shots until it accumulates at least **100 logical failures**, stopping at a cap of **40,960 shots**. If a code reaches 40,960 shots with fewer than 100 failures, it is marked **censored**: `true_ler` is left `null`, and only its statistical upper bound `true_ler_ub` is reported. **1 code is censored** (0.4%; 93 failures in 40,960 shots). In ranking metrics, censored rows rank by `true_ler_ub` (D-035), and every metric also reports its value with censored rows excluded.
- **Distance provenance:** `d_upper` comes from a randomized, decoder-assisted distance search, meaning the true code distance satisfies `true distance ≤ d_upper`. `d_exact` is `null` on every M0 row. `Φ` is computed from `d_upper` and named `phi_from_d_upper` ([INV-5](CONTRACT.md#inv-5--distance-is-labelled-as-bound-or-exact-never-conflated)).

### The three committed Parquet files

Committed byte-for-byte (D-037) in [`evidence/m0-verdict/2026-10-03-1131f10/data/`](evidence/m0-verdict/2026-10-03-1131f10/data/) under **CC BY 4.0** (joined on `code_id`):

| File | Rows | SHA-256 | What is inside |
|---|---|---|---|
| `m0_measurements.parquet` | 242 | `5c644c028ff81803e904bda86a2714f4f8169aa8de717462a735f603d650d696` | Ground-truth measurements (`true_*`), counts, intervals, and provenance |
| `m0_features.parquet` | 242 | `49e28025ca8bbddf376613ed72382536ef569e94ebef1dfc154789c63b0632a6` | 28 cheap structural & circuit features (`feature_set` = `m0_features_v1`) |
| `m0_predictions.parquet` | 242 | `ba6f75f41c3fbd0e858c7bb6dbe7f3e6facbabc7d1594a408f5564a5f3e5e5ea` | Out-of-fold LightGBM outputs (`pred_log10_ler`, `fold`, `model_version`) |

Measurements (`true_*`) and model predictions (`pred_*`) are deliberately kept in separate files so a model's guess can never be mistaken for a real simulation ([INV-1](CONTRACT.md#inv-1--the-surrogate-is-never-the-ground-truth)).

<details>
<summary><strong>Click to view the full column dictionary for <code>m0_measurements.parquet</code> (28 columns)</strong></summary>

| Column | Type | Meaning |
|---|---|---|
| `code_id` | str | `{program_id}-{sha256(params_json)[:12]}`; unique join key |
| `construction_program_id` | str | `bb_v1_<template>`; grouping key for train/test splits |
| `family` | str | `BB` for every M0 row |
| `params_json`, `seed` | str, int64 | Exact parameters to regenerate the code's parity-check matrices |
| `n`, `k` | int32 | Physical data qubits (`n`) and logical qubits (`k`, exact GF(2) rank) |
| `d_exact` | int32, nullable | Exact distance (only populated if provably exact; null on every M0 row) |
| `d_upper` | int32 | Distance upper bound from randomized decoder-assisted search |
| `phi_from_d_upper` | float64 | Proxy score `k * (d_upper ** 2) / n` |
| `n_ancilla`, `n_total` | int32 | Ancilla (check) qubits and total physical qubits (`n + n_ancilla`) |
| `protocol_hash` | str | SHA-256 of the simulation/decoding protocol; identical across all 242 rows |
| `commit_sha` | str | Git commit that produced the row (`1131f10…` for all 242) |
| `sampling_seed` | int64 | Deterministic seed passed to the Stim sampler |
| `stim_version`, `cpu_class` | str | Execution provenance (`1.16.0`, `x86_64/sse2`) |
| `p` | float64 | Physical error rate (`0.002`) |
| `rounds` | int32 | Syndrome-extraction rounds (`r`, equal to `d_upper`) |
| `shots`, `failures` | int64 | Total simulated shots and observed logical failures |
| `true_ler` | float64, nullable | Per-round, per-logical-qubit Z-memory LER; null if censored |
| `true_ler_ub` | float64 | 95% Wilson upper bound on LER, present on every row |
| `true_ler_ci_low`, `true_ler_ci_high` | float64 | 95% Wilson confidence interval on `true_ler` |
| `censored` | bool | `True` when `failures < 100` |
| `decode_seconds` | float64 | Wall-clock CPU decoding time (cost telemetry) |
| `schema_version` | int32 | Schema version (`1`) |
| `created_at` | str | UTC timestamp (ISO 8601) |

</details>

---

## How to install and use `qecscreen`

Everything runs on a standard **CPU** — no quantum hardware, no GPU, no API keys, and no paid cloud services.

### Installation

These are the exact commands tested by CI on Python 3.11, 3.12, and 3.13 (CI runs the full test suite with `pytest -m "slow or not slow"`; plain `pytest` runs the faster default subset):

```bash
git clone https://github.com/Pushkar0997/qecscreen
cd qecscreen
pip install -r requirements.txt
pip install .
python -m qecscreen.selfcheck
pytest
```

Run the Python examples below from the **repository root**, since the M0 dataset snapshot lives inside `evidence/` in the repository rather than inside the installed wheel.

### a. Load the M0 dataset and inspect the 10 best codes

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

Output from the committed snapshot: ten `bb_v1_pair_2_2` codes, all `k = 2`, the censored one second, ending `242 rows; 1 censored; 1 protocol_hash`.

### b. Score your own screening idea against the M0 labels

Have a new heuristic, analytical formula, or ML model? Add it as a numeric column on the measurements DataFrame — oriented so that **higher value = predicted better code** — and evaluate it directly with `qecscreen.metrics`.

- `recall_at_k` and `spearman` return the score, the count of censored rows, and the score with censored rows excluded.
- `bootstrap_compare` computes the exact same 1,000-resample paired bootstrap confidence interval against `Φ` used in the M0 verdict table.
- Every metric automatically enforces the **INV-6 protocol guard** (refusing to mix rows simulated under different protocols).

All three functions are covered by `tests/test_metrics.py`. Example with a trivial score (`-n`, guessing that smaller codes have lower error rates):

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

```text
Recall@30-of-top-10  my_score           0.000  censored 1, without them  0.000
Recall@30-of-top-10  phi_from_d_upper   0.000  censored 1, without them  0.000
Spearman             my_score          -0.043  censored 1, without them -0.033
Spearman             phi_from_d_upper   0.242  censored 1, without them  0.243
Spearman, my_score - phi: -0.285 [-0.428, -0.145]
refused: refusing to combine 2 distinct protocols: [' ...
```

Notice that `Φ`'s lines reproduce the verdict (`0.000`, and `0.242` / `0.243`). To use the 28 structural features, merge `m0_features.parquet` on `code_id`. **If your score is trained on these labels, always evaluate out-of-fold grouped by `construction_program_id`** (`qecscreen.splits.grouped_kfold`), never on codes it trained on or via a random split.

### c. Reproduce the M0 numbers from the raw pilot archive

Run once by the maintainer; results and input hashes are recorded in `spec/evals.md §7`. Not re-run for this README.

Install at commit `17263bf` or later (a clone of `main` qualifies), **not** at `1131f10`. `1131f10` is the commit that ran the Kaggle pilot and that every row records, but at that commit assembly refuses the two D-036 codes and the label-noise ceiling does not exist yet. The evaluation ran from source equal to `17263bf`.

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

Verify the pilot archive checksum and run the script:

```bash
# Bash
(cd evidence/pilot/final-1131f10 && sha256sum -c m0-pilot.tar.sha256)
python rerun_m0.py
```

```powershell
# PowerShell
(Get-FileHash evidence\pilot\final-1131f10\m0-pilot.tar -Algorithm SHA256).Hash.ToLower()
# expect ccef076d29db82a25148f55fafe3f3e6c9cb5d15943817266daf015dbc511aa8
python rerun_m0.py
```

The writers refuse to overwrite existing files, so `data/` must not already contain the three Parquet files, and the output directory must lie under `evidence/`. Seeds are pinned (`20261001` for bootstrap, `20261002` for the label-noise ceiling).

### d. Re-running the full Kaggle pilot

`notebooks/pilot.ipynb` executes one session of the M0 pilot; the step-by-step runbook is in [`spec/architecture.md §2`](spec/architecture.md#m0-pilot-runbook-d-033). In summary: install pinned to one full 40-character commit SHA across all sessions; Session 1 runs a 12-code, 3-hour probe whose cost report is checked locally before scaling up; subsequent sessions attach the previous session's `m0-pilot.tar` and resume from disk, stopping cleanly at 10.5 hours to stay safely inside Kaggle's 12-hour limit. The M0 pilot finished in 3 sessions (76.3 core-hours). Note that the runner is currently pinned to the M0 population and refuses custom populations.

### e. What is NOT supported yet

From the capability register (`spec/architecture.md §4`) and backlog (`spec/tasks.md`):

- **Other code families (GB, HGP, TB):** Currently BB codes only. Planned for M1.
- **Multiple physical error rates (`p`):** Currently one error rate (`p = 0.002`). Multi-`p` sweeps are planned for M1.
- **Exact code distance (`d_exact`):** Only `d_upper` bounds are computed; exact distance may never be supported at scale.
- **Scoring CLI or `score(code)` API:** Not built yet. Benchmark CLI is planned for M2; a ready-to-use scoring function for M4.
- **Zenodo / HuggingFace release and DOI:** Planned for M1. Until then, use the committed snapshot in `evidence/m0-verdict/2026-10-03-1131f10/data/`.

---

## Five common pitfalls (and the rules that prevent them)

QEC machine-learning benchmarks are notoriously easy to get subtly wrong. `qecscreen` encodes its safeguards as testable invariants in [CONTRACT.md](CONTRACT.md):

1. **Do not use random train/test splits ([INV-2](CONTRACT.md#inv-2--splits-are-by-construction-program-never-by-row)).** Codes generated by the same polynomial template are near-duplicates. Splitting rows randomly leaks family structure into the test set and produces artificially high scores. Always group splits by `construction_program_id`.
2. **Never compare error rates across different protocols ([INV-6](CONTRACT.md#inv-6--every-row-stores-a-protocol-hash-and-rows-with-different-hashes-are-never-compared)).** Changing the noise model, gate schedule, or decoder moves logical error rates more than changing the code itself. Always verify a single `protocol_hash`.
3. **Never mistake `d_upper` for exact distance ([INV-5](CONTRACT.md#inv-5--distance-is-labelled-as-bound-or-exact-never-conflated)).** `d_upper` is an upper bound (`true distance ≤ d_upper`); always label whether a distance is exact or bounded.
4. **Treat censored codes as bounds, not point estimates ([INV-3](CONTRACT.md#inv-3--every-label-carries-its-shot-count-and-interval-and-thin-labels-are-censored-not-guessed)).** Fewer than 100 observed failures is too thin for a reliable LER estimate. Rank censored codes by `true_ler_ub` and exclude them from regression training targets.
5. **Never report model predictions as measured error rates ([INV-1](CONTRACT.md#inv-1--the-surrogate-is-never-the-ground-truth)).** `pred_log10_ler` is a surrogate guess; only `true_ler` comes from real circuit simulation.

---

## Repository guide

```text
README.md        You are here — plain-English overview, results, usage, and roadmap
docs/            Visual beginner's guide (explainer.md) and M0 write-up (m0-writeup.md)
NARRATIVE.md     Plain-language history of what happened and why
BRIEF.md         One-page status summary (3-minute read)
CONTRACT.md      Hard invariants and pinned simulation constants (the ground rules)
AGENTS.md        Working rules for AI coding agents
spec/            Detailed engineering specs: plan, architecture, decisions (D-001…), evals, tasks
src/qecscreen/   Python package: protocol, codes/, circuits/, evaluate/, features/, models/,
                 splits.py, metrics.py, verdict.py
tests/           Unit, golden-value, and invariant-guard tests (mirrors src/)
notebooks/       Thin Kaggle/Colab execution runners (pilot.ipynb, calibrate.ipynb)
evidence/        Committed run outputs with SHA-256 checksums, including the M0 data snapshot
```

**How this project is built:** `qecscreen` follows a spec-driven workflow. `CONTRACT.md` defines non-negotiable scientific invariants (each backed by automated tests), `spec/decisions.md` records every design choice and rejected alternative, and `evidence/` stores immutable run outputs with checksums so every claim in `spec/evals.md` is verifiable.

---

## Roadmap

> These are **plans, not results** (`spec/plan.md`). **M1 has not started.**

| Milestone | Planned goal | Key deliverables |
|---|---|---|
| **M1 — Dataset v0.1** *(Next)* | Broaden beyond small BB codes and fix the single-fold bottleneck | Add Generalized Bicycle (GB) and Hypergraph Product (HGP) families; 3 qubit budgets; 3 values of `p`; ~2,000 measured rows; citable Zenodo DOI |
| **M2 — Benchmark & Baselines** | Establish the cross-family benchmark | Frozen splits with **held-out code family** as the headline metric; scoring CLI; research preprint |
| **M3 — GNN Surrogate** | Test whether graph structure helps generalization | Tanner-graph GNN compared head-to-head against LightGBM and `Φ` on the frozen family holdout |
| **M4 — Package & Outreach** | Make screening plug-and-play for code-search loops | Pip-installable `score(code)` function and a worked automated search-loop example |

---

## Citation, licence, and contributing

- **Citation:** Use [CITATION.cff](CITATION.cff) (GitHub's **"Cite this repository"** button reads it automatically).
- **Licence:**
  - **Source software:** **Apache License 2.0** ([LICENSE](LICENSE), [NOTICE](NOTICE)).
  - **M0 dataset snapshot** (`evidence/m0-verdict/2026-10-03-1131f10/data/`): **CC BY 4.0** ([data LICENSE](evidence/m0-verdict/2026-10-03-1131f10/data/LICENSE)). Attribution is required per `CITATION.cff`.
  - Copyright 2026 Pushkar Kumar.
- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md). Every commit requires a Developer Certificate of Origin (DCO) sign-off (`git commit -s`).
