# AGENTS.md — qecscreen

**Read this completely before touching any code.**

This is a research-infrastructure project run by one undergraduate with roughly 10 hours a week, zero budget, and agentic tools doing most of the execution. Optimise for correct, small, reversible steps that a fresh session can pick up cold.

---

## 1. Read order

1. `AGENTS.md` — this file
2. `CONTRACT.md` — what must never break
3. `spec/architecture.md` — stack, structure, capability register
4. `spec/plan.md` — which milestone is active
5. `spec/tasks.md` — the specific task
6. `AGENT_LOG.md` — top 3 entries, for current state

Read `spec/evals.md` before claiming anything works. Read `spec/decisions.md` before proposing an architectural change — it may already have been rejected with reasons.

**If a task conflicts with `CONTRACT.md`, the contract wins.** Stop and flag it. Do not silently resolve.

---

## 2. Hard invariants

Never break these without explicit human approval. Full statements with detection methods are in `CONTRACT.md`; these are the operational summaries.

### INV-1 — Predictions are never presented as measurements
`pred_*` and `true_*` never merge. No helper silently falls back to the model.

### INV-2 — Splits are grouped by construction program
`train_test_split` on code rows is banned. Headline metric is family-holdout.

### INV-3 — Thin labels are censored, not estimated
Fewer than 100 observed logical failures means `censored = True` and a null `true_ler`.

### INV-4 — One LER formula, defined in CONTRACT
Per round, per logical qubit. Produced only by `qecscreen.protocol.logical_error_rate`.

### INV-9 — Zero recurring cost
No servers, no paid APIs, no managed databases, no API keys. Runs on a laptop, Kaggle or Colab. If a task appears to need one of these, stop and flag it — there is always another way and the constraint is not negotiable.

### INV-11 — Licence and attribution files are not optional
`LICENSE`, `NOTICE` and `CITATION.cff` stay current. Never delete or empty them, never
add a GPL/AGPL dependency that would force relicensing, and never merge an external
contribution without DCO sign-off (`git commit -s`) — see D-012, which explains why
that is impossible to retrofit.

### INV-10 — Publish before polishing
The M0 verdict is posted publicly within **7 days** of being recorded, whatever it says, including if it kills the project. Any task whose effect is to make an unpublished thing nicer is deferred. This exists because the stated failure mode for this project is a perfectionist spiral, not a lack of ability.

---

## 3. Stack — pinned

| Layer | Choice | Version |
|---|---|---|
| Language | Python | 3.11 |
| Circuit simulation | `stim` | ≥1.14 |
| Sampling orchestration | `sinter` | ≥1.14 |
| Decoder | `ldpc` (Roffe) | ≥2.1 |
| Arrays | `numpy` | ≥1.26,<3 |
| Tables | `pandas` + `pyarrow` | ≥2.2 / ≥15 |
| Graphs | `networkx` | ≥3.2 |
| Baseline model | `scikit-learn`, `lightgbm` | ≥1.4 / ≥4.3 |
| Statistics | `scipy` | ≥1.12 |
| GNN (M3 only) | `torch`, `torch-geometric` | pinned at M3, not before |
| Tests | `pytest` | ≥8.0 |
| Env | `pip` + `requirements.txt` | — |

`pip` and `requirements.txt` rather than Poetry or uv, because Kaggle and Colab are pip environments and the project must install in one cell.

**Do not add a dependency** without checking: is it needed, is it maintained, does it install on Kaggle without a compiler, does it need an API key, **and is its licence compatible with Apache-2.0 redistribution**. A GPL or AGPL dependency would force this project to relicense — flag it and stop rather than adding it. Record every addition in `spec/decisions.md`.

**Do not import torch outside `src/qecscreen/models/gnn/`.** It is a heavy optional dependency and the data pipeline must run without it.

---

## 4. Working rules

**One task per change, one commit, task ID in the message.** Do not batch. Do not refactor files you were not asked to touch. Commit format: `<type>(<scope>): <task-id> <summary>`.

**State the milestone before you start.** First line of any session response: which milestone is active and which task you propose. If you cannot say, you have not read `spec/plan.md`.

**Report what you changed.** Files created, files modified, public functions whose signature changed, spec files that now need updating, and anything you noticed but did not fix.

**Update the spec in the same change as the code.** A spec that has drifted is worse than none, because the next agent trusts it.

**Do not invent values.** If you need a constant, a convention, or a capability and it is not in `CONTRACT.md` or `spec/architecture.md`, stop and ask. Do not pick one and proceed. This project is full of choices that look arbitrary and are not.

**Prefer improving over adding.** Given a choice between a new feature and making an existing one correct, make it correct.

**If a task fails twice, stop.** Do not try a third time. Two failures means the task is underspecified — escalate to rewrite the *task*, not to a bigger model doing the same work.

**Long-running jobs are checkpointed.** Any data-generation run writes partial results to Parquet every batch and can resume from disk. Kaggle sessions die at 12 hours and Colab dies whenever it feels like it. A job that loses 6 hours of work because it held everything in memory is a defect, not bad luck.

---

## 5. Definition of done

- [ ] Tests pass clean — no errors, no new warnings
- [ ] Acceptance criteria observably met
- [ ] Relevant test in `spec/evals.md` passes
- [ ] `spec/smoke.md` passes for the affected area
- [ ] Spec updated if behaviour diverged
- [ ] `spec/tasks.md` checkbox ticked
- [ ] `AGENT_LOG.md` entry written
- [ ] Committed with the task ID in the message

"It runs" is not done. "The numbers look reasonable" is emphatically not done — reasonable-looking wrong numbers are this project's characteristic failure.

---

## 6. Vocabulary

Use these words with these meanings, consistently.

- **Code** — a quantum error-correcting code, specified by `H_X` and `H_Z`. Never means source code. When you mean source code, say "source".
- **Construction program** — the parameterised recipe that generates a family of codes (e.g. the BB polynomial template). The unit of grouping for splits.
- **Family** — a class of construction programs: BB, GB, HGP, TB. The unit of the headline holdout.
- **Label** — a measured `true_ler` from a real Stim + decoder run.
- **Prediction** — model output, always `pred_*`.
- **Proxy** — a cheap scalar used for screening. Φ = kd²/n is *the incumbent proxy*, and it is the baseline we must beat.
- **Screening** — ranking many candidates cheaply to decide which few get expensive evaluation. The task this project exists to improve.
- **Protocol** — the frozen tuple of noise model, p, rounds, decoder and scheduling. Identified by `protocol_hash`.
- **Censored** — a row with too few observed failures to be a point estimate.

Avoid: "accuracy" (say which metric), "performance" (say LER or say runtime), "distance" without saying exact or upper bound.

---

## 7. Compute budget

No metered paid services. The constrained resource is **CPU hours**, and it binds before anything else.

| Resource | Ceiling | Notes |
|---|---|---|
| Kaggle | ~30 h/week, 12 h max session | 4 CPU cores. The workhorse. |
| Colab free | variable, unreliable | Fallback and interactive work only. |
| Local laptop | whatever it is | Development and tests, not bulk generation. |
| GitHub Actions | free for public repos | Tests only. **Never** bulk data generation — wrong tool, against the spirit of the tier. |

Worst-case arithmetic, written down so a future change fails loudly rather than silently overspending — see `spec/architecture.md §6`. Any change to `MAX_SHOTS`, `SHOT_BATCH` or `osd_order` requires recomputing it in the same commit.

If a generation run is projected to exceed its milestone's stated CPU budget, stop and report rather than starting it.
