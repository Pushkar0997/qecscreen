# decisions.md — Decision Log

Every non-obvious decision, why, and what was rejected. **This file exists to stop the next agent from re-opening a settled question or reverting a deliberate choice.**

All entries below were made during intake on 2026-08-30.

**Note:** A root-level `decisions.md` existed as a byte-identical duplicate. It was removed on 2026-08-31; this file (`spec/decisions.md`) is canonical.

---

## D-001 — Build a screening surrogate, not a decoder or a discovery agent

**Status:** decided
**Decision:** The project produces a labelled dataset and a ranking model for screening candidate qLDPC codes. It does not decode, and it does not search for codes.
**Rationale:** Both adjacent spaces are occupied by far better-resourced teams. Neural decoding has DeepMind, NVIDIA and Riverlane in it. Code discovery has IBM, MPI Erlangen and NTU, all of whom published within the last four months. The screening step is the one gap those groups have publicly named and not filled, and supplying them is a stronger position than competing with them.
**Rejected:**
- *A neural decoder* — cannot win against three funded teams with free-tier compute.
- *An LLM-guided code discovery loop* — the space closed in roughly 90 days between April and July 2026.
- *A fault-tolerant compilation tool* — owned by TUM's MQT group, Microsoft and Quantinuum; not an entry point for one person.

**Revisit if:** a group publishes a general, transferable circuit-level LER surrogate with released data before M1 closes. Then the contribution shifts to benchmarking theirs, or the project ends.

---

## D-002 — M0 is a two-week falsification, not the first slice of the build

**Status:** decided
**Decision:** The first milestone tests whether the premise is true and is designed to be able to kill the project.
**Rationale:** The riskiest assumption is not "can this be built" — it is "do cheap features carry signal Φ misses." Building four months of infrastructure before testing that is the expensive version of the same experiment.
**Rejected:**
- *Build the dataset first, evaluate later* — spends 100 core-hours before knowing whether the answer is interesting.
- *Start with the GNN* — a model cannot be evaluated without labels or splits, so this is not even orderable first.

**Revisit if:** never.

---

## D-003 — Zero recurring cost is an architectural invariant, not a preference

**Status:** decided
**Decision:** No servers, no managed databases, no paid APIs, no API keys. Kaggle and Colab for compute, GitHub and Zenodo for storage.
**Rationale:** The stated budget is ₹0/month. An architecture that assumes a small monthly cost stops working the month it is not paid, and this project has a multi-month horizon with no income attached to it. Written as INV-9 so agents do not casually propose a hosted vector database.
**Rejected:**
- *A small VPS for long-running jobs* — recurring cost, and Kaggle's 30 h/week already covers the budget in `spec/architecture.md §6`.
- *GitHub Actions for bulk data generation* — free for public repos, but it is the wrong tool, sessions are capped, and it abuses the tier.

**Revisit if:** a grant (Unitary Foundation, Deltakit) is awarded. Even then, prefer keeping the pipeline free so that a stranger can reproduce it.

---

## D-004 — The IBM Quantum Open Plan is not used

**Status:** decided
**Decision:** No part of this project runs on quantum hardware.
**Rationale:** Every label is produced by classical stabilizer simulation. Hardware access adds nothing, and the Open Plan's runtime quota would be a binding constraint if it were on the critical path. Recorded explicitly because the project owner has access and an agent might otherwise propose using it to "validate on real hardware," which would be scientifically meaningless at these code sizes.
**Rejected:**
- *Validating a few codes on real IBM hardware* — the devices cannot run a `[[72,12,6]]` memory experiment at the fidelity needed, and a partial run would produce an unpublishable number that invites the wrong questions.

**Revisit if:** never, within this project's scope.

---

## D-005 — BP+OSD with pinned parameters, not the fastest available decoder

**Status:** decided
**Decision:** `ldpc.BpOsdDecoder`, min-sum, `max_iter=30`, `osd_cs`, `osd_order=10`.
**Rationale:** Comparability with published qLDPC results matters more than speed. BP+OSD is what OmniQEC, IBM and the BB code literature report against, so our labels can be sanity-checked against theirs. Pinning the parameters is what makes `protocol_hash` meaningful.
**Rejected:**
- *BP+LSD* — faster and newer, but fewer published comparison points. Kept as the fallback if M0-EVAL-05 shows BP+OSD is too slow to fit the budget.
- *Relay-BP* — same reasoning, and less mature tooling.
- *A neural decoder* — circular. We would be measuring our own model's output.

**Revisit if:** measured per-shot cost exceeds 10 ms, per the stop rule in `spec/architecture.md §6`.

---

## D-006 — Rounds `r = d_upper`, provisional

**Status:** decided, **provisional — revisit at M2**
**Decision:** Each memory experiment runs `r = d_upper` noisy syndrome-extraction rounds, followed by a noiseless final data measurement.
**Rationale:** This is the field convention and it makes our labels directly comparable to published BB numbers, which is worth a lot for credibility and for sanity-checking the pipeline. The per-round-per-logical-qubit normalisation (INV-4) is what makes codes with different `r` comparable to each other.
**Rejected:**
- *Fixed `r = 12` for every code* — removes `d` as a confound in the label, which is arguably cleaner for a ranking task, but breaks comparability with every published number and would make the pipeline harder to validate.

**Revisit if:** M2 analysis shows the ranking is materially sensitive to the choice of `r`. If so, generate both and report both.

---

## D-007 — Splits grouped by construction program; family-holdout is the headline

**Status:** decided
**Decision:** INV-2. Random row-level splits are banned from headline claims.
**Rationale:** Codes from one polynomial template are near-duplicates. A random split lets the model memorise the template and produces an enormous, meaningless score. This is the specific way this project would fail while appearing to succeed, so it is written as an invariant with a source-grep test rather than left as good practice.
**Rejected:**
- *Random split, reported alone* — the headline number would be roughly 3–10× the honest one and it is the first thing a reviewer checks.
- *Leave-one-code-out* — does not test the thing that matters, which is transfer to structures never seen.

**Revisit if:** never.

---

## D-008 — Recall@k is the headline metric, not R² or MSE

**Status:** decided
**Decision:** Primary metric is Recall@30 of the true top-10 on a held-out family. Spearman is the continuous companion. Regression metrics are not reported as headlines.
**Rationale:** The task is screening. A user passes the top 30 of 300 candidates to expensive evaluation and cares only whether the good ones survived. A model with excellent MSE that misplaces the best code is useless; a model with mediocre MSE that reliably keeps the top 10 in its top 30 is exactly what is wanted.
**Rejected:**
- *R² / MSE* — measures the wrong thing and is the anti-metric's natural habitat.
- *Spearman alone* — a global rank correlation can look healthy while the head of the ranking, which is the only part anyone uses, is scrambled.

**Revisit if:** a target group tells us they use the surrogate differently.

---

## D-009 — Three separate Parquet files: measurements, features, predictions

**Status:** decided
**Decision:** Measurements, features and predictions live in separate files joined on `code_id`.
**Rationale:** Enforces INV-1 structurally rather than by discipline. A predicted value cannot leak into a measurement column if they are not in the same file, and features can be recomputed and versioned without touching labels that cost core-hours to produce.
**Rejected:**
- *One wide table* — simpler to read, and it makes the most dangerous bug in the project a one-line mistake.

**Revisit if:** never.

---

## D-010 — MIT for source, CC-BY-4.0 for the dataset

**Status:** **superseded by D-011.** Retained because the rejected alternatives below still stand.
**Decision:** Permissive on both.
**Rationale:** The goal is adoption by a dozen named labs, several of them industrial. Any copyleft or non-commercial term adds a legal review step between them and using it, which at this scale means they will not. Permissive also keeps commercial optionality open without pursuing it.
**Rejected:**
- *GPL* — blocks industrial adoption, which is the entire target.
- *CC-BY-NC* — same problem, and "non-commercial" is ambiguous for a research lab inside a company.

**Revisit if:** never.

---

## D-011 — Apache-2.0 for source, CC-BY-4.0 for the dataset

**Status:** decided. Supersedes D-010.
**Decision:** Source is Apache License 2.0. Any released dataset is CC-BY-4.0, licensed separately and stated as such in `NOTICE` and in every dataset card. `NOTICE` and `CITATION.cff` are maintained as first-class files, not afterthoughts.
**Rationale:** Apache-2.0 keeps the permissive adoption properties that the whole distribution strategy depends on, while adding three things MIT lacks: an express patent grant with a retaliation clause, a `NOTICE` file that downstream users are obliged to preserve, and a requirement that modified files carry prominent notices of change. That is materially better attribution machinery for the same adoption cost. It also matches the surrounding ecosystem — Qiskit and Stim are both Apache-2.0 — so a downstream user's legal review sees a licence stack it already understands.

