# CONTRACT — qecscreen

**The correctness core. An agent that reads only this file must not be able to break the domain.**

Precedence: this file outranks every other document. If something here conflicts with a task, the task is wrong — stop and flag it.

This project produces **a dataset that other researchers will trust**. A subtly wrong label is worse than no dataset, because it propagates into their work and ours is the name on it. Every invariant below exists because a plausible-looking mistake would produce numbers that are confidently wrong and undetectable by inspection.

---

## Invariants

### INV-1 — The surrogate is never the ground truth

**Rule:** Any reported statement about how a code actually performs must trace to a recorded Stim + decoder Monte Carlo run. Model output is never presented as a measurement.
Columns carrying measurements are prefixed `true_`. Columns carrying predictions are prefixed `pred_`. No function returns both under one name, and no plot mixes them on one series without a legend distinguishing them.

**Why:** The entire value of this project is that it tells search loops where to spend real simulation. If a predicted LER ever leaks into a results table, we have published fiction about a physical system, and the field's trust in the dataset is gone permanently.

**Violated by:** A convenience helper like `get_ler(code)` that silently falls back to the model when no measurement exists. Also by caching predictions into the same Parquet columns as measurements.

**Detected by:** `test_no_pred_true_collision` — asserts no dataframe returned by any public function contains a column that is neither `true_*`-prefixed, `pred_*`-prefixed, nor in the declared metadata schema. Plus a grep test rejecting any assignment of a `pred_` value into a `true_` column.

---

### INV-2 — Splits are by construction program, never by row

**Rule:** Two code instances generated from the same construction program with different seeds or different `(l, m)` parameters belong to the same split. The headline metric is computed on a **held-out code family**. Random row-level splits may be reported only alongside the family-holdout number, never alone, and never in an abstract or README headline.

**Why:** BB codes generated from one polynomial template are near-duplicates of each other. A random split puts siblings on both sides, the model memorises the template, and the reported score is enormous and meaningless. This is the specific way this project fails while looking like a triumph.

**Violated by:** `sklearn.model_selection.train_test_split(X, y)` — the default, the obvious call, and wrong here every time.

**Detected by:** `test_no_program_leakage` — asserts the intersection of `construction_program_id` sets across train and test splits is empty. Runs on every split produced anywhere in the codebase.

---

### INV-3 — Every label carries its shot count and interval, and thin labels are censored not guessed

**Rule:** A row is a valid point estimate only if it recorded **≥ 100 logical failures**. Below that it is written with `censored = True` and its `true_ler` is stored as an upper bound in `true_ler_ub`, with `true_ler` set to null. Censored rows are excluded from regression targets and included in ranking metrics only as ties at the bottom.

**Why:** A code that failed 3 times in 200,000 shots has an LER consistent with a range spanning an order of magnitude. Treating that as a number, and then training on it, teaches the model noise and it will confidently rank good codes badly.

**Violated by:** Running a fixed shot budget per code and dividing failures by shots regardless of how few failures occurred. This looks completely reasonable.

**Detected by:** `test_censoring_rule` — asserts every row with `failures < 100` has `censored == True` and `true_ler` is null; and every row with `censored == False` has `failures >= 100` and a finite `true_ler_ci_low`/`true_ler_ci_high`.

---

### INV-4 — LER normalisation is pinned to exactly one formula

**Rule:** Logical error rate is reported **per syndrome-extraction round, per logical qubit**, computed as:

```
p_LER = 1 - (1 - P_L) ** (1 / (r * k))
```

where `P_L` is the fraction of shots in which **any** logical observable was incorrect, `r` is the number of noisy syndrome-extraction rounds, and `k` is the number of logical qubits. No other normalisation appears anywhere in the codebase, in a plot, or in a paper draft.

**Why:** Published papers use per-shot, per-round, per-logical-qubit and per-round-per-logical-qubit interchangeably and often without saying which. Mixing two of them inside one dataset produces a ranking that is wrong by a factor that varies with `k` — precisely the quantity we are trying to rank against. This would silently destroy the entire result.

