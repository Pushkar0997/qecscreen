# plan.md — Milestones

Sequential. Do not start M(n+1) before M(n)'s exit criteria are met and a verdict is recorded in `spec/evals.md §7`.

Sized for **10 hours a week**, deliberately below the stated 10–20, because that is the number that gets hit in a bad month and a plan that only works in good months is a wish.

**Currently active: M0.**

---

## M0 — Falsification ⏱ 2 weeks · cost ₹0

The load-bearing assumption of this entire project is that cheap structural features carry ranking signal that Φ misses. If that is false, nothing downstream matters. M0 tests it before any infrastructure is built, and is designed to be able to **kill the project in two weeks**.

**Scope discipline:** one code family (BB), one physical qubit budget, one physical error rate. Everything else is deferred. Resisting the urge to "just also do GB while I'm here" is the single most valuable behaviour in this milestone.

**M0's scope, exactly (D-031):** BB codes; the 11 polynomial templates of D-024; `d_upper >= 3`; `n <= 72`. That is 244 codes, enumerated, not sampled; 242 of 244 are labelled (D-036: two mixed_3_5 codes are unbuildable under the pinned schedule and have no row). The protocol is the pinned BP+OSD at `P_PILOT = 0.002`, with `SHOT_BATCH = 256` and `MAX_SHOTS = 40,960` (D-034). The M0 verdict is a claim about this population only. **Larger n is M1's question.**

**Deliverables**
- Working BB code generator, validated against the published `[[72,12,6]]` reference
- Stim circuit builder with X-then-Z monomial-matching syndrome extraction, Z-basis memory (D-025)
- BP+OSD evaluation loop with the censoring rule and resume-from-disk
- The 244 admissible BB codes at `n <= 72`, 242 of 244 (D-036) labelled at `P_PILOT = 0.002` (D-031)
- ~20 cheap structural features per code
- LightGBM ranking baseline, grouped splits
- Recall@30-of-top-10 and Spearman, for Φ and for the model, with bootstrap confidence intervals
- A short public write-up of the result, whichever way it goes

**Exit criteria**
- [x] `pytest` passes, including every invariant test in `spec/evals.md §3` — evidence in the M0 verdict, `spec/evals.md §7`
- [x] BB generator reproduces `n=72, k=12, d_upper=6` for the reference parameters
- [x] Measured per-shot decode cost recorded, and `spec/architecture.md §6` updated with the real number — the Kaggle calibration's BP+OSD costs, with the budget-72 re-projection (M0-EVAL-05, D-031)
- [x] One row for each of the 244 codes in the M0 population (D-031), each with shots, failures, Wilson interval and `protocol_hash`. This replaces "≥250 rows": the enumerated population has 244 codes. **Amended by D-036 (2026-10-02): 242 of 244**, the two codes `bb_schedule` cannot build excluded and recorded in the measurements file
- [x] Censoring rate reported; if >40% of rows are censored, the chosen `p` was wrong and the pilot is re-run at a higher `p` before proceeding
- [x] A results table exists showing Recall@30 and Spearman for Φ vs LightGBM, on a construction-program-grouped split, with bootstrap CIs
- [x] A verdict — proceed or kill — is recorded in `spec/evals.md §7` with evidence per criterion — 2026-10-03: PROCEED, headline criterion FAIL
- [ ] The write-up is published within 7 days of the verdict (INV-10)

**Risk:** the decode cost was measured at 1.1–2.3 s/shot on [[42]]–[[72]], not the 5 ms planned (`spec/architecture.md §6`). The pilot's probe measured 3.69 core-hours for 12 evenly ranked codes, so the pilot is ~110 core-hours at `MAX_SHOTS = 40,960` (D-034, `spec/architecture.md §6`), under the 158 ceiling, or about three Kaggle sessions after a new probe. Mitigation, if the new probe's per-code costs run far past that: stop and report (AGENTS §7), then shrink the population to a smaller n or reduce `osd_order`, recording the protocol change as a new `protocol_hash`. BP+LSD is not a mitigation, because it re-ranks codes (D-031). Do not solve it by reducing shots below the censoring rule — that trades a compute problem for a correctness problem.

**Kill condition:** Φ's Spearman is already high and LightGBM's advantage does not survive bootstrap resampling. Publish the negative result, stop. This is a success.

---

## M1 — Dataset v0.1 ⏱ 4 weeks

