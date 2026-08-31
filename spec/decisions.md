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

**Status:** decided
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