**Violated by:** Copying an LER computation out of a paper's repository without checking its normalisation, then merging with rows computed our way.

**Detected by:** `test_ler_formula_golden` against the exact values in the Golden values section below. Plus: `p_LER` is only ever produced by `qecscreen.protocol.logical_error_rate` — a grep test rejects any other exponentiation of `(1 - P_L)` in the codebase.

---

### INV-5 — Distance is labelled as bound or exact, never conflated

**Rule:** Two separate columns, `d_exact` and `d_upper`. `d_exact` is populated only when the distance was computed by an exhaustive or provably exact method. A decoder-assisted or randomised search populates `d_upper` and leaves `d_exact` null. Any figure of merit using distance states which column it used. Φ is computed from `d_upper` and is therefore named `phi_from_d_upper`.

**Why:** This is the domain rule a newcomer violates without realising. Randomised distance search returns an upper bound; reporting it as the distance is a claim about a code's guaranteed protection that has not been established. It is also how you accidentally publish a code as `[[n,k,8]]` that is actually distance 6.

**Violated by:** Naming the column `d` and forgetting where it came from three weeks later.

**Detected by:** `test_distance_provenance` — asserts no row has both `d_exact` and `d_upper` null; asserts `d_exact <= d_upper` where both are present; asserts the string `"d="` never appears in a generated report without an adjacent `exact` or `≤`.

---

### INV-6 — Every row stores a protocol hash, and rows with different hashes are never compared

**Rule:** Each measurement row carries `protocol_hash`, a SHA-256 over the canonical JSON of: noise model name and version, `p`, the **rule** for choosing the number of rounds (`rounds_rule`, pinned to `"r = d_upper"`), decoder name, decoder version, decoder parameters, syndrome-extraction scheduling method, and the schema version. Any function that ranks, plots, correlates or trains across rows asserts a single distinct `protocol_hash` in its input, or raises.

The **concrete value of `r` is deliberately not in the hash.** It is a per-row stored column instead. The decoder version is the version actually installed at the time of the run — a placeholder such as `"unset"` is never acceptable, because a hash that silently omits the thing it claims to carry is worse than no hash at all.

**Why:** LERs measured under different noise models or decoders are not comparable, and the difference is often larger than the difference between codes. Silently mixing them makes the entire dataset noise while every individual number remains correct.

**Why the rule and not the value:** `r = d_upper` (D-006) varies from code to code, so hashing the concrete `r` made `protocol_hash` a per-code identifier — `assert_single_protocol()` then fired on every legitimate cross-code ranking, which is the metric this project exists to compute. Dropping rounds from the hash altogether would be wrong in the opposite direction: a fixed-`r = 12` dataset and a variable-`r = d_upper` dataset would hash identically while being incomparable. The rule is the protocol decision; the value is a per-row fact that INV-4's per-round normalisation already accounts for. See D-014.

**Violated by:** Appending a re-run with `osd_order=5` to a table generated with `osd_order=10` because "it's the same decoder."

**Detected by:** `test_single_protocol_guard` — asserts `assert_single_protocol()` raises on a mixed-hash frame; and every ranking/training entry point calls it.

---

### INV-7 — Every code instance is regenerable from what is stored

**Rule:** The dataset stores the **construction program and its parameters**, not only the resulting check matrices. `regenerate(row)` must reproduce bit-identical `H_X`, `H_Z` from `construction_program_id` + `params` + `seed`.

**Why:** A dataset of anonymous matrices is not reproducible, cannot be extended, and cannot be split by program (INV-2). Reviewers will ask.

**Detected by:** `test_regenerate_roundtrip` — for a random sample of 20 rows per release, regenerate and assert matrix equality.

---

### INV-8 — Code validity is verified, never assumed

**Rule:** Every row passes, before any circuit is built: `H_X @ H_Z.T % 2 == 0`; `n` equals the column count of both; `k = n - rank_F2(H_X) - rank_F2(H_Z)`. Rank is computed over GF(2), never with floating-point linear algebra.