CC-BY-4.0 on the dataset is the stronger of the two protections: attribution is a *condition of the licence*, so using the data without crediting it is a licence breach rather than a norm violation.

**Note on what this does not do:** neither Apache-2.0 nor MIT requires anyone to pay for commercial use. Licence choice buys credit, not compensation. Compensation for this project runs through grants (Unitary Foundation microgrant, Riverlane Deltakit fund) and through the academic value of citations, both of which *require* an open licence. See D-012 for the alternative that was considered and rejected.

**Rejected:**
- *MIT* — fine, but strictly less attribution machinery for identical adoption. No reason to prefer it here.
- *GPL / AGPL as a single licence* — blocks the industrial labs in `spec/product.md §3`, who are the target.
- *CC-BY-NC on the dataset* — "non-commercial" is ambiguous for a research lab inside a company, so those groups avoid it entirely.
- *All rights reserved* — forfeits Zenodo deposition, grant eligibility, and the entire adoption channel, in exchange for control that copyright already provides.

**Revisit if:** the project pivots from research infrastructure toward a commercial product. See D-012 for what that would require.

---

## D-012 — Dual licensing considered and deferred, but kept possible

**Status:** decided (deferred, not closed)
**Decision:** Do not dual-license now. Preserve the ability to do so later by requiring that every external contributor signs off under the Developer Certificate of Origin, and by not merging any contribution that would fragment copyright ownership without an explicit agreement.
**Rationale:** Dual licensing — AGPL-3.0 publicly plus a paid commercial licence — is the only mechanism that actually extracts payment from commercial users. It was rejected for now because it would cost the four named target groups, the grant eligibility, and the citation pathway, which together are worth far more at this stage than hypothetical licence revenue from a project with no results yet.

The option only survives if **the copyright stays consolidated**. Once a third party contributes non-trivially under Apache-2.0 without a contributor agreement, relicensing requires their permission, and the option quietly dies. That is why the DCO requirement exists now rather than later — it costs nothing today and is impossible to retrofit.

**Rejected:**
- *Dual-license from day one* — pricing and negotiating a commercial licence for an unvalidated pilot is effort spent on the wrong milestone entirely, and it advertises commercial intent to exactly the academic groups whose adoption is the goal.
- *No contributor policy at all* — cheapest today, forecloses the option permanently.

**Revisit if:** a company approaches about commercial use, or the project acquires a result substantial enough that licence revenue is plausible.

---

## D-013 — Private through M0, public from M1

**Status:** decided; on visibility, superseded by D-030 (the repo went public during M0)
**Decision:** The repository stays private until the M0 verdict is recorded in `spec/evals.md §7`. It goes public at the start of M1, or at the moment a negative M0 result is published, whichever comes first.
**Rationale:** M0 may kill the project and there is no reason to publish an unvalidated pilot. From M1 onward, every mechanism the plan depends on — Zenodo DOI, grant applications, adoption by the named groups, citations — requires a public repository. Privacy is a temporary state with a defined exit, not a posture.

**This does not weaken INV-10.** The M0 write-up publishes within 7 days of the verdict regardless of whether the repo itself is public yet. A private repo is not a reason to delay the write-up; if it were, it would become one.

**Rejected:**
- *Public from day one* — an empty repo with no result is a weaker first impression than no repo.
- *Private indefinitely* — see D-011's rejected list; nothing in the plan works.

**Revisit if:** never. The exit condition is written above.

---

## D-014 — `protocol_hash` records the rounds *rule*, not the value of `r`

**Status:** decided
**Decision:** The `rounds_rule` string (`"r = d_upper"`, per D-006) is part of `protocol_hash`. The concrete number of rounds `r` is **not** — it stays a per-row stored column. Separately, `Protocol.decoder_version` loses its `"unset"` default and becomes a required field, populated from the installed `ldpc` version at call time.
**Rationale:** INV-6 originally hashed `r` itself. Because D-006 sets `r = d_upper`, and `d_upper` varies from code to code, every distinct distance produced a distinct `protocol_hash` — so `assert_single_protocol()` raised on any frame containing codes of different distance. That is *every* legitimate cross-code ranking, which is the single metric M0 exists to produce; `M0-RUN-04` could not have run. The bug was in CONTRACT, not in the code that obeyed it.

Hashing the rule preserves what INV-6 is actually for — two rows share a hash exactly when they were measured under the same recipe — while letting `r` vary as that recipe says it should. INV-4's per-round-per-logical-qubit normalisation is what makes rows with different `r` comparable in the first place, so the concrete value carries no comparability information the normalisation has not already handled.

On `decoder_version`: a default of `"unset"` meant a hash could be produced that claimed to encode the decoder version and did not. Two runs on different `ldpc` versions would hash identically — precisely the silent incomparability INV-6 exists to prevent.

**Rejected:**
- *Drop rounds from the hash entirely* — the obvious fix, and wrong. A fixed-`r = 12` dataset and a variable-`r = d_upper` dataset would then hash identically while being incomparable, so the hash would stop detecting a real protocol difference. The choice of rounds rule **is** a protocol decision; only the per-code value is not.
- *Keep `r` in the hash and relax `assert_single_protocol` to ignore it* — pushes the exception into every call site, so the guard weakens wherever someone forgets to apply it. INV-6's value comes from being unconditional.
- *Fix `r = 12` for every code so the value is constant* — already rejected in D-006 for breaking comparability with published BB numbers; it would trade a bookkeeping problem for a scientific one.
- *Leave `decoder_version` defaulted and fill it by convention* — conventions are not enforced, and the field is load-bearing for INV-6.

**Revisit if:** D-006 is revisited at M2. If `r` becomes fixed, `rounds_rule` changes value and `protocol_hash` changes with it — which is correct, because labels genuinely are not comparable across that change.

---

## D-015 — Dependency upper bounds track the execution environment, not the dev box

**Status:** decided; **the `pyarrow` half is superseded by D-019** (the `<19` cap is removed — see D-019 for why). The `pandas<3` cap and the general principle below are unaffected and still stand.
**Decision:** `pandas` is capped at `<3` and `pyarrow` at `<19`, matching what Colab actually ships (2.2.3 and 18.1.0). Generally: where a **data-path** dependency is materially newer on the development machine than on the machines that will run the generation, the requirement is capped to the execution environment and the dev machine is brought down to meet it — never the reverse.
**Rationale:** The M0-SETUP-01 Colab run measured a target environment's stack for the first time, and it is much older than the dev box — `pandas` 2.2.3 vs 3.0.5, `pyarrow` 18.1.0 vs 25.0.1. Development was therefore happening on a `pandas` **major version that the machine doing the bulk generation has never executed**.

That gap does not fail fast. `pandas` 3 changed default dtypes and null handling, and `pyarrow` is the Parquet engine; a divergence surfaces as a dtype or schema difference at M1, hours into a Kaggle job, in a shard that is already half written. CONTRACT's nulls convention — "explicit null, never `NaN`-as-sentinel" — is precisely the behaviour that differs across a `pandas` major, so this is not a hypothetical class of bug for this project.

Colab (Python 3.13) is the newer of the two target environments, so capping at Colab's versions is *expected* to be safe for Kaggle too. Expected, not measured — see the revisit condition.

**Rejected:**
- *Lower bounds only, and rely on discipline* — this is what was in place. It silently produced a two-major-version gap that nobody noticed until a Colab log was read line by line.
- *Cap everything at Colab's exact versions* — over-constrains. `numpy` (2.1.3 vs 2.5.2), `scipy` (1.16.3 vs 1.18.1) and `scikit-learn` (1.6.1 vs 1.9.0) differ only *within* a major. Tightening those would start forcing downgrades of a preinstalled stack for no measured benefit, which breaks the one-cell install (`spec/smoke.md §1`).
- *Cap `pytest` at `<9`* — considered and rejected, even though the gap is a full major (Colab 8.4.2, dev 9.1.1). `pytest` is a development tool, not a data-path dependency, and a runner mismatch fails loudly at test time rather than silently inside a Parquet file. Both versions are known to pass this suite.
- *Pin exact versions* — forces a downgrade of whatever the host already has, which is the failure mode this decision exists to avoid.

**Revisit if:** **Kaggle is measured.** Kaggle has never been run, and it is the workhorse for bulk generation. If it ships `pyarrow` ≥19 or `pandas` ≥3, these caps would force a downgrade *there* — the very thing they exist to prevent — and must be raised. Run `notebooks/verify_env_colab.ipynb` on Kaggle before the M1 bulk run. Also revisit whenever a target environment's version of a data-path dependency overtakes its cap.

