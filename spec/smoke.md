# smoke.md — Manual Smoke Checklist

Run before every dataset release and before every tagged version. ~10 minutes. Catches what automated tests do not.

This project has no deploy, no users and no UI, so the standard web checklist does not apply. What replaces it is the **cold-clone check** — the equivalent of a cold start for a research artifact, and the thing that most often reveals the project only works on one laptop.

```
pytest -q && python -m qecscreen.selfcheck
```

## 1. Environment

- [ ] `pip install -r requirements.txt` succeeds in a **fresh** Colab cell, no manual fixes
- [ ] Same on Kaggle
- [ ] `import qecscreen` completes in under 3 seconds
- [ ] `import qecscreen` makes no network call (INV-9-T covers this; confirm it ran)
- [ ] `torch` is **not** installed and nothing breaks

## 2. Cold clone

The most valuable section. Do it properly — a fresh clone in a fresh directory, not a `git pull`.

- [ ] Clone into a new directory with no `data/`
- [ ] `pytest -q` passes with zero pre-existing data files present
- [ ] `scripts/run_m0_pilot.py --limit 3` generates 3 rows end to end from nothing
- [ ] Kill it mid-run, restart it — it resumes and does not duplicate rows
- [ ] The reference `[[72,12,6]]` code reproduces `n=72, k=12, d_upper=6` (G-07..G-10)

## 3. Correctness spot-checks

- [ ] Open the generated Parquet and eyeball 5 rows: shots, failures, and `true_ler` are mutually consistent
- [ ] At least one censored row exists and has a null `true_ler` — if none do, either the pilot `p` is too high or the censoring rule is not firing
- [ ] `protocol_hash` is identical across every row of a single run
- [ ] Pick the single best code by `true_ler` and re-run it independently; the two LERs overlap within their confidence intervals
- [ ] Confirm no column starting with `pred_` exists in the measurement Parquet

## 4. Reproducibility

- [ ] Re-running with the same seed produces identical `code_id`s
- [ ] `regenerate(row)` on 3 random rows returns bit-identical check matrices
- [ ] The random seed appears in every stored row

## 5. Documentation honesty

- [ ] The README's headline number is the family-holdout number, not the random-split one
- [ ] Every reported distance says `≤` or `exact`
- [ ] The censoring rate is stated in the dataset card, even though it is unflattering
- [ ] `spec/architecture.md §6` compute arithmetic reflects the *measured* per-shot cost, not the original 5 ms placeholder

## 6. Publication discipline (INV-10)

- [ ] The most recent completed milestone has a public output — write-up, DOI, or preprint
- [ ] If it does not, stop and ship that before starting anything else

---

## Failure protocol

1. **Revert first:** `git revert <sha>` — the history is one task per commit precisely so this is surgical
2. Reproduce locally with a fixed seed
3. Add a test to `spec/evals.md` that would have caught it — do this *before* fixing
4. Fix
5. Re-run this checklist in full, not just the failed section

For a bad dataset release: **never delete the Zenodo record.** Publish a corrected new version and mark the old one superseded in its description. A DOI is a promise.

Every real bug adds an item to this file.