**Why:** A generator that produces non-commuting checks yields a "code" that is not a code. Stim will happily build a circuit for it and BP+OSD will happily decode it, producing a plausible LER for an object with no meaning.

**Violated by:** `numpy.linalg.matrix_rank`, which works over the reals and gives the wrong rank over GF(2). This is a real and common bug.

**Detected by:** `test_css_commutation` and `test_gf2_rank_not_float` — the latter greps for `linalg.matrix_rank` and fails if found.

---

### INV-9 — Zero recurring cost

**Rule:** No component may require a paid service, a server, a managed database, or a metered API. Everything runs on a laptop, Kaggle, or Colab. Storage is GitHub, Zenodo and HuggingFace, all free tiers.

**Why:** Stated budget is ₹0/month. An architecture that assumes a small monthly cost is an architecture that stops working the month it is not paid.

**Detected by:** `test_no_network_at_import` — importing `qecscreen` performs no network call. Plus a manual review item in `spec/smoke.md`.

---

### INV-10 — Publish before polishing

**Rule:** Every milestone has a **published** output, not merely a completed one. M0 ends with a public write-up within 7 days of the recorded verdict, whichever way the verdict went. M1 ends with a resolvable DOI. M2 ends with a posted preprint. A milestone whose work is finished but unshared is **not closed**, and M(n+1) may not start.

**Why:** The owner named the perfectionist trap as the specific risk to this project, and the failure mode is well understood: work continues indefinitely because it is never quite ready to show. A negative M0 result published in week 3 is worth more than a positive one published in month 9, because the first one is read and the second one is scooped. Distribution is the binding constraint on this project's value, not code quality.

**Violated by:** "I'll post it once the plots look better." Also by treating the write-up as a task at the end of a milestone rather than as an exit criterion of it.

**Detected by:** Not automatable. `INV-10-T` is a manual gate in `spec/smoke.md §6`, checked when a verdict is recorded in `spec/evals.md §7`. The verdict row for the publication criterion may be PASS only with a URL in the evidence column.

---

## Pinned conventions

Every choice below could reasonably go two ways. Each is pinned. Divergence is a bug, not a style preference.

| Concern | Decision |
|---|---|
| Matrix field | GF(2) throughout. Matrices are `numpy.uint8`, values in `{0,1}`. Never bool, never float. |
| Rank | `qecscreen.linalg.gf2_rank` only. Never `numpy.linalg.matrix_rank`. |
| Qubit indexing | 0-based. Data qubits `0..n-1`; X-ancillas then Z-ancillas follow, in that order. |
| Check matrix orientation | Rows are checks, columns are qubits. `H_X` has shape `(m_x, n)`. |
| LER units | Per round, per logical qubit. Formula in INV-4. Column `true_ler`. |
| Error rate `p` | Float, the physical error rate of the noise model. Stored to 6 decimal places. |
| Rounds `r` | `r = d_upper` (field convention, matches published BB numbers). Stored explicitly per row. The **rule** goes in `protocol_hash`, never the value — see D-014. **Provisional — revisit at M2**, see D-006. |
| Random seeds | Every generator and sampler takes an explicit `seed: int`. No implicit global RNG. |
| IDs | `construction_program_id` is a slug: `bb_v1`, `gb_v1`, `hgp_v1`. `code_id` is `{program_id}-{sha256(params_json)[:12]}`. |
| Dataset format | Parquet, one row per (code, protocol) pair. Schema version in every row. |
| Dates | ISO 8601, UTC. |
| Floats in Parquet | float64. Never store an LER as float32. |
| Metric names | `spearman_family_holdout` is the headline. `spearman_random_split` must carry the suffix. |
| Nulls | Explicit null, never `-1`, never `0`, never `NaN`-as-sentinel. |

---

## Exact values — protocol v1

Constants agents would otherwise recompute slightly differently.