---

## D-016 — M0 physical error rate pinned at `p = 0.005`

**Status:** decided
**Decision:** The M0 pilot runs at a single physical error rate `p = 0.005`, recorded as `P_PILOT` in `CONTRACT.md`'s exact-values block.
**Rationale:** The BB `[[72,12,6]]` code's circuit-level threshold under uniform depolarising noise with BP+OSD is approximately 0.7%. `p = 0.005` sits below that threshold, so the reference code is expected to produce a measurable but non-trivial LER — strong enough that the censoring rule (INV-3, `MIN_FAILURES = 100`) is reachable within `MAX_SHOTS = 200,000` for most of the candidate set, while weak enough that good codes are clearly separated from bad ones in the ranking. This value was already the implicit planning figure in `spec/architecture.md §6` (the table's "typical pilot code at p=0.005" row), and in `protocol.py`'s `_protocol()` test helper, but was never formally pinned — and `AGENTS.md §4` forbids inventing values.

**Rejected:**
- *A lower `p` (e.g. 0.001)* — pushes more codes toward the `MAX_SHOTS` cap without reaching `MIN_FAILURES`, inflating the censoring rate. `plan.md`'s M0 exit criteria already guard against exactly this: if >40% of rows are censored, the chosen `p` was wrong and the pilot must be re-run at a higher `p`. A `p` that is lower than necessary increases the chance of triggering that re-run for no scientific benefit at M0.
- *A higher `p` (e.g. 0.01)* — above threshold for the reference code, so the label for the best-known code becomes uninformative. Rankings lose resolution at the interesting end.
- *Multiple values of `p`* — deferred to M1. M0 is single-`p` by design (D-002, `plan.md` scope discipline). Each additional `p` multiplies the compute budget and adds no information to the M0 question ("do cheap features beat Φ").

**Revisit if:** M0-RUN-03 shows the censoring rate exceeds 40% at this `p`, per the exit criteria in `plan.md`. In that case raise `p` and regenerate, recording the change as a new `protocol_hash`.

---

## D-017 — `commit_sha` is a required row column, sourced from `provenance.resolved_commit()`

**Status:** decided
**Decision:** Every measurement row stores `commit_sha`: the exact git commit of the code that produced it, read via `qecscreen.provenance.resolved_commit()` at run time. Required on every row, never null, never a placeholder. It is not part of `protocol_hash` (INV-6) — it is a separate stored column.
**Rationale:** `protocol_hash` alone cannot identify the code that produced a row. It hashes the noise model, `p`, the rounds rule, decoder name/version/parameters, scheduling method and schema version — the measurement recipe — but says nothing about which version of *this project's own source* executed that recipe. Two rows can carry an identical `protocol_hash` while one was generated before a bug fix (in, say, the scheduling or censoring logic) and one after, and without a recorded commit that difference is invisible and unattributable when a discrepancy is found later. `resolved_commit()` must read what is actually installed and importable at run time, not echo a value asserted elsewhere.
**Rejected:**
- *Trust the notebook's pinned SHA* — a cell like `!pip install git+...@<sha>` records what the notebook author intended to install, not what pip actually resolved and installed. A stale cache, a ref that silently resolves to a moving branch HEAD rather than the pinned commit, or a partially re-run cell can leave the running code different from the pin, and nothing would catch it. Verifying against the installed package, rather than trusting the pin, is the entire point of the decision.

**Revisit if:** never — this is provenance bookkeeping, not a protocol decision, so it does not vary the way D-006 or D-014 do.

---

**Cleanup, 2026-09-13:** Deleted the duplicate `NOTICE.txt`, keeping `NOTICE` — Apache-2.0 §4(d) and licence scanners expect that exact filename. Closes the duplication flagged in `AGENT_LOG.md` (v) and (w). Not a numbered decision.

---

## D-018 — "No from-source build" replaced by "no C toolchain invoked during install"

**Status:** decided
**Decision:** The M0 environment exit criterion in `spec/smoke.md §1` and the corresponding row in `spec/evals.md §7` is restated from "no from-source build" to **"no C toolchain invoked during install"**. This is a change to the criterion itself, checked mechanically by the CI compiler grep added in `cf5542e`.

**Rationale:**
- The original criterion was a proxy for "needs a compiler", per `AGENT_LOG.md` (n).
- `sinter` 1.16.0 is sdist-only on every Python version, pure Python, no compiler. It builds in one cell on both Colab and Kaggle.
- The replacement is mechanically checked by the CI compiler grep added in `cf5542e` and validated against five logs. The old `--only-binary=:all:` flag tested nothing of the sort and silently pinned CI to `sinter` 1.15.0.
- This is recorded explicitly as a criterion change, not a re-measurement, and it is accepted only because the replacement is checked in CI while the original never was.

**Rejected:**
- *Keep the literal wording* — carries a permanent FAIL on a criterion nobody intends to satisfy, which makes §7 unreadable.

**Revisit if:** never — this retires a proxy criterion in favour of the mechanical check it was always meant to express; it does not vary the way a protocol decision would.

---

## D-019 — Remove the `pyarrow` upper bound

**Status:** decided. Supersedes the `pyarrow` half of D-015; D-015's `pandas<3` cap and general principle are unaffected.
**Decision:** `requirements.txt` changes from `pyarrow>=15,<19` to `pyarrow>=15` — the upper bound is removed, not raised.
**Rationale:** The `<19` cap was set on 2026-08-30 from Colab's then-ambient `pyarrow` 18.1.0 (D-015). Both target platforms have since moved past it: Colab now ships 23.0.1, Kaggle ships 24.0.0. The cap therefore forces a downgrade on *every* runtime it is supposed to protect, and that downgrade breaks `datasets` (both platforms, needs `pyarrow>=21`) and `bigframes` (Colab, needs `pyarrow>=23.0.1`) — measured 2026-09-14 on factory-reset Colab and Kaggle runtimes, install logs captured. Nothing in this project depends on `pyarrow` internals: rows are `float64` and strings, and the Parquet format itself is stable across 15–24.
**Rejected:**
- *Raise the cap to `<25`* — fixes today's measurement and re-breaks the next time either base image moves, which they have now demonstrably done once already inside three weeks. A cap re-derived from a snapshot of a base image nobody controls is not a fix, it is a countdown.

**Revisit if:** a future measurement shows a `pyarrow` release actually breaking this project's Parquet read/write path (a schema or dtype incompatibility, not merely a version bump) — at that point cap against the specific breaking behaviour, not against an arbitrary ambient snapshot.

---

## D-020 — Add Python 3.12 to the CI matrix

**Status:** decided
**Decision:** `.github/workflows/ci.yml`'s Python matrix gains `3.12`, alongside the existing `3.11` and `3.13`. `spec/architecture.md §1`'s interpreter row is updated to state all three and why.
**Rationale:** Measured 2026-09-14: Kaggle — the intended bulk-generation host and the workhorse per `AGENTS.md §7` — runs Python **3.12.13**, not 3.13 as the stack table previously implied by omission. Colab runs 3.13.15. CI tested only 3.11 and 3.13, so the interpreter that will actually run the M1 bulk generation has never been tested by CI.
**Rejected:**
- *Drop 3.11 to keep the matrix at two entries* — 3.11 has its own justification independent of this decision (recorded where the matrix was introduced) and dropping it trades one untested target interpreter for another.

**Revisit if:** Kaggle's or Colab's shipped interpreter version changes at the platform level; re-measure and update the matrix to match, the same way this decision was reached.

---

## D-021 — `estimate_d_upper`'s method and default `attempts`, measured

**Status:** decided
**Decision:** `qecscreen.codes.distance.estimate_d_upper` uses a random-information-set search (`METHOD_NAME = "random_information_set_v1"`), with `DEFAULT_ATTEMPTS = 64`.
**Rationale:** A first implementation — draw one random dense combination of the `ker(H_X)`/`ker(H_Z)` nullspace basis, then greedily flip in single stabiliser generators while that reduces Hamming weight — failed the [[144,12,12]] gross-code reference check even at 5,000 attempts, returning 14 instead of the published 12. It is a real algorithm, not a bug, but too weak a local search for a code this size: single-generator greedy descent from a random dense (roughly half-weight) starting vector gets stuck in a local minimum well above the true minimum.

Replaced with random-information-set search: draw a random column permutation, use it to select fresh pivot columns when row-reducing the same nullspace basis, and read off the minimum-weight nontrivial row across all attempts. Measured directly, 30 seeds each, on both reference codes:
- [[72,12,6]]: reaches `d_upper=6` reliably from `attempts=1`.
- [[144,12,12]] (the binding constraint): `attempts=3` is unreliable — 25/30 seeds correct; `attempts=4` is reliable — 30/30 seeds correct, and stayed 30/30 at 5 and 6.