Only if M0 says proceed. The dataset is the artifact with the longest half-life — it stays useful even if every model in this repo is superseded, which is why it ships before any modelling work.

**Deliverables**
- Two additional families implemented: generalized bicycle and hypergraph product
- Three physical qubit budgets, three values of `p`
- ~2,000 labelled rows, sharded Parquet, resumable generation
- Dataset card: schema, protocol, censoring, known limitations, how to regenerate
- Zenodo release with a DOI; HuggingFace Datasets mirror
- `regenerate(row)` round-trip verified on a 20-row sample

**Exit criteria**
- [ ] ≥1,500 non-censored rows across ≥3 families
- [ ] Every row passes INV-3, INV-5, INV-6, INV-7, INV-8 checks in CI
- [ ] Zenodo DOI issued and resolvable
- [ ] A stranger can clone the repo, run one command, and regenerate 10 rows that match the published ones bit-for-bit on the same stim version and CPU class (the rows' `stim_version` and `cpu_class` columns), and otherwise passing, row by row, a two-sided two-proportion test of regenerated against published `failures`/`shots` at α = 0.05/10 (Bonferroni over the 10 rows) (D-027). The Bonferroni level caps the chance that correct code fails this criterion at about 5%; the earlier wording, "within their Wilson intervals", failed correct code about 40% of the time (0.95^10 ≈ 0.60 to pass)
- [ ] Dataset card states the censoring rate and the per-family row counts honestly

---

## M2 — Benchmark and baselines ⏱ 3 weeks

The citable artifact. This is the milestone that stands on its own even if the GNN never works.

**Deliverables**
- Frozen, versioned splits: family-holdout as the headline, grouped-CV alongside
- Evaluation script producing the standard table for any scoring function
- Baselines: Φ, `n`-only, random, LightGBM
- Decision on the "clear margin" threshold for success metric 1 — **written before the M2 results are looked at**
- Short arXiv preprint

**Exit criteria**
- [ ] `python -m qecscreen.benchmark --scorer <fn>` runs for an arbitrary scoring function and emits the table
- [ ] Headline number is family-holdout; random-split appears only beside it (INV-2)
- [ ] Preprint posted

---

## M3 — GNN surrogate ⏱ 4 weeks

**Deliverables**
- Tanner-graph GNN, trained on M1 data, evaluated on M2 splits
- Comparison against LightGBM and Φ on the same holdout

**Exit criteria**
- [ ] Beats LightGBM on family-holdout Recall@30, or the negative result is recorded as such and not buried

---

## M4 — Package and outreach ⏱ 3 weeks

**Deliverables**
- `qecscreen.score(code)` — one function, documented, pip-installable
- A worked integration example screening candidates in a realistic search loop
- Emails to the four named groups in `spec/product.md §3`
- Unitary Foundation microgrant application

**Exit criteria**
- [ ] `pip install qecscreen` works in a clean Colab cell
- [ ] Four emails sent
- [ ] At least one external response recorded in `AGENT_LOG.md`

---

## Sequencing rules

- **M0 blocks everything.** It exists to make the other four unnecessary if the premise is wrong.
- M1 ships before M3. The dataset is the durable artifact; the model is the perishable one.
- **Do not skip M2.** It is tempting to go straight from data to the fancy model, and it is exactly backwards: the frozen benchmark is what makes any model claim credible, and it is what other groups will actually adopt.
- M4 outreach happens after M2, not after M3. You email people about a benchmark, not about a model that might improve.

## Anti-goals for the current stage

Things that will feel productive and are not, until M0 closes:

- Implementing a second code family. One family answers the question.
- Building the GNN, or reading about GNN architectures. Torch is not even a dependency yet.
- Writing a README that markets the project. There is no result to market.
- A logo, a docs site, a project website, a Twitter thread.
- Refactoring the pipeline for elegance before 300 rows have been generated once.
- Sweeping decoder hyperparameters. The protocol is pinned; changing it invalidates labels.
- Adding a second noise model.
- Optimising decode speed before the real per-shot cost has been measured.

If you find yourself doing one of these, check which milestone is active.

## The perfectionism guard

Stated because the project owner named this as the specific risk.

Every milestone has a **published output**, not just a completed one. M0 ends with a public write-up within 7 days of the verdict (INV-10). M1 ends with a DOI. M2 ends with a preprint. A milestone that is "done but not shared yet" is not done.

If two consecutive weeks pass with commits but no exit criterion moving, that is the signal to stop and re-read this section.