```
NOISE_MODEL             = "uniform_depolarizing_v1"
  single-qubit gates and idle : depolarizing, each of X,Y,Z at p/3
  two-qubit gates (CX)        : two-qubit depolarizing, each of 15 non-identity Paulis at p/15
  reset                       : orthogonal-state preparation error at p
  measurement                 : classical flip of the outcome at p
  final data measurement      : noiseless

DECODER                 = "BpOsdDecoder"
  library               = ldpc (Roffe)
  bp_method             = "minimum_sum"
  max_iter              = 30
  ms_scaling_factor     = 0.625
  osd_method            = "osd_cs"
  osd_order             = 10

SCHEDULING              = "tanner_edge_colouring_v1"
  (BB codes additionally have "bravyi2024_8step" available; record which was used)

ROUNDS_RULE             = "r = d_upper"   # D-006. The rule is hashed, never the
                                          # concrete r (INV-6, D-014).

MIN_FAILURES            = 100          # below this the row is censored (INV-3)
MAX_SHOTS               = 200_000      # hard cap per (code, p)
SHOT_BATCH              = 10_000       # sample and decode in batches, check stopping rule between
CONFIDENCE              = 0.95         # Wilson score interval, two-sided
Z_95                    = 1.959963984540054
SCHEMA_VERSION          = 1
```

---

## Golden values

Literal, computed, and asserted in `spec/evals.md`. Do not round.

**Compare with `math.isclose(rel_tol=1e-12)`, never with `==`.** These values are reproducible to within a few units in the last place, but not bit-identically, because floating-point results depend on the order of operations and a mathematically equivalent rearrangement of the Wilson formula shifts the final digit. An exact-equality assertion here fails for a correct implementation, which trains the next agent to "fix" the golden value instead of the code — the worst possible outcome for this file.

**LER formula (INV-4)** — `logical_error_rate(P_L, r, k)`:

| `P_L` | `r` | `k` | expected `p_LER` |
|---|---|---|---|
| 0.5 | 12 | 12 | `0.004801955655646228` |
| 0.01 | 6 | 6 | `0.0002791370299384255` |
| 0.25 | 4 | 2 | `0.0353213700396906` |
| 0.0 | 12 | 12 | `0.0` |

**Wilson 95% interval** — `wilson_interval(failures, shots)`:

| failures | shots | expected low | expected high |
|---|---|---|---|
| 100 | 10000 | `0.008229336148148417` | `0.012146982255114645` |
| 1 | 1000 | `0.00017654637062607809` | `0.0056425585979579355` |

**Reference code** — the `[[72,12,6]]` bivariate bicycle code of Bravyi et al. 2024, parameters `l=6, m=6, A=x^3+y+y^2, B=y^3+x+x^2`, must satisfy `n=72`, `k=12`, `d_upper=6`, all checks of weight 6. This is the smoke test for the generator: if it does not reproduce these numbers exactly, the generator is wrong and nothing downstream is trustworthy.

---

## Never do this

- **Never call `train_test_split` on code rows** — because siblings from one construction program land on both sides and the score becomes meaningless (INV-2). Use `GroupKFold` on `construction_program_id`, or an explicit family holdout.
- **Never use `numpy.linalg.matrix_rank` on a check matrix** — because it computes rank over the reals and gives the wrong `k` over GF(2) (INV-8). Use `qecscreen.linalg.gf2_rank`.
- **Never report an LER without its shot count** — because a rate from 3 failures is not a rate (INV-3).
- **Never merge rows from two protocol hashes** — because decoder or noise differences exceed code differences and the dataset becomes noise (INV-6).
- **Never write a predicted value into a `true_` column, even temporarily** — because temporary becomes permanent and the dataset becomes fiction (INV-1).
- **Never publish a number in a README or abstract that came from a random split** — because it is 3–10× the real number and it is the first thing a reviewer will check (INV-2).
- **Never add a dependency that needs a paid tier or an API key** — because the budget is ₹0 and the project must run for a stranger who clones it (INV-9).
- **Never delete or overwrite a published Zenodo record** — because a DOI is a promise. Publish a new version.

---

## Changing this file

Requires explicit human approval. An agent proposing a change here stops and asks; it does not edit and report.