`DEFAULT_ATTEMPTS=64` is set at 16x the measured reliability threshold (4), for margin against a code this project hasn't sampled yet needing more attempts than either reference code. Measured wall-clock at that default (20-seed average, dev box): ~0.10 s/call for the gross code, ~0.05 s/call for the [[72,12,6]] code — negligible next to the ~100 s/code BP+OSD decoding budget in `spec/architecture.md §6`, which is unaffected by this number.

**Rejected:**
- *Keep the greedy-descent method and just raise attempts further* — at 5,000 attempts it was still 2 short of the published distance (14 vs 12) with no sign of closing the gap quickly; the method's local-search neighbourhood (single-generator flips from a random dense start) is the limitation, not the attempt count.
- *Call into `ldpc`'s own distance-estimation utilities* — `ldpc` is already a pinned dependency, but the task explicitly scoped this module to `numpy` only; revisit if that constraint is ever lifted.

**Revisit if:** a future construction program (GB, HGP, TB — M1) needs more than 64 attempts to reliably match a published reference distance; re-measure per family rather than assuming this default generalises.

---

## D-022 — `sample_bb_params`'s template set, and why some shapes are structurally excluded

**Status:** decided
**Decision:** `qecscreen.codes.sample.TEMPLATES` holds 10 polynomial shapes, each verified to have a nonzero success rate against `qecscreen.codes.validate.validate` across the full `l, m in [2, 19]` grid under `budget=150`, before being kept. `construction_program_id = f"bb_v1_{template_name}"` — one level more specific than the bare `bb_v1` shown as CONTRACT.md's illustrative example for the family, because two structurally unrelated polynomial shapes sharing a family-level id would still let INV-2's split-grouping mix near-duplicates from one shape with genuinely different codes from another; `AGENTS.md §6`'s own vocabulary entry for "Construction program" already names "the BB polynomial template" as the unit, one level below family.
**Rationale:** While building the template set, three candidate shapes — each with a single-monomial side (e.g. `B = x*y`, one term) — turned out to fail `validate()`'s `k >= 1` check for **every** `(l, m)` tried, not merely most. The reason is structural, not bad luck: a single-monomial polynomial is itself an invertible permutation matrix, which forces `rank(H_X) = rank(H_Z) = l*m` regardless of the other polynomial, which forces `k = 0` identically. Giving both sides of those three shapes a second term did not fix it — two of the three replacements *also* failed for every `(l, m)` tested, for reasons tied to the specific polynomials' algebraic structure (not the simple single-monomial rule) that a full explanation would require deriving the polynomials' relationship to `x^l - 1` and `y^m - 1` in the underlying group ring. Rather than chase that theory under an M0 time budget, every template actually shipped was instead verified empirically against the grid before being kept — three replacement shapes were found this way with nonzero (9%-100%) yield, and are what appear in `TEMPLATES` now.
**Rejected:**
- *Derive a general rule for which shapes are viable and filter algorithmically* — the single-monomial case has a clean, provable rule; the second failure mode encountered here evidently does not have an equally simple one reachable in the time available, and getting this wrong silently (a plausible-looking rule that still admits a some-but-not-all-viable shape) is worse than the grid-verification actually used, which cannot be fooled by a rule not covering some case.
- *Keep the always-failing shapes in `TEMPLATES` anyway, relying on `sample_bb_params`'s reject-and-redraw loop to route around them* — technically works (rejection sampling correctly wastes attempts on them and moves on) but wastes an unbounded fraction of every draw's attempt budget forever, and silently normalises shipping a template that can never contribute a single code — worth catching once here rather than leaving as permanent overhead.

**Revisit if:** a future construction program's shape needs the same grid-viability check; reuse the method (verify across the target budget's `(l, m)` grid before adding to a template list) rather than assuming a new shape works from inspection alone.

---

## D-023 — `sample_bb_params` allocates codes evenly across templates, with distinct `(l, m)` per template

**Status:** decided
**Decision:** `sample_bb_params(n_codes, budget, seed, balanced=True)`. With `balanced=True` (the new default), `n_codes` is split evenly across `TEMPLATES` (remainder assigned by a seeded permutation), and each template fills its quota by walking its own seeded, weighted, without-replacement ordering of the `(l, m)` grid (weights match the `balanced=False` `l`-then-`m` draw, so the `n` distribution stays comparable). Codes within a template are therefore distinct. A template that runs out of valid pairs before its quota is marked **exhausted** and the shortfall is redistributed evenly to the templates still open, repeating until the list is full; if every template is exhausted first, `RuntimeError` — never a shorter list. The return value is a `BBSample` (a `list` subclass, so existing callers and `==` are unaffected) carrying `counts`, `quota`, `exhausted`, `attempts`, `rejections`. `balanced=False` reproduces the M0-CODES-05 sampler exactly (same list, pinned by `test_unbalanced_unchanged_from_m0_codes_05`).
**Rationale:** Measured on the M0-CODES-05 sampler, 300 codes at `budget=150`, `seed=0`: `pair_2_2` 70, `quad_4_4` 69, `quad_4_2` 63, `quad_2_4` 61, `mod_2_3` 21, `sym_3_3` 8, `rare_2_3` 6, `mixed_3_5` 1, `rare_3_4` 1, `mixed_5_3` **0** — four templates held 263/300 (87.7%), max/mean 2.33. Uniform template draws against per-template yields of 9%-100% cause this. INV-2 groups splits on `construction_program_id`, so the family holdout collapsed to roughly four effective folds, with singleton test groups. The same draw also held **95 exact duplicate codes** (same template, `l`, `m`): duplicates stay inside one group, so they do not leak, but they inflate a group's weight with no new information and would cost labelling CPU for nothing. Measured at `budget=150`, the number of distinct valid `(l, m)` pairs per template (out of 189 on the grid) is: `pair_2_2`, `quad_4_2`, `quad_2_4`, `quad_4_4` 189 each; `mod_2_3` 62; `sym_3_3` 20; `rare_3_4`, `rare_2_3`, `mixed_3_5`, `mixed_5_3` 17 each. So every template is viable at 150, and five cannot fill a quota of 30 with distinct codes. The same draw after this change (`balanced=True`): five templates capped at 17-20 (exhausted), the other five at 42-43; max/mean 1.43, min 17, 300 distinct codes, `k <= 4` fraction 0.57 (was 0.79), 1240 `validate()` calls / 940 rejected, 2.5 s wall-clock (was 1.6 s).
**Rejected:**
- *Balance quotas but allow duplicate `(l, m)` within a template* — every template would reach exactly 30, but the five low-yield ones would do it by repeating ~17 codes, which would give them the look of balance without the substance. It would also make "can't fill its quota" nearly impossible to detect, since any template with even one valid pair can fill any quota with copies.
- *Weight template draws by inverse measured yield* — needs yields that are budget-specific and would need re-measuring whenever the budget or template set changes; the balance it achieves is only in expectation, not per draw.
- *Bound each template by an attempt timeout instead of the finite grid* — "exhausted" would then be a guess from a timeout rather than a fact. The grid at any budget is finite and small (189 pairs at 150), so walking it without replacement makes exhaustion exact and the attempts bounded by construction.
- *Change the return type to a separate result object* — would break every existing caller for the sake of the metadata; a `list` subclass carries it without that.

**Revisit if:** the template set or budget changes enough that most templates are exhausted (redistribution would then pile codes onto the few with large grids — check `BBSample.counts`), or if the M0 grid expands to more construction families, where the same per-program balance question applies across families as well as within one.

---

## D-024 — Template set corrected for duplicate programs and d <= 2 codes; `d_upper >= 3` admission rule

**Status:** decided (amends D-022's template list; D-023's allocation unchanged)
**Decision:**
1. **Removed three templates.** `quad_2_4` and `mixed_5_3` were exact A/B swaps of `quad_4_2` and `mixed_3_5`. `quad_4_4` had `A == B`.
2. **Added four templates**, giving 11 in total: `bb288_3_3` (the [[288,12,18]] shape from Bravyi et al.), `tri_3_3`, `diag_3_3` and `sq_4_2`. Each must have at least 10 distinct `(l, m)` at `budget=150` that pass both `validate()` and rule 3, measured on the full 189-pair grid as D-022 did. It is also checked against every other template for A/B-swap identity by generating the codes.
3. **Admission rule.** `sample_bb_params` emits a code only if `estimate_d_upper(h_x, h_z, seed=0) >= MIN_D_UPPER = 3`, with the default attempts from D-021. Rejections are reported by cause, `k<1` or `d_upper<3`.
4. **Uniqueness.** `template_key(a_exps, b_exps)` gives the canonical form of a template under A/B swap and under shifting each polynomial by a monomial. No two `TEMPLATES` may share a key.

