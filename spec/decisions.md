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

**Status:** decided
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