**Why renames and removals are allowed now:** no labelled row exists yet. Nothing has been generated, sampled, decoded or written to Parquet, so no stored `construction_program_id` refers to a removed template. After the first labelled row exists, removing or renaming a template changes the ids of stored rows, and INV-2 grouping over those rows silently breaks. From then on the only acceptable fix is a new id alongside a superseding decision.

**Rationale:**
- **A/B swap is the same program.** `[B|A]`, `[A^T|B^T]` become `[A|B]`, `[B^T|A^T]` when the two qubit halves are exchanged, at every `(l, m)`. So each swapped pair was one construction program under two ids, which is an INV-2 leak: near-duplicates on both sides of a family-holdout split.
- **Monomial shifts are the same program too.** Replacing `(A, B)` with `(Ag, Bh)` for monomials `g`, `h` permutes the qubits within each half, so the code is the same. `template_key` covers this as well; this was not in the owner's report, and none of the templates collided under it.
- **`A == B` forces d <= 2.** With `H_X = [A|A]`, `Z_i Z_{i+lm}` commutes with every X check. Whenever `k >= 1`, some such pair is not a stabiliser. Measured: `quad_4_4` had `k >= 1` at all 189 grid pairs, and **every one** had `d_upper <= 2` (188 at 2, one at 1). That means 69/300 codes in the M0-CODES-05 draw, and 42/300 in D-023's balanced draw, were d <= 2 codes from this one template.
- **d <= 2 codes don't belong in a screening dataset.** They correct no errors, so any method ranks them last trivially, and they inflate rank correlation for every screening method alike, the incumbent proxy included.
- **Why the rule uses `estimate_d_upper`.** It is an upper bound, so in principle it can miss a weight-2 logical. On the grid it never did: an exact search for weight-1/2 logicals (column pairs with equal syndromes, checked against the stabiliser row space) agreed with `d_upper <= 2` on **every** k >= 1 code screened, 0 disagreements across all templates.
- **Measured fraction rejected by the rule, per template, over the budget=150 grid:** `diag_3_3` 47/104, `sq_4_2` 55/189, `rare_2_3` 7/17, `rare_3_4` 5/17, `pair_2_2` 4/189, `mod_2_3` 2/62, and 1 each for `sym_3_3`/20, `quad_4_2`/189, `bb288_3_3`/20 and `tri_3_3`/20; `mixed_3_5` 0/17. Admissible pairs per template: `quad_4_2` 188, `pair_2_2` 185, `sq_4_2` 134, `mod_2_3` 60, `diag_3_3` 57, `sym_3_3`, `bb288_3_3` and `tri_3_3` 19 each, `mixed_3_5` 17, `rare_3_4` 12, `rare_2_3` 10.
- **Measured, reported rather than asserted:** under x↔y exchange, alone or combined with A/B swap, no template matches any other (generated at `l = m = 7`, row-space comparison after the corresponding qubit permutation). This is a real program-level equivalence too: the x↔y image of a template at `(l, m)` is the template at `(m, l)`, and the budget grid is symmetric. It just has no instances in the current set. Several templates are self-symmetric under it (e.g. `sym_3_3` under x↔y+AB), which is harmless.
- **`bb288_3_3` is not `sym_3_3` in disguise.** It shares `sym_3_3`'s B and viable-lattice count (20), so I compared per-lattice `(k, d_upper)` fingerprints. They differ, e.g. `(3, 18)` gives d_upper 10 vs 6. `tri_3_3` differs from both in k.

**Rejected:**
- *Keep `quad_4_4` and rely on the admission rule to reject its codes* — it would never emit a single code, and would permanently waste its share of every draw's attempts. D-022 already rejected shipping a template that can never contribute.
- *Deduplicate at the id level, e.g. map `quad_2_4` to the id `bb_v1_quad_4_2`* — two exponent lists for one program would stay in the list, and the balanced allocator would give that program two quotas.
- *An exact-distance admission rule* — the exact weight-≤2 search agreed with `d_upper` everywhere it was measured, so it adds cost and a second code path for no measured gain. Revisit if a future family disagrees.
- *Include x↔y in `template_key` now* — mathematically justified, but the owner asked to measure it rather than assert it, and there are no instances. See Revisit.

**Consequence for D-023:** `test_unbalanced_unchanged_from_m0_codes_05`, which pinned `balanced=False` to the M0-CODES-05 draw, is removed. That draw came from a template set that no longer exists and contained no d ≤ 2 filter. `balanced=False` keeps its algorithm (uniform template draw, reject-and-redraw) but not its old output.

**Revisit if:** a template is added. Then extend `template_key` to x↔y exchange, since the equivalence holds and the owner's measurement found only that no current pair triggers it. Also revisit if the budget changes: `rare_2_3` sits exactly at the 10-admissible-pair bar at 150. Or if another family (GB, HGP) is added: re-derive that family's own equivalences, because these are specific to the BB construction.

---

## D-025 — Circuit protocol v1: Z memory, pinned noise placement, monomial-matching schedule

**Status:** decided (owner, 2026-09-25). Memory basis and schedule are **provisional — revisit at M1**.
**Decision:** Five linked choices that together fix what one label measures.

1. **Memory basis: Z only.** Data prepared in `|0…0⟩`, final data measurement in Z, observables are `k` Z-logical operators. `memory_basis = "Z"` is a new `protocol_hash` field (INV-6). The label is a **Z-memory LER**, stated in INV-4, the pinned conventions, `AGENTS.md §6` and the `true_ler` schema row.
2. **Noise placement in `uniform_depolarizing_v1`.** Native `RX`/`MX` for X-type ancillas, so the circuit has no single-qubit gates and CONTRACT's "single-qubit gates and idle" line covers idles only. `DEPOLARIZE1(p)` on every qubit not acted on in a tick. `DEPOLARIZE2(p)` after every CX. `X_ERROR(p)` after `R`, `Z_ERROR(p)` after `RX`. `M(p)`/`MX(p)` classical flips. Initial data preparation and final data measurement are **noiseless**. Tick layout per round: one reset tick (all ancillas), the X-phase CX ticks, the Z-phase CX ticks, one measurement tick (all ancillas). Data qubits idle in the reset and measurement ticks, and each ancilla type idles through the other type's phase.
3. **Scheduling: `bb_monomial_matching_xz_phased_v1`**, which replaces `tanner_edge_colouring_v1`. X checks in one phase, then Z checks, never interleaved. Each monomial of `A` or `B` is a permutation matrix, so it is a perfect matching between the `lm` ancillas and one data block. One CX tick per monomial. X phase: `A`'s monomials (data block `0..lm-1`), then `B`'s (block `lm..2lm-1`), each in stored `a_exps`/`b_exps` order, CX ancilla → data. Z phase: `B^T`'s monomials (block `0..lm-1`), then `A^T`'s (block `lm..2lm-1`), same order, CX data → ancilla. Depth `|A| + |B|` per phase (12 per round for weight-6 BB), which is the König minimum (max Tanner-graph degree). Deterministic, with no colouring strategy to pin.
4. **Rounds:** `r = d_upper` noisy rounds **in total, the first included** (D-006, INV-4). No extra noiseless round.
5. **Observables:** the `k` Z logicals are derived deterministically. Take `gf2_nullspace(H_X)` rows in order and keep each one that raises the GF(2) rank of `H_Z` stacked with the kept rows. No RNG. Failure is "any observable flipped" per INV-4, which does not depend on basis.

**Rationale:**
- *Basis.* For BB codes `H_Z = [B^T|A^T]` is `H_X` with halves swapped and transposed, so X memory mirrors Z memory, and running both would double decode cost to measure the same thing. That symmetry does not hold for HGP/GB, hence the M1 revisit.
- *Noiseless boundaries: the reason that matters most.* `r` varies by code (`r = d_upper`). Noise at the boundaries (state preparation, final readout) happens once per experiment, not once per round. After INV-4 divides by `r`, it is diluted more for high-distance codes than for low-distance ones. That biases the per-round rate by distance, which is exactly the ranking this project measures. Noiseless boundaries at both ends keep all noise inside the `r` rounds that INV-4 normalises. (Symmetry with D-006's noiseless final measurement is a weaker, secondary reason.)
- *Phased schedule.* Within one check type all CXs point the same way and commute, so their order cannot change what is measured. Interleaving X and Z checks in an arbitrary order can measure something other than the stabilisers. Greedy networkx line-graph colouring (the original M0-CIRC-01 wording) would add a strategy parameter to pin and may exceed the König minimum. The BB group-algebra structure gives an optimal schedule for free.

**Free only because no labelled row exists yet.** Changing the basis, noise placement or scheduling string after labels exist would invalidate every one of them (the `protocol_hash` changes). These changes cost nothing on 2026-09-25 because the dataset is empty.

**Rejected:**
- *X and Z memory both.* Twice the decode budget, plus a rule to combine two `P_L` into INV-4's single one that CONTRACT does not give.
- *`R` + `H` for X ancillas.* Adds single-qubit gate noise sites for no benefit, and makes the gate line of the noise model apply to something.
- *Noisy initial preparation.* Distance-dependent dilution bias, see above.
- *Interleaved X/Z schedule (e.g. `bravyi2024_8step`).* Correct only for a specifically verified order. Still available for BB under its own string if ever wanted.
- *networkx greedy edge colouring.* Strategy-dependent, and not guaranteed minimal.

**Revisit if:** M1 adds families without BB's X/Z symmetry (basis) or without group-algebra structure (schedule: needs a general, verified bipartite edge colouring under a new string).

### D-025 amendment (2026-09-25) — ancilla timing

**Status:** decided (owner, 2026-09-25). Replaces the tick layout in item 2; every other D-025 choice is unchanged.
**Decision:** Per round: reset X-ancillas → X phase → [measure X-ancillas + reset Z-ancillas, one tick] → Z phase → measure Z-ancillas. The Z readout of round `t` shares a tick with the X reset of round `t+1`, and the last one shares the tick of the noiseless data readout, so a round stays `2(|A|+|B|) + 2` ticks: no added depth, and data qubits still idle exactly twice per round. `DEPOLARIZE1(p)` still goes on every qubit not acted on in a tick. For an ancilla that now only happens between its readout and its next reset, where it cannot change any outcome (the detector error model is identical with those idles stripped, which a test asserts).

**Rationale:**
- *Measurement error on the Z checks.* In the original layout the Z-ancillas were reset at round start and idled in `|0⟩` through the whole X phase before their first CX. Each idle tick flips them with probability `2p/3`, adding about `(|A|+|B|) · 2p/3` measurement error to the Z checks, and in Z memory those are the checks that protect the observables. (X-ancillas idled through the Z phase too; that matters far less in Z memory.)
- *Feature leakage, the reason this could not wait.* The X-phase length is `|A|+|B|`, which varies by template, so that penalty correlated with check weight, a planned cheap feature. A model could learn "heavier checks → worse label" from a circuit artefact instead of from code quality. That is a screening signal manufactured by the label pipeline.
- **Free only because no labelled row exists yet.** Like D-025 itself, this changes every label; on 2026-09-25 the dataset is empty, so it costs nothing. The scheduling string and noise-model name are unchanged (owner instruction: keep every other D-025 choice), so rows built before and after this amendment would share a `protocol_hash`. None were built before.
- **Scheduling string renamed to `bb_monomial_matching_xz_phased_v2` (owner, 2026-09-25, follow-up).** Supersedes the "unchanged" sentence above. **A change that alters labels must change `protocol_hash`, with no exceptions** — including a change the owner considers a correction rather than a new protocol, and including one where "no row exists" makes it look moot. The ancilla timing is part of what the scheduling string names, so the string moves to `_v2`, and a circuit built from any pre-`5f1ee3b` commit now hashes differently from one built after it. The rename itself is free **only because no labelled row exists**; after the first row is written, the same rename would orphan it, which is exactly what it should do. Owner authorisation covered the `SCHEDULING` line of `CONTRACT.md` and `protocol.py` only. The noise-model name `uniform_depolarizing_v1` is not renamed: the channels and their rates did not change, only when the ancillas are reset and read, which is scheduling.

**Measured on [[72,12,6]], r = 6:** ticks per round 14 before and after (86 in the circuit, both). Ancilla idle ticks while holding syndrome, per round: 432 before (216 of them between reset and first CX), 0 after. Detectors 432 and DEM error mechanisms 15,840, both unchanged.

**Rejected:**
- *The same order with a separate final Z-measurement tick per round.* One extra tick per round, and one extra data idle per round (`n · p` more depolarising noise each round), which is the added depth the owner excluded.
- *A separate closing tick for the last Z readout, before the data readout.* One data idle outside the rounds, i.e. boundary noise, which D-025 excludes for the distance-dilution reason.
- *Dropping idle noise on ancillas outside their syndrome window.* Same DEM, but it would need CONTRACT's "every qubit not acted on" line reworded, for no change in any label.

---

## D-026 — Seeded sampling loop without sinter; Wilson clamp; P_PILOT exported; DEM conversion and ldpc `schedule` pinned

**Status:** decided (owner, 2026-09-26). Answers the stops in AGENT_LOG (mm).
**Decision:** Four items. The owner authorised `CONTRACT.md` and `protocol.py` edits for these only.

1. **Sampling is our own seeded loop, and sinter leaves the data path.** `stim.Circuit.compile_detector_sampler(seed=seed)` per code, one code per process, batches of exactly `SHOT_BATCH` shots, stopping rule checked between batches. CONTRACT's pinned convention "every generator and sampler takes an explicit `seed: int`" stays as written, **with no exemption for Monte Carlo sampling**. `sinter` stays in `requirements.txt` for now, but nothing on the label path imports it.
2. **`wilson_interval` clamps to `[0, 1]` in `protocol.py`.** At zero failures, `centre - half` cancels to about -1e-18 for 17,314 values of `shots` ≤ 200,000 (the first is 21), and `logical_error_rate` rejects it. The clamp moves only float residue, because the true interval always lies in `[0, 1]`. The local clamp in `evaluate/label.py` is removed, so there is one Wilson implementation again. The golden values G-05/G-06 are interior and unchanged.
3. **`P_PILOT = 0.005` is exported from `protocol.py`.** Tests import it rather than pin a copy. Its value is unchanged: it will be decided from a Kaggle calibration run, not from local measurements.
4. **Two label-changing settings that were unpinned are now in `DECODER_PARAMS`, and so in `protocol_hash`:**
   - `dem_to_matrix = "dem_undecomposed_merge_by_symptom_v1"`, defined exactly in CONTRACT. It is the conversion `evaluate/run.py` already implemented: an undecomposed, flattened DEM; one column per distinct (detectors, observables) symptom, with instructions merged, not one per instruction; priors from each instruction's probability, merged as independent flips; columns in order of first appearance. `run.py` refuses to run if `DECODER_PARAMS` names a different conversion.
   - `schedule = "parallel"`, ldpc 2.4.1's default, now set explicitly and passed to `BpOsdDecoder`.

**Rationale:**
- *Seed.* `sinter.collect` builds its stim samplers unseeded (`sinter/_decoding/_stim_then_decode_sampler.py`) and sizes batches from wall-clock time. Stim's own documentation says seeded output "MAY NOT be consistent if you vary how many shots are taken", so a timing-sized batch breaks reproducibility even with a seed. With more than one worker, per-worker seed streams could also repeat seeds, and that silently double-counts identical shots. Parallelism across codes, one code per process, gives Kaggle's 4 cores the same use without either problem.
- *DEM conversion.* The conversion determines the decoder's input. ldpc's own `detector_error_model_to_check_matrices` merges by detectors only and keeps one observable set, so two reasonable implementations give different labels wherever two mechanisms share detectors. A setting that changes labels but is not hashed is the failure INV-6 exists to prevent. Column order is pinned too. OSD ranks columns by BP's soft output, and where soft values tie, the result can depend on position. That was not checked in ldpc's source, so it is pinned rather than argued.
- *`schedule`.* It changes BP's messages and therefore results. The hashed ldpc version would catch a change of default, but only by accident of a version bump, and it would not say what changed.

**What "reproducible" now means, and does not.** Same code, `p`, seed, stim version **and machine SIMD width** give identical shots and failures (a test asserts it on one machine). Stim states that seeded results are not consistent across stim versions, and may not be across machines with different SIMD widths (SSE vs AVX). So labels regenerate bit-for-bit only on a matching stim version and CPU class. Elsewhere they regenerate statistically. The stim version is not in `protocol_hash` today (only the decoder version is). That is flagged for the owner, not changed: the sampler is distribution-neutral across versions, but plan.md's M1 criterion "regenerate 10 rows … bit-for-bit" depends on it.

**Free only because no labelled row exists yet.** Items 1 and 4 change `protocol_hash` or which shots a label sees. On 2026-09-26 the dataset is empty.

**Rejected:**
- *Keep sinter and exempt sampling from the seed rule.* Labels would reproduce only statistically, the M1 regeneration criterion would need rewording, and one pinned convention would gain its first exception.
- *A custom seeded `sinter.Sampler`.* sinter still sizes batches from timing, and its workers would share or repeat seed streams.
- *Wall-clock-sized or adaptive batches.* Breaks seeded determinism by stim's own statement. The overshoot this causes at ~2 s/shot (AGENT_LOG (mm) item 5) is a `SHOT_BATCH` value question for the Kaggle calibration, not a reason to size by time.
- *One column per error instruction.* Also a valid conversion, but it is not what was implemented and tested, and it gives duplicate columns that BP treats as independent. Either would be defensible. Merged is pinned because it is what exists.
- *Clamp only in `label.py`.* Two places that compute or correct an interval would eventually disagree. `protocol.py` is the one place (INV-4 module docstring).

**Revisit if:** the Kaggle calibration changes the decoder, `P_PILOT` or `SHOT_BATCH`. Also if bit-for-bit label regeneration across machines is required: then the stim version, and possibly the SIMD width, must enter the hash or the row.

---

## D-027 — Sampling seed derived from the row; `stim_version` and `cpu_class` are provenance columns, not hash inputs; sinter claims corrected

**Status:** decided (owner, 2026-09-26). Answers AGENT_LOG (nn) "noticed" items 2, 3 and 4.
**Decision:** Three items. The owner authorised `CONTRACT.md`, `protocol.py` and `plan.md` edits for items 1–2.

1. **`sampling_seed` = first 8 bytes of `sha256(f"{code_id}|{protocol_hash}")` as an unsigned int, masked to 63 bits.** A required int64 row column, computed only by `qecscreen.protocol.sampling_seed`. The owner's wording left two things open, and both are pinned in CONTRACT's `SAMPLING_SEED` block: the string is UTF-8 encoded, and the 8 bytes are read **big-endian**, i.e. `int(hexdigest[:16], 16)`, which is the reading of "first 8 bytes" that matches the hex digest a person would look at. A golden value is in CONTRACT and in `test_protocol.py`. `protocol_hash` must be the 64-char lowercase hex digest or the function raises.
2. **`stim_version` and `cpu_class` are required per-row provenance columns, not `protocol_hash` inputs.** `cpu_class` is `<machine>/<stim SIMD backend>`, the backend being the compiled extension stim actually loaded (`_stim_sse2`, `_stim_avx2` or `_stim_polyfill`). That is the "or equivalent" of the owner's "cpu_flags": stim chooses the backend from the CPU flags at import, and the backend, not the flag list, decides the bits. A raw flag list would differ between Kaggle machines that produce identical bits. plan.md's M1 regeneration criterion now reads: bit-for-bit on the same stim version and CPU class, within Wilson intervals otherwise.
3. **Stale sinter claims corrected** in `AGENTS.md §3`, `.github/workflows/ci.yml` and `requirements.txt`, and in `spec/architecture.md §1` (which also said stim's version enters the hash). sinter's version never entered `protocol_hash`; only ldpc's does. sinter stays installed only because `ldpc` depends on it.

**Rationale:**
- *Seed.* A label is reproducible only if the sampler's seed can be recovered. Deriving it from two columns the row already has means it cannot be lost or mistyped. Storing it too means nobody has to trust the derivation to read it. Including `protocol_hash` gives each `p` a different stream for the same code, so rows at different `p` never share shots. 63 bits fit int64 Parquet and stim's seed argument.
- *Provenance, not hash.* The hash says which rows are comparable. Two rows sampled on different stim versions or CPU classes, under the same protocol, estimate the same quantity; they differ in which shots were drawn, exactly like two different seeds. Hashing `cpu_class` would split one Kaggle dataset into as many protocols as there were machine types, and `assert_single_protocol()` would then refuse legitimate rankings.

**Rejected:**
- *A seed chosen per run and stored.* Works, but a stored-only seed can be lost or copied wrong, and a derived one cannot.
- *Little-endian bytes.* Equally valid; big-endian is pinned because it matches the hex digest.
- *`stim_version` / `cpu_class` in `protocol_hash`.* See rationale: it splits comparable rows.
- *Raw CPU flag list as the column.* Too fine: it varies across machines that give identical bits.
- *Removing sinter from `requirements.txt` now.* It would still be installed by ldpc, so the line's removal changes nothing but the file; left for a separate change.

**Revisit if:** stim changes how it chooses its backend (e.g. re-enables AVX2, stim issue 432), which changes what `cpu_class` must capture. Or if ldpc drops its sinter dependency.

---

## D-028 — Remote execution: install by pinned SHA from a private repo, token from platform secrets

**Status:** decided (owner, 2026-09-26). The token is optional since D-030: the install cell uses it only if the secret exists.
**Decision:** All sampling and decoding runs on Kaggle or Colab, from notebooks the owner runs; agents never execute notebooks. A notebook installs this package with `pip install git+https://github.com/Pushkar0997/qecscreen@<40-hex sha>` (`pyproject.toml`, src-layout, runtime dependencies read from `requirements.txt`). While the repository is private (D-013), the install reads a GitHub token from the platform's secret store, Kaggle Secrets or Colab `userdata`, under the name `GITHUB_TOKEN`. The token never appears in a notebook's source, its outputs, or any artifact. Notebook rules are in `spec/architecture.md §2`.

**How the no-credential rule is enforced:**
- `provenance.py` returns no URL, no path and no environment variable. From `direct_url.json` it takes only `vcs_info.commit_id`, and only if it is a bare hex object id. `test_provenance.py` installs a fake distribution whose install URL carries a token, sets the token in the environment too, and asserts that neither `resolved_commit()` nor anything in `record()` contains it.
- The install cell masks the token in pip's output before printing it. pip redacts credentials in its own logs and in `direct_url.json` (PEP 610), but that is pip's behaviour, not something this project controls.
- `test_notebook_contract.py` scans every notebook's source and outputs for strings shaped like GitHub tokens.

**Relation to INV-9 and `architecture.md §7`.** INV-9 forbids paid services and metered APIs, and AGENTS.md's summary says "no API keys". The token is neither a paid service nor a metered API: it is read access to the owner's own repository on GitHub's free tier, used only by the notebook's install cell. The package itself still needs no key, and a clone of a public repo needs none. The token exists only while D-013 keeps the repo private and is retired when it goes public.

**Rejected:**
- *Token in the cell, or in a Kaggle dataset.* It survives in Kaggle's version history and in every copy of the notebook.
- *Uploading a wheel or a zip of the repo as a Kaggle dataset.* No commit to read back, so `resolved_commit()` returns `None` and no row can be written (D-017).
- *Making the repo public early.* Contradicts D-013.

**Revisit if:** the repository goes public (then the secret and its read are removed from the template), or Kaggle/Colab change their secrets APIs.

---

## D-029 — Decoder calibration: paired BP+OSD vs BP+LSD run, kept out of the dataset

**Status:** decided (owner, 2026-09-26: the grid, decoders, paired design, limits and summary contents are the owner's; the choices below marked *pinned here* are the agent's readings, listed so they can be overruled).
**Decision:** `qecscreen.evaluate.calibrate.run_calibration(config, out_dir)`, run from `notebooks/calibrate.ipynb` on Kaggle, measures the decoders on p ∈ {0.001, 0.0015, 0.002, 0.003} × {[[72,12,6]], gross [[144,12,12]], 6 sampled codes}. Its output is what the owner will use to choose the decoder, `P_PILOT`, `SHOT_BATCH` and possibly `MAX_SHOTS`; it changes none of them and recommends nothing.
- **Paired.** Per cell, one stim sampler seeded with `sampling_seed(code_id, h)`, `h` the pinned protocol's hash at that p. Every decoder decodes every shot, all decoders per shot, so a stop condition leaves all of them on the same shots. Per decoder: failures, per-round LER and Wilson interval (via `make_label`, so INV-3 censoring still nulls the point estimate under 100 failures), ms/shot, BP convergence fraction. For each LSD variant against OSD: discordant counts and an exact McNemar p-value.
- **Decoders.** `bposd` is `run.CompiledBpOsd`, the label path's decoder. `bplsd_cs_0` and `bplsd_cs_4` are ldpc `BpLsdDecoder` with the pinned `bp_method`, `max_iter`, `ms_scaling_factor` and `schedule`, `lsd_method="lsd_cs"`, and `lsd_order` 0 and 4; everything else is at ldpc defaults.
- **Limits.** A cell stops when every decoder has `MIN_FAILURES`, at `max_shots` (default `MAX_SHOTS`), or at a 20-min wall cap checked between shots, and records which. 4 processes. Before sampling it prints `ceil(cells / processes) × cap`, a hard bound for list scheduling when every job is shorter than the cap, and refuses to start above 3 h. The default grid's bound is 8 × 20 min = 2.67 h, plus at most one shot per decoder per cell past the cap.
- **Not dataset rows.** One JSON per cell plus `plan.json` and `summary.json`, all `"calibration": true`. An out_dir with any path component named `data` is refused. `qecscreen.evaluate.rows.reject_calibration` refuses any of it; the row writer (M0-EVAL-04 / M0-RUN-01, not yet written) must call it on every input.
- *Pinned here:* the sampled codes come from `sample_bb_params(300, budget=150, seed=CALIBRATION_CODE_SEED = 20260926)`. 150 is the budget every M0 measurement so far used, not a pinned constant. The 6 are chosen by `select_spanning`: targets evenly spaced from min to max `d_upper`, each taking the nearest unused code. The same 300 codes are the population the pilot projection is made over. M0-RUN-01 must not use this seed.
- *Pinned here:* `code_id` is CONTRACT's formula over `params_json` = canonical JSON of `l`, `m`, `a_exps`, `b_exps`. The dataset's own `code_id` function does not exist yet; if M0-RUN-01 canonicalises differently, only calibration ids change.
- *Pinned here:* stim sampling batches of 256 inside a cell (not `SHOT_BATCH`, which is under evaluation; a 10,000-shot batch would exceed the cap on most codes). Unused rows of the last batch are discarded, so the shots decoded are a prefix of a reproducible stream.
- *Pinned here, summary projections:* shots to `MIN_FAILURES` = `100 × shots / failures`, with a range from the Wilson interval; with 0 failures, "exceeds `MAX_SHOTS`" is true only if even the Wilson upper bound needs more, else unknown. Core-hours use the label loop's `SHOT_BATCH` granularity, with an unbatched figure alongside; censored and unknown codes are costed at `MAX_SHOTS`. For the 300-code pilot: seconds/shot from a power law in `n × d_upper` fitted over the calibration codes, and failure fraction from the calibration code nearest in `d_upper` (then `n`). These are extrapolations from 8 codes, and the summary names the method.

**Rejected:**
- *Sampling separately per decoder.* The decoder difference would be buried in sampling noise; the paired design exists to remove it.
- *Using `sample_and_decode` per decoder.* Label-path semantics: `SHOT_BATCH` batches and BP+OSD only.
- *A per-cell time estimate from a probe before the run.* Probing is sampling; the cap already gives a hard bound without it.
- *Guarding only by directory name.* The marker travels with every file and record, so it still works once output is copied elsewhere.

**Revisit if:** the grid changes enough that the default bound exceeds 3 h, or M0-EVAL-04's writer lands (its tests must then drive the calibration output through the writer itself).

**Amendment (owner, 2026-09-26) — hard per-cell kill, because BP+LSD can hang.** A hang inside `decode()` cannot be interrupted by the between-shot wall cap. And since resume skips only completed cells, a hung cell would hang again on every restart: same seed, same syndrome.
- **What happens now.** Every cell runs in its own spawned worker process, at most `processes` at a time. A worker still alive `cell_wall_seconds + cell_kill_margin_seconds` after it started is killed.
- **The kill record.** The parent writes the cell's file with `status: "killed"`. It holds:
  - `sampling_seed`, `sample_batch`, `batch_index`, `shot_in_batch`, `shot_index` and the `decoder` that was running, all read from a shared array the worker updates before every `decode()` call;
  - a `reproduce` recipe.

  That is enough to regenerate the exact syndrome locally.
- **What is kept.** The worker flushes a partial tally at every batch end and every 30 s. The kill record keeps the last flush as `partial`: shots `0 .. partial.shots - 1`, every decoder done on each, with per-decoder counts and paired comparisons. Everything decoded after that flush is lost, including the shot that hung.
- **Unexpected exits.** A worker that exits without writing its result, for example on a segfault, is written the same way as `status: "died"` with its exit code.
- **Resume and summary.** Resume treats `killed` and `died` as done and never retries them. The summary lists them under `unfinished_cells` and leaves them out of every comparison and projection.
- **Margin and bound.** The margin defaults to 120 s: one shot per decoder past the cap (~1 min on the largest code) plus the worker's imports. The projected bound is now the real hard one, `ceil(cells / processes) × (cap + margin)`. For the default grid that is 8 × 22 min = **2.93 h**, which supersedes the 2.67 h above and is still under 3 h.

**Why a hang on a real sampled shot would matter.** A hang is only expected on a syndrome no error can produce. The mutant that found it fed LSD a rotated syndrome. Every syndrome the sampler emits is the detector image of some set of circuit faults. Each of those faults is a mechanism in the DEM. So every sampled syndrome lies in the column span of the DEM check matrix built from that DEM (merging mechanisms by symptom keeps their columns). If LSD hangs on a *real* shot, the most likely cause is that the DEM → matrix conversion (`dem_undecomposed_merge_by_symptom_v1`) dropped a mechanism. That would make the matrix a wrong model of the circuit for every decoder, BP+OSD on the label path included, not only for LSD. The kill record is how that would be found: rebuild the syndrome from `sampling_seed`, batch and shot, then check it against the column span of `dem_matrices(...)` over GF(2). If it is outside the span, the conversion is wrong. If it is inside, the hang is an ldpc bug on a valid input.

**Note (owner's re-projection, 2026-09-28).** `summarize(out_dir, *, population=None, max_shots=MAX_SHOTS, shot_batch=SHOT_BATCH)` can re-project the same cells over another population or under other `max_shots` and `shot_batch` values. The defaults reproduce the stored summary. Each pilot projection now also reports:
- `censored_overall`;
- `max_code_core_hours`;
- the fit codes' `n·d_upper`;
- for each population code, the fit codes that bracket it (`interpolation_brackets`);
- the codes outside the fit range (`outside_fit_range`).

The models above are unchanged, and no protocol constant moves. The first use is `evidence/reprojection/2026-09-28/`, recorded in `spec/evals.md §7`.

---

## D-030 — The repository is public; the notebook install needs no token

**Status:** decided (owner, 2026-09-27). Supersedes D-013 on visibility.
**Decision:** The repository is public from 2026-09-27, before the M0 verdict. Cell 1 of `notebooks/template_run.ipynb` and `notebooks/calibrate.ipynb` reads the `GITHUB_TOKEN` secret (Kaggle Secrets, then Colab `userdata`) only if it exists, and otherwise installs from the plain URL `git+https://github.com/Pushkar0997/qecscreen@<40-hex sha>`. A missing secret, or neither platform, is not an error. The cell prints which way it installed. When a token is used, the D-028 rules still hold: it is masked in pip's output and never appears in a notebook or an artifact.
**Rationale:** A public repo needs no credential to install, so requiring one would make a notebook fail for anyone without the owner's secret, the owner included on a fresh Kaggle account. The token path is kept rather than removed, so a notebook with the secret attached keeps working unchanged, and so is the credential-leak guard: `test_provenance.py`'s credential tests and `test_notebook_contract.py`'s token scan stay. `test_notebook_contract.py` now also executes cell 1 against fake Kaggle and Colab secret stores, with pip replaced by a recorder: with no secret it installs from the plain URL; with one, from the token URL, with the token masked in the printed output.
- *Pinned here:* both platforms raise, rather than return `None`, when the secret is not attached (Kaggle's `get_secret` raises a backend error, Colab's `userdata.get` raises `SecretNotFoundError` or `NotebookAccessError`), so the cell catches `Exception` around each read. The cost: a Kaggle secrets-service failure also falls through to the public URL, which on a public repo installs the same commit.
- D-013's rationale for going public at M1 (DOI, citations) is unchanged. INV-10 is unaffected: the M0 write-up still publishes within 7 days of the verdict.

**Rejected:**
- *Removing the token read.* A notebook with the secret attached would still work, but the masking would go untested, and the path returns if the repo is ever made private again.
- *Keeping the token required.* A public repo would fail to install without a credential it does not need.

**Revisit if:** the repository is made private again (then the token becomes required, and the cell should fail loudly without it), or Kaggle/Colab change their secrets APIs.

---

## Template

```
## D-0XX — <short title>

**Status:** proposed | decided | superseded by D-0YY
**Decision:** <what>
**Rationale:** <why, including what breaks without it>
**Rejected:** <alternatives, each with why not>
**Revisit if:** <condition>
```

Rules: add the entry the day the decision is made — backfilled logs are fiction. Supersede rather than delete. The rejected list is the part that does the work.
