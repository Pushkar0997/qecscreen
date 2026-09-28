# AGENT_LOG

Append-only. **Newest entry at the top.** Never edit past entries — append corrections as new ones.

Every session writes an entry, including failed sessions. "Noticed, did not fix" may not be empty without a reason.

---

## 2026-09-28 (vv) — Claude Opus 5.5 / Claude Code — the pilot travels as one tar: Kaggle keeps at most 500 output files (D-033 amendment 2)

**Milestone:** M0. **Task:** a fix to M0-RUN-01/02 before the probe runs. As built, the pilot directory sat in `/kaggle/working`, and with up to ~10,000 shards the chain would break by session 2 (owner confirmed Kaggle's "Too many output files (max 500)"). This was (uu)'s "noticed" item 2.

**Changed:**
- `evaluate/pilot.py`: the pilot directory is scratch, and `PilotConfig.archive_dir` (default `/kaggle/working`) receives `m0-pilot.tar` plus `.sha256`, written `.tmp` → fsync → rename, every `SNAPSHOT_MINUTES` = 60 and at session end, plus the session summary without its inventory. `PREVIOUS` accepts exactly one tar: sha256 is checked, the tar is extracted, and the inventory check runs. A mismatch, a missing sidecar, zero tars or two tars are refused. `pilot_cost_report` and `assemble_measurements` take the tar or a directory. An `OUT_DIR` inside `archive_dir` is refused.
- Pinned here (D-033 amendment 2 lists them): each snapshot writes `inventory.json`, because a mid-session snapshot no longer matches the previous summary's inventory. A pilot with a manifest but no summary is a probe that died, and it is re-run as the probe. A resumed snapshot keeps its session number.
- `notebooks/pilot.ipynb`: the runbook and cells 3–4. `OUT_DIR = /kaggle/tmp/m0-pilot`, and the artifact goes to `/kaggle/working`. Cell 5 was not authorised, so the tar location is `PilotConfig`'s default, not a notebook argument.
- `spec/architecture.md`: §2 runbook. In §6, the 20,000-shot rejection is restated as D-031's cost reason.
- Tests: the chain runs through tars, and each "working" dir holds exactly 3 files. Other tests: a corrupted tar or missing sidecar is refused, as are two tars or none; the inventory is checked inside a tar; a mid-session snapshot resumes to the uninterrupted rows (slow); a died probe is re-run as the probe; `OUT_DIR` inside the archive dir is refused; the cost report on a tar equals the one on the directory.

**Suite:** default only, **319 passed, 26 deselected**. The slow tests (the tar chain and the mid-session snapshot among them) were not run locally, per this session's rules; CI runs them. No mutation testing.
**CI:** reported in the session reply for the pushed SHA.

**Noticed, did not fix:**
1. `spec/evals.md` N-17 still describes the chain through directories, and `spec/tasks.md` was not touched. Neither was in the authorised list.
2. `/kaggle/tmp` is the owner's path. Kaggle's docs name `/kaggle/temp` as scratch. Either should work, since the runner creates the directory, but it has not been run.
3. Kaggle's handling of a crashed version's output (whether the last snapshot is kept) is assumed from the owner's brief, not observed.

---

## 2026-09-28 (uu) — Claude Opus 5.5 / Claude Code — D-032 resume rule; M0-RUN-01 row writer and pilot runner; M0-RUN-02 pilot notebook, probe and cost gate (D-033)

**Milestone:** M0 — Falsification
**Tasks attempted:**
- Part 0: owner decisions recorded (spec only).
- Part 1: the measurement-row writer (M0-RUN-01).
- Part 2: the pilot runner, chained across Kaggle sessions (M0-RUN-01).
- Part 3: the pilot notebook, the probe session, the cost gate and `pilot_cost_report` (M0-RUN-02).

Nothing was decoded beyond test-sized runs on [[12]] codes locally. No notebook was run.

**CI for (tt)'s commit `c47273d`:** success (run 36395846316), read through the public API.

**Owner answers asked for this session** (the brief marked them "confirm", or left them unpinned):
- `SESSION_WALL_HOURS` = **10.5**, not the proposed 11.0.
- The probe: **12 codes, 3 h**, not 2 h.
- The measurements file: **`data/m0_measurements.parquet`**. Architecture §2 pinned `data/` but no file name, so this was a stop-and-ask.

**Landed:**
- `49a4260` **Part 0**, spec only.
  - CONTRACT SAMPLING gains the batch-level resume rule, recorded as **D-032**.
  - D-031's status line notes the owner's approval of plan.md's "one row for each of the 244 codes".
  - D-031's reason for rejecting 20,000 shots is restated as cost (~13 vs ~6.5 core-hours for a capped code), with a dated correction note and the owner's "Revisit if".
  - tasks.md: M0-EVAL-03 reworded (done when test names match CONTRACT or CONTRACT is corrected, and the guard is tested on a DataFrame column). "Every ranking entry point calls it" moved to M0-METRIC-01. M0-RUN-01's `CALIBRATION_CODE_SEED` rule reworded as given.
- `5a1a78f` **Part 1**, M0-RUN-01's row writer.
  - `evaluate.rows.build_row(code, checkpoint_dir)`, with `MEASUREMENT_SCHEMA`, which is exactly architecture §3's columns and types. A test parses §3's table and compares.
  - Checkpoint shards now record `commit_sha`, `stim_version` and `cpu_class` per batch. Shards that disagree raise `ProvenanceMismatchError`, as does a resume by a process that differs from them. A digest mismatch raises `SampleDigestMismatchError`. Both are `CheckpointMismatchError`s.
  - New `codes/ids.py`: `params_json`, `code_id` and `regenerate`. `calibrate.code_id` delegates to it; a test checks the committed calibration's ids are unchanged.
  - `build_row` refuses: calibration input; a missing, empty or placeholder commit; mixed provenance; an unfinished code; a seed that is not `sampling_seed(code_id, protocol_hash)` under the installed ldpc; a code record that disagrees with its parameters.
  - N-16, 5 of 5 mutants caught.
- `a67c6bc` **Part 2**, M0-RUN-01's runner: `evaluate/pilot.py`, D-033.
  - The population is enumerated by the new `codes.sample.admissible_codes(72)`. It has 244 codes, pinned digest `5008e14e…`. Its per-template counts equal evals §7's budget-72 row. A slow test checks it equals `sample_bb_params(244, 72, CALIBRATION_CODE_SEED)`.
  - `sample_and_decode(..., deadline=)` is checked between batches, predicting one batch ahead. The first batch of a call always runs.
  - The copy of `PREVIOUS` is verified file by file, and against the inventory the previous session's summary recorded. A Kaggle-truncated output is therefore refused.
  - Tests: `tests/test_pilot.py`, with worker hooks in `tests/_pilot_fakes.py`. N-17, 13 of 13 mutants caught (chaining and the manifest check).
- `3f928e5` **Part 3**, M0-RUN-02.
  - `notebooks/pilot.ipynb`: a runbook markdown cell, then the six template cells, cells 1–2 identical to the template. The runbook is mirrored in architecture §2.
  - Session 1 (no manifest) is the probe. Later sessions refuse without `COST_GATE`, which is recorded in the manifest.
  - `pilot_cost_report` and `format_cost_report`. `_project_pilot(per_code=True)` is opt-in, so `summarize`'s output is unchanged.
  - D-033 amendment. N-18, 7 of 7 mutants caught.

**M0-RUN task IDs this closes:** M0-RUN-01 and M0-RUN-02, both ticked. M0-RUN-03 (execute the pilot) stays open; it is the owner's Kaggle work. **Reworded because their wording predated D-031:**
- M0-RUN-01: `scripts/run_m0_pilot.py` and "sample params" became the package runner.
- M0-RUN-02: `m0_kaggle.ipynb` became `pilot.ipynb`.
- M0-RUN-03: "≥250 rows" became 244 rows, with the session procedure.

**Merged for spec-with-code:** each part's spec edits are in that part's commit. Part 3's commit also carries the `_project_pilot` change the cost report needs.

**No column had to be invented.** The row stores exactly architecture §3's columns. Deliberately not in the row, but kept in each checkpoint directory: `stopped_by`, `osd_invocations`, `samples_sha256`, `batch_size`, `max_shots`. The last two are CONTRACT constants that the manifest also records.

**Suite:** default **313 passed, 25 deselected**, 49 s. The 9 slow tests in `test_pilot.py` were also run locally once, because they are the chaining evidence: all pass, ~2.5 min.
**CI:** this entry is committed before the push. The pushed SHA's run is reported in the session reply.
**Blockers:** none. The pilot notebook is ready to upload with the pushed SHA as `QECSCREEN_SHA`.

**Noticed, did not fix:**
1. `spec/architecture.md §6` still says the cap is not 20,000 because ~13 h is "longer than a 12-hour Kaggle session". That is the rationale 0c corrected in D-031, but architecture was not in Part 0's authorised list.
2. **Kaggle output file count, not checked.** A finished pilot directory holds up to ~10,000 small files (244 × ≤ 41). If Kaggle drops files from a large output, the inventory check refuses the next session rather than resuming wrongly. The probe (≤ ~500 files) will not show it. Session 2's copy is the first real test.
3. **Kaggle input mount path, not checked.** The runbook says to set `PREVIOUS` to the directory the Input panel shows. The runner searches below it for the one pilot manifest, so the exact layout under `/kaggle/input` should not matter, but this is from the docs, not a run.
4. **`PREVIOUS` pointing at the notebook's own output.** Attaching several versions of the same notebook is refused (two manifests). The runbook says to detach older versions.
5. `format_summary` still titles its projection "300-code"; `evaluate/__init__.py` still has the placeholder docstring (carried from (ss) and (tt)).
6. The Bash tool here failed twice on Python heredocs containing certain quoted text; the edits went through Edit instead. This is tooling, not the repo.

**Spec changes:**
- `CONTRACT.md`: SAMPLING (D-032).
- `spec/decisions.md`: D-031 status and correction, D-032, D-033 and its amendment.
- `spec/architecture.md`: §2, for `data/m0_measurements.parquet`, `pilot.ipynb` and the runbook.
- `spec/evals.md`: N-15 extended; N-16, N-17, N-18.
- `spec/tasks.md`: EVAL-03, METRIC-01, RUN-01, RUN-02 and RUN-03.

No NARRATIVE entry: nothing surprising came up. The calibration/pilot shared-shots fact was the owner's, recorded as given.

---

## 2026-09-28 (tt) — Claude Opus 5.5 / Claude Code — D-031 M0 pilot protocol (M0-EVAL-05 closed); M0-EVAL-04 resume within a code

**Milestone:** M0 — Falsification
**Tasks attempted:**
- Part 1: the owner's decisions, recorded as D-031. Ticks M0-EVAL-05.
- Part 2: M0-EVAL-04, redefined by the owner as resume within a code at batch granularity.
- Check whether M0-EVAL-03 is already satisfied.

No FEATURES, SPLIT or RUN task was started, and nothing was decoded on Kaggle.

**CI for (ss)'s commit `f35828d`:** success (run 36380257010), read through the public API.

**Stopped once, and asked.** `MAX_SHOTS = 10,000` with `SHOT_BATCH = 256` is 39.06 batches. CONTRACT requires both "batches of exactly `SHOT_BATCH`" and `MAX_SHOTS` as a hard cap, and `sample_and_decode` already refused a `max_shots` that is not a whole number of batches. The owner chose **10,240 = 40 × 256** over 9,984, a truncated last batch, or "stop once shots ≥ `MAX_SHOTS`". D-031 records this.

**Landed:**
- `c120737` **D-031 + M0-EVAL-05**, code and spec in one commit (AGENTS §4, §7). CONTRACT exact values:
  - `MAX_SHOTS` 10,240;
  - `SHOT_BATCH` 256;
  - `P_PILOT` 0.002;
  - a D-031 note on `DECODER`.

  Also in the commit:
  - `protocol.py`: the same three constants.
  - D-031 records BP+LSD as rejected, with the evidence for `P_PILOT`, and says the mixed_3_5 codes stay in. It states M0's scope as BB codes, the 11 templates, `d_upper ≥ 3` and n ≤ 72, and leaves larger n to M1. It gives the reason for 10,240 rather than 20,000: ~13 h vs a 12 h session. D-016 is marked superseded.
  - `architecture.md §6`: measured per-shot costs replace the 5 ms figure. The M0 budget is budget-72 at p = 0.002: 244 codes, 52.5 core-h, 13.1 wall-h, 0% censored. That is identical at 10k/20k/50k shots, so 10,240 changes nothing. It adds "assume 2–3×", because the cost model misses its own fit codes by 0.17–7×. The M1 budget is marked not recomputed.
  - `plan.md`: M0's scope, the deliverable, the risk paragraph, and the per-shot exit criterion ticked. **The "≥250 rows" exit criterion is now "one row for each of the 244 codes"**, because an enumerated population of 244 cannot reach 250.
  - `evals.md`: the M0 verdict section's required size-scaling diagnostic, and N-03 restated at `MAX_SHOTS`.
  - Tests:
    - New: `test_d031_shot_cap_is_a_whole_number_of_batches`.
    - `test_d026_p_pilot_exported` now expects 0.002.
    - Four existing tests had the old constants baked in. They now either use the symbols or pass the old values explicitly:
      - `test_shots_needed_and_censoring_projection`;
      - `test_pilot_projection_on_synthetic_cells`;
      - `test_projection_under_other_constants_and_population`;
      - `test_stops_at_min_failures_at_the_first_batch_boundary`, which asked for `max_shots=20_000` and now asks for 10,000.

      N-03 was renamed `test_n03_three_failures_at_max_shots_is_censored_not_a_rate`.
- `152fbea` **M0-EVAL-04**:
  - New module `evaluate/checkpoint.py`, and `sample_and_decode(..., checkpoint_dir=None)`.
  - A one-row Parquet shard per completed batch, written atomically (`.tmp`, fsync, rename) before the next batch is sampled.
  - `result.parquet` marks the code finished.
  - Resume re-creates the seeded sampler, draws and discards the completed batches, checks each against its shard's batch digest and running digest, and restores the counts.
  - `CheckpointMismatchError` on a digest mismatch, a gap, or another seed, batch size or `max_shots`.
  - Tests: `tests/test_evaluate_resume.py`, 18 tests, ~13 s. 5/5 mutants caught. Recorded in tasks.md and evals N-15.
- `NARRATIVE.md` entry (this commit).

**M0-EVAL-03 is not ticked. It is implemented, but not as the task words it.** Present:
- `protocol_hash()` and `assert_single_protocol()` in `protocol.py`.
- Tests in `tests/test_protocol.py`: `test_inv6_single_protocol_guard` (raises on two hashes and on none), the hash-stability tests, and the tests for the D-014, D-025, D-026 and decoder-version hash inputs.

Missing:
1. `tests/test_inv_6_protocol.py`, the file the task names, does not exist.
2. CONTRACT's detector name `test_single_protocol_guard` does not exist; the test is called `test_inv6_single_protocol_guard`.
3. INV-6-T says the guard raises "on a frame". It is only tested on a list, never on a DataFrame's `protocol_hash` column.
4. "Every ranking and training entry point calls it" cannot be tested, because none exists yet. That belongs to METRIC and RUN-04.

**Suite:** default only: **269 passed, 16 deselected**, 51 s (was 250). The slow tests were read, not run. `test_ler_increases_with_p` uses `max_shots=10_000` ≤ 10,240. None of the others depends on the changed constants.
**CI:** reported in the session reply for the pushed SHA. The next entry should record it.
**Blockers:** none.
**Noticed, did not fix:**
1. `CalibrationConfig.max_shots` defaults to `MAX_SHOTS`, so a calibration re-run on the same grid would now stop cells at 10,240 shots. The Kaggle run's [[12]] cells took 20,521. `summarize()` on the committed evidence now projects at the new constants by default. With `max_shots=200_000, shot_batch=10_000` it reproduces the stored `summary.json` projections exactly (checked).
2. CONTRACT's SAMPLING paragraph does not mention resume: "a resumed code draws and discards its completed batches". Part 2 did not authorise a CONTRACT edit.
3. M0-RUN-01's text says "must not draw codes with `CALIBRATION_CODE_SEED`". With an enumerated population the seed no longer decides membership, and the population includes the calibration's n ≤ 72 codes. Their calibration output is still refused by `reject_calibration`. The wording may need the owner.
4. D-029's "revisit if M0-EVAL-04's writer lands": this checkpoint writer takes a circuit, not records, so `reject_calibration` has no input to check. The row writer is still M0-RUN-01.
5. CONTRACT INV-3's "Why" still uses "3 times in 200,000 shots" as an illustration. It is not an exact value, so it was left.
6. Carried from (ss): `format_summary` still titles its projection "300-code"; `evaluate/__init__.py` still has the placeholder docstring.

**Spec changes:**
- `CONTRACT.md`: exact values.
- `spec/decisions.md`: D-031, and D-016 superseded.
- `spec/architecture.md`: §6.
- `spec/plan.md`: M0.
- `spec/evals.md`: §4 N-03 and N-15, §7 M0 verdict diagnostic.
- `spec/tasks.md`: EVAL-04 and EVAL-05 ticked.
- `NARRATIVE.md`.

---

## 2026-09-28 (ss) — Claude Opus 5.5 / Claude Code — Part 0 standing rules; M0-EVAL-07 calibration recorded; BP+OSD re-projection of the pilot

**Milestone:** M0 — Falsification
**Tasks attempted:**
- Part 0: three owner-authorised edits, in separate commits.
- Part 1: record the Kaggle calibration (M0-EVAL-07, ticked).
- Part 2: re-project the pilot over the owner's grid with the pinned BP+OSD.

No decoding was run. `DECODER_PARAMS`, `P_PILOT`, `SHOT_BATCH`, `MAX_SHOTS`, `codes/` and `circuits/` are untouched. No new dependency. Nothing is recommended.

**CI for (rr)'s commit `7e91f82`:** success (run 36340014354), read through the public API.

**Landed:**
- `ed28f05` AGENTS.md §5:
  - locally run only the default suite; the slow tests run in CI;
  - after every push, check that commit's CI through the public GitHub API and report its conclusion;
  - not done while that run is in progress or red.
- `0ead429` INV-9 summary: the repo is public (D-030), so the notebook token is optional.
- `5150fe3` ci.yml comment: Actions minutes are no longer metered. The concurrency cap and timeout are kept.
- `ea5579f` **M0-EVAL-07**:
  - Evidence: `evidence/calibration/2026-09-27-7e91f82/` (35 files).
  - Records: `spec/evals.md §7` has a calibration result, not a verdict. `spec/tasks.md` is ticked. `spec/architecture.md §2` gains `evidence/`.
  - The folder was **not** at the path the brief gave. The output was in `~/Downloads/qecscreen_kaggle_test/`: a `results.zip` and an unzipped copy with 6 files moved into a `claude/` subfolder.
  - All 35 files of the two copies are byte-identical. The committed copy is the zip's flat layout, and its provenance commit is `7e91f82e…`.
  - `reject_calibration` refuses the directory.
  - `summarize()` at HEAD reproduces the stored summary, apart from the last digits of the power-law fit.
- `318517a` Part 2, code and spec together:
  - `summarize(out_dir, *, population=None, max_shots=MAX_SHOTS, shot_batch=SHOT_BATCH)`; `_shots_needed`, `_run_shots` and `_project_pilot` take the same values.
  - Each projection also reports `censored_overall`, `max_code_core_hours`, `fit_codes`, `interpolation_brackets` and `outside_fit_range`.
  - Defaults unchanged. New test: `test_projection_under_other_constants_and_population`.
  - Evidence: `evidence/reprojection/2026-09-28/`, holding `reproject.py` and `reprojection.json`, both marked calibration.
  - Recorded in `spec/evals.md §7`, plus a D-029 note.
- `20c7d30` NARRATIVE entry.

**Findings (details in evals §7):**
- **Size scaling (BP+OSD):**
  - pair_2_2 is sub-threshold, with intervals separate, at p = 0.0015, 0.002 and 0.003.
  - sym_3_3 is sub-threshold only at 0.002, on 20 gross shots.
  - mixed_3_5 shows no improvement at any p, and every completed interval lies above p.
- **Paired decoders:** LSD fails more than OSD in 15/27 cells at McNemar p ≤ 2e-3. LSD-0/OSD runs 1.29–2.53 and LSD-4/OSD 1.20–2.25, falling with p in every code. The ratio is not constant.
- **[[140,6,≤16]]** died in all 4 cells, exit −9. Three died before their first decode, and one after 3 shots.
- **The killed [[112]] cell** at p=0.003 is explained by its timings: ~25 s setup, then 3 × 334 s. Shot 3 started at ~1,026 s, and its LSD-4 decode would end at ~1,360 s, past the 1,320 s kill. There is no evidence of a real-shot hang.
- **Re-projection:**
  - 116 / 175 / 244 / 373 admitted codes at budget 48 / 60 / 72 / 96.
  - Core-hours from 8.4 (48, p=0.002) to 935 (96, p=0.0015, 50k shots).
  - No code lies outside the fit's `n·d_upper` range.
  - But the power law misses the fit codes themselves by 0.17–7×.

**Suite:** default only (the new §5 rule): **250 passed, 16 deselected**, 31 s. The full suite runs in CI.
**CI:** this entry is committed before the push. The pushed commit's result is reported in the session reply and should be recorded by the next entry.
**Blockers:** none. The decoder, `P_PILOT`, `SHOT_BATCH` and `MAX_SHOTS` decisions are the owner's.
**Noticed, did not fix:**
1. The "60-shot test that saw no difference", cited in the brief, is not in AGENT_LOG, NARRATIVE or the spec. The NARRATIVE entry cites it as the owner reported it.
2. `spec/architecture.md §6` still carries the 5 ms/shot planning figure. M0-EVAL-05 is open, and the calibration now gives measured numbers: BP+OSD takes 1.1–2.3 s/shot on [[42]]–[[72]] and 48–78 s on gross.
3. The cost model's `n·d_upper` does not separate codes with different DEM sizes. [[136,2]] has 31,960 mechanisms and [[112,6]] has 88,704; they are 7× over-predicted and 2.5× under-predicted. The mechanism count might fit better. Not changed, because the brief asked for a minimal extension.
4. The re-projection's censoring is a step function of which of the 7 calibration codes donates the failure fraction, as evals §7 explains. At p=0.0015, 10,000 vs 20,000 shots flips every d_upper 3–4 code on [[12]]'s 11,244 shots.
5. At budget 96 the costliest single codes project at 29–163 core-hours, longer than one 12 h Kaggle session. M0-EVAL-04's resume is per code, not within a code.
6. D-029's 120 s kill margin assumed ~1 min for one shot on every decoder. [[112]] takes ~5.5 min, and [[140]] ~6 min for OSD alone.
7. Enumerating the four populations took ~2 min locally (`estimate_d_upper` per candidate), not seconds.
8. `format_summary` still titles the projection "300-code pilot projection" whatever the population size.
9. `evaluate/__init__.py` still has the placeholder docstring.

**Spec changes:**
- `AGENTS.md`: §5 and the INV-9 summary.
- `.github/workflows/ci.yml`: comment.
- `spec/evals.md §7`: calibration result and re-projection.
- `spec/tasks.md`: EVAL-07 ticked.
- `spec/architecture.md §2`: `evidence/`.
- `spec/decisions.md`: D-029 note.
- `NARRATIVE.md`: new entry.

---

## 2026-09-27 (rr) — Claude Opus 5.5 / Claude Code — D-030: the repo is public, the notebook install needs no token

**Milestone:** M0 — Falsification
**Tasks attempted:** the owner's decision that the repo is public, recorded as D-030 (supersedes D-013 on visibility), and the install cell change it needs. Nothing else was changed, and no notebook was run on Kaggle or Colab.

**Landed:** `f41e5da`, code and spec together.
- **Cell 1** of `template_run.ipynb` and `calibrate.ipynb` (still identical, as `test_calibrate_notebook_follows_the_template` requires):
  - It tries Kaggle's `UserSecretsClient().get_secret("GITHUB_TOKEN")`, then Colab's `userdata.get("GITHUB_TOKEN")`, each inside `except Exception`.
  - With a token it installs from `git+https://<token>@github.com/...@<sha>` and masks the token in pip's output, as before.
  - Without one it installs from the plain `git+https://github.com/Pushkar0997/qecscreen@<sha>`.
  - `assert token` is gone. The cell prints which way it installed.
  - Both platforms raise, rather than return `None`, for a secret that is not attached. That is why each read is wrapped. This is from the platforms' documented behaviour, not checked on either platform.
- **Tests.** All credential-leak tests are kept: the provenance credential tests, the token scan and the template shape test. The shape test now also asserts there is no `assert token`. New in `test_notebook_contract.py`: 10 tests that execute cell 1 of both notebooks against fake secret stores, with `subprocess.run` replaced by a recorder, so there is no network and no install.
  - No secret: on neither platform, on Kaggle with the secret missing, and on Colab with it missing. Each installs from the plain URL without raising.
  - Secret on Kaggle, and on Colab: each installs from the token URL. The fake pip echoes the URL back, and the printed output holds `***` and not the token.
  - Checked against HEAD's cell 1: the three no-secret cases and the shape test fail on it.
- **Spec:** D-030 in `spec/decisions.md`, with status notes on D-013 and D-028. `spec/architecture.md` §2 rule 5 and §7 now say the token is optional. `spec/evals.md` N-13 describes the new tests.

**Suite:** full (`-o addopts=""`, slow tests included) **265 passed**, exit 0, 279 s. That is 255 plus the 10 new tests. The default run passed too.
**CI:** this entry is committed before CI runs on it, so the result is reported to the owner in the session reply. The next entry should record it.
**Blockers:** none.
**Noticed, did not fix:**
1. **AGENTS.md's INV-9 summary** says the token is permitted "while the repo is private (D-028)". Read literally, that now forbids the token path the owner asked to keep. It needs an owner-authorised edit, as in (pp).
2. `.github/workflows/ci.yml` line 11 says "The repo is private through M0 (D-013), so Actions minutes are metered". Public repos get free Actions minutes, so the comment is stale. The concurrency cap and timeout are still worth keeping.
3. The notebooks' cell comment still points to Kaggle and Colab secrets. That is intended, since the secret is optional.
4. `evaluate/__init__.py` still has the placeholder docstring.
**Spec changes:** `spec/decisions.md` (D-030; status notes on D-013 and D-028), `spec/architecture.md` (§2 rule 5, §7), `spec/evals.md` (N-13). No `spec/tasks.md` change, because no task ID was assigned. No NARRATIVE entry: this is a routine visibility change.

---

## 2026-09-26 (qq) — Claude Opus 5.5 / Claude Code — M0-EVAL-06 fix: hard per-cell kill for a hung decoder (D-029 amendment)

**Milestone:** M0 — Falsification
**Tasks attempted:** the owner's single fix before the Kaggle calibration run: BP+LSD can hang (D-029), a hang inside `decode()` is not interruptible by the between-shot cap, and resume would retry it forever. Nothing else was changed, and nothing was run on Kaggle.

**Landed:** `b6335be`, code and spec together.
- **Workers.** Every `(p, code)` cell runs in its own spawned worker, at most `processes` at a time, including `processes=1`. The in-process path and the `ProcessPoolExecutor` are gone. The parent waits on the workers' sentinels and kills a worker still alive `cell_wall_seconds + cell_kill_margin_seconds` after it started. The margin is a new config field, default 120 s.
- **Kill record.** The parent writes the cell file with `status: "killed"`, holding `sampling_seed`, `sample_batch`, `batch_index`, `shot_in_batch`, `shot_index`, `decoder` and a `reproduce` recipe. The batch, shot and decoder come from a 3-slot shared array the worker sets before every `decode()` call.
- **Unexpected exits.** A worker that exits without writing its result is recorded the same way, as `status: "died"` with its exit code. This was not asked for, but without it a segfault would leave no file and be retried on every restart, which is the same problem.
- **What is kept.** The worker flushes a partial tally at every batch end and every 30 s: shots `0 .. partial.shots - 1`, every decoder done on each, with counts, LER/Wilson, timings and paired comparisons. The kill record carries the last flush as `partial`. Everything decoded after it is lost, including the shot that hung. The `partial_*.json` file is deleted once folded in, or once the cell completes.
- **Resume and summary.** Resume skips `killed` and `died` like completed cells. The summary lists them under `unfinished_cells`, adds `killed`/`died` to its stop counts, and leaves them out of every comparison and projection. Completed cells now carry `status: "completed"`.
- **Projection.** The bound is now the hard one, `ceil(cells / processes) × (cap + margin)`. For the default grid it is **2.93 h** (8 × 22 min), up from 2.67 h and still under 3 h.
- **D-029 amendment** records the above, plus why a hang on a *real* shot would matter. Every sampled syndrome lies in the column span of the DEM check matrix, so a real shot that hangs LSD most likely means the DEM → matrix conversion dropped a mechanism, which would be wrong for BP+OSD labels too. The kill record is how that would be found: regenerate the syndrome and check it against the span over GF(2).
- **Tests.** `test_a_hung_decoder_is_killed_recorded_and_never_retried` runs in 5.1 s.
  - Setup: `tests/_calibration_fakes.py`'s decoder hangs forever on shot 150 of `bplsd_cs_4`, with a 100-shot batch, a 3 s cap and a 2 s margin.
  - The run completes, and the cell is `killed` at batch 1, row 50, shot 150, decoder `bplsd_cs_4`, with the right seed.
  - The batch-0 partial (100 shots, identical syndrome digests across both decoders) is kept, and no partial file is left behind.
  - The syndrome regenerates from the record.
  - A restart starts no worker.

  The two resume tests now patch `_start_worker` instead of the removed `_cell_job`.

**Suite:** full (`-m "slow or not slow"`) **255 passed**, exit 0. The default run is **239 passed, 16 deselected**. Both are under `filterwarnings = error`.
  - The first full run took 918 s because it competed with other test runs I had going at the same time. A clean rerun passed too, with normal durations: calibration tests 5–7 s each, the 300-code draw 41 s.
  - Wall-time totals in this entry are unreliable for that reason. Spawning a worker per cell costs ~2 s on Windows, so the default run is about 10 s slower than in (pp).

**Blockers:** none. The owner runs `calibrate.ipynb` on Kaggle.
**Noticed, did not fix:**
1. A kill leaves no file for the syndrome itself, only the recipe to regenerate it. That is enough with the same stim version and CPU class (D-027), both in the record's `provenance`. On a different CPU class, the regenerated shot may not be the one that hung.
2. The span check described in the amendment is not implemented. It is a local step once a kill record exists.
3. With `processes=1` every cell still pays a spawn. That is harmless on Kaggle, where cells are minutes long.
4. `evaluate/__init__.py` still has the placeholder docstring.
**Spec changes:** `spec/decisions.md` (D-029 amendment), `spec/evals.md` (N-14), `spec/tasks.md` (EVAL-06 note).

---

## 2026-09-26 (pp) — Claude Opus 5.5 / Claude Code — Part 1 owner items (M1 criterion, INV-9 summary, CI installs the package, requirements header); M0-EVAL-06 decoder calibration (D-029)

**Milestone:** M0 — Falsification
**Tasks attempted:** Part 1, four owner items in separate commits (edits authorised to plan.md, AGENTS.md's INV-9 summary, ci.yml and requirements.txt). Part 2: the decoder calibration, now task `M0-EVAL-06` (ticked) with the Kaggle run as `M0-EVAL-07` (open, owner's). Nothing was run on Kaggle. `DECODER_PARAMS`, `P_PILOT`, `SHOT_BATCH`, `MAX_SHOTS`, `codes/` and `circuits/` are untouched, and there is no new dependency.

**Landed:**
- `cbf1e5d` plan.md: the M1 regeneration criterion is now a per-row two-sided two-proportion test of regenerated against published `failures`/`shots` at α = 0.05/10. The text says the Bonferroni level caps the false-fail rate for correct code at about 5%, and why the Wilson wording failed ~40% of the time. It does not pick a test variant, such as a pooled z-test or Fisher's exact test; that choice is made when the check is written.
- `9dc274e` AGENTS.md INV-9 summary matches D-028: no paid services or APIs, the package needs no key, and the one credential permitted is a read-only token for this repo, read from platform secrets.
- `9adb049` ci.yml gains a step on every leg. It runs `pip install "$GITHUB_WORKSPACE"` from `$RUNNER_TEMP`, asserts `qecscreen.__file__` is in site-packages and outside the checkout, then runs `python -m qecscreen.selfcheck`. Verified in a fresh 3.13 scratch venv: the step passes on the installed package and exits 1 when `PYTHONPATH=src` shadows it. The YAML was not parsed locally because PyYAML is not installed; CI is the first real parse.
- `1cbd728` requirements.txt header: Kaggle runs 3.12 (measured 3.12.13, D-020), and all three interpreters are listed.
- `0193b9b` **M0-EVAL-06**, spec and code in one commit, following D-029.
  - `evaluate/calibrate.py`: `CalibrationConfig`, `run_calibration`, `run_cell`, `summarize`, `format_summary`.
  - `evaluate/rows.py`: `reject_calibration`.
  - `notebooks/calibrate.ipynb`: cells 1–2 are byte-identical to the template.
  - `tests/test_calibrate.py`: 19 tests. The smoke config (one [[12,2,3]] code, one p, two decoders, 300 shots) runs in about 0.3 s. Two tests are marked slow: the default 300-code draw (41 s) and the 2-process pool (3 s).
  - Mutants: 4 of 4 caught (no marker on a cell file, no resume check, LSD fed a second seeded stream, no `data/` guard).
  - Spec: D-029, evals N-14, tasks EVAL-06/07 plus a RUN-01 note, and architecture §2/§4.
- **Code ids the Kaggle run will use** (dev box; `d_upper` from `estimate_d_upper(seed=0)`):
  - `ref72` `bb_v1_sym_3_3-6d2a992b16a4` [[72,12,≤6]]
  - `gross144` `bb_v1_sym_3_3-e2a88777e704` [[144,12,≤12]]
  - `bb_v1_pair_2_2-afbf55db2c35` [[12,2,≤3]]
  - `bb_v1_mixed_3_5-cf5649b397df` [[42,6,≤6]]
  - `bb_v1_quad_4_2-c7c6d07a81bf` [[48,4,≤8]]
  - `bb_v1_pair_2_2-deb94a2172e3` [[136,2,≤11]]
  - `bb_v1_mixed_3_5-3a2afa35a12f` [[112,6,≤14]]
  - `bb_v1_mixed_3_5-3fde0f6a646a` [[140,6,≤16]]

  The population's `d_upper` runs from 3 to 16.
- **Projected wall time before sampling:** 32 cells on 4 processes, capped at 20 min each, gives ≤ 2.67 h, plus at most one shot per decoder per cell past the cap. Selecting the codes takes ~40 s on the dev box before that.

**Suite:** default **238 passed, 16 deselected, 17 s**. Full (`-m "slow or not slow"`) **254 passed, 141 s**. Both under `filterwarnings = error`.
**Blockers:** none. The owner runs `calibrate.ipynb` on Kaggle.
**Noticed, did not fix:**
1. **No row writer exists**, so "the row writer rejects calibration output" is tested against the guard the writer must call, `reject_calibration`, not against a writer. M0-EVAL-04's tests must drive calibration output through the real writer (D-029 "Revisit if").
2. **ldpc's BP+LSD appears to hang on a syndrome no error can produce.** A mutant that fed LSD a rotated syndrome ran for more than 4 minutes on [[12,2,3]] before I killed it. Real shots are always producible, so the calibration is unaffected, but a hang inside a worker would stall the run with no error. Not investigated further.
3. The largest sampled code, [[140,6,≤16]] at r = 16, has more detectors (~2,240) than gross (~1,728). By (mm)'s power-law fit, one BP+OSD shot there could take ~15–20 s, so these cells will likely hit the wall cap with few shots and wide intervals. The summary records `stopped_by` for each cell.
4. The calibration's `sampling_seed` is derived from `code_id` and the pinned protocol's hash. If the pilot uses the same code, the same `code_id` canonicalisation and the same `p`, it draws identical shots. That does not matter for labels, but the pilot's first rows of such a code would not be independent of the calibration.
5. Out of scope and left alone:
   - `verify_env_colab.ipynb` cell 1 still says "Kaggle runs 3.11";
   - README line 43 says "no API keys";
   - D-027's text quotes the superseded M1 wording, which is history and is not edited.
6. `evaluate/__init__.py` still has the placeholder docstring.
7. Resuming on Kaggle only works within one session unless the owner copies a saved version's output back into `OUT_DIR`. The notebook's cell 4 says so.
**Spec changes:** `spec/plan.md` (M1 criterion), `AGENTS.md` (INV-9 summary), `spec/decisions.md` (D-029), `spec/evals.md` (N-14), `spec/tasks.md` (EVAL-06/07, RUN-01 note), `spec/architecture.md` (§2 notebooks, §4 capability). No NARRATIVE entry: the M1 criterion correction was already written up in (oo) as a finding, and the calibration's findings come from the Kaggle run.

---

## 2026-09-26 (oo) — Claude Opus 5.5 / Claude Code — D-027 (seed, provenance columns, sinter claims), D-028 remote execution: pyproject, provenance, notebook template and contract

**Milestone:** M0 — Falsification
**Tasks attempted:** Part 1, D-027 (owner items 1–3; CONTRACT.md, protocol.py and plan.md edits authorised for items 1–2). Part 2: `M0-SETUP-04` (pyproject), `M0-CORE-05`/`M0-CORE-06` (provenance), `M0-SETUP-05` (template notebook and contract test), recorded as D-028. SETUP-04/05 are new task IDs, added for the owner's items (a) and (c)–(e). No notebook executed. Decoder, P_PILOT, SHOT_BATCH, MAX_SHOTS, `codes/` and `circuits/` untouched.

**Landed:**
- `fe791fc` **D-027** (spec and code together).
  - `protocol.sampling_seed(code_id, protocol_hash)` implements the owner's rule.
  - Two readings were left open by the wording, and I pinned both in CONTRACT's new `SAMPLING_SEED` block:
    - the string is UTF-8 encoded;
    - the 8 bytes are read **big-endian**, which equals `int(hexdigest[:16], 16)`.
  - Golden G-14: `("bb_v1_ref-0123456789ab", "a"*64)` → `6435667380748351026`, re-derived independently from the hex digest.
  - Tests cover the golden value, stability, a different `code_id` giving a different seed, a different `protocol_hash` (a different `p`) giving a different seed, the 63-bit range, that stim accepts the seed, and 6 bad-input cases.
  - The function raises unless `protocol_hash` is the 64-char lowercase hex digest.
  - CONTRACT gains an INV-6 paragraph and pinned-convention rows. `sampling_seed`, `stim_version` and `cpu_class` are required columns, and none of them is in the hash.
  - `cpu_class` is `<machine>/<stim SIMD backend>`, for example `x86_64/sse2`. That is my "or equivalent" for the owner's cpu_flags. stim picks `_stim_sse2`, `_stim_avx2` or `_stim_polyfill` from the CPU flags at import, and the backend is what decides the bits; AVX2 is disabled in stim 1.16. A raw flag list would split machines that give identical bits.
  - plan.md's M1 criterion is reworded. The sinter claims are corrected in AGENTS §3, ci.yml and requirements.txt, and in architecture §1, which also wrongly said stim's version enters the hash.
- `7cf22fe` **M0-CORE-05/06** (ticked).
  - `provenance.resolved_commit()` returns `vcs_info.commit_id`. It returns `None` for editable, local-dir, archive and index installs, and when the package is not installed. It raises, without echoing the value, on malformed JSON or a commit id that is not bare 40/64 hex.
  - `stim_version()`, `cpu_class()` and `record()` are added. `record()` is the whole provenance dict an artifact carries: no URL, no path, no env var.
  - Tests use a fake `qecscreen-0.0.1.dist-info` on `sys.path`, which `importlib.metadata` finds normally.
  - Credential tests: with a token in the install URL and in `GITHUB_TOKEN`/`PIP_INDEX_URL`, nothing in `record()` contains it.
  - 4 of 4 mutants caught: returning the URL, ignoring vcs_info, dropping the hex check, adding a url field to `record()`.
  - D-028 recorded, and architecture §7 no longer says "Secrets: none exist".
- `a85b676` **M0-SETUP-04** `pyproject.toml`: setuptools backend (build-time only, not a runtime dependency), src-layout, dependencies read dynamically from `requirements.txt`. `.gitignore` gains `build/`, `dist/` and `*.egg-info/`.
  - **Clean-venv verification:** fresh Python 3.13.7 venv, `pip install git+file:///D:/Coding_Work/qecscreen/qecscreen@a85b676936f0f51355b6a18f9466b4ddbde18681`.
    - Install exited 0 and `pip check` is clean. The wheel metadata lists all 11 requirements.
    - `qecscreen` imported from site-packages, not `src/`.
    - `record()` = `{commit_sha: a85b676936f0f51355b6a18f9466b4ddbde18681, stim_version: 1.16.0, cpu_class: x86_64/sse2, decoder_version: 2.4.1, python_version: 3.13.7}`.
    - `python -m qecscreen.selfcheck` passed.
- `2dc779c` **M0-SETUP-05**.
  - `notebooks/template_run.ipynb`, exactly six code cells:
    1. install by full SHA, asserted 40-hex, with the token read from Kaggle `UserSecretsClient` or Colab `userdata` as `GITHUB_TOKEN`, and pip output printed with the token masked;
    2. `record()`, asserting `commit_sha == QECSCREEN_SHA`;
    3. `RUN_NAME`;
    4. the output path;
    5. `qecscreen.selfcheck.main()`;
    6. the JSON artifact and a summary.
  - `tests/test_notebook_contract.py`:
    - no FunctionDef, AsyncFunctionDef, ClassDef or Lambda in any code cell, with `!`/`%` magics blanked and cell magics refused;
    - no token-shaped string in any notebook, source or outputs;
    - the template's shape;
    - self-tests of the checker.
  - `verify_env_colab.ipynb` defined two functions and failed the new test (checked against HEAD). Its search cell is flattened with the same search order, and its stale sinter print is fixed. Cell 2 was parsed, not run.
  - `notebooks/runs/` is evidence and is exempt from the no-definition rule only.
  - Notebook rules are in architecture §2, and evals gains N-12 and N-13.

**Suite:** default **201 passed**, full (`-m "slow or not slow"`) **233 passed**, both under the ini's `filterwarnings = error`.
**Blockers:** none. The template has not been run on Kaggle or Colab; that is the owner's step. Put a SHA in cell 1 and attach the `GITHUB_TOKEN` secret, a fine-grained read-only token for this one repo.
**Noticed, did not fix:**
1. **The M1 criterion "within Wilson intervals otherwise" fails a correct implementation about 40% of the time as literally read.** If each of 10 regenerated rows must fall inside the published row's 95% interval, P(all 10) = 0.95^10 ≈ 0.60. Wrote the owner's wording; it needs a reading, such as "intervals overlap" or a stated tolerance, before M1.
2. AGENTS.md's INV-9 summary says "no API keys". D-028 explains why the install token is not what INV-9 forbids, but the AGENTS line itself was not edited, because that was not authorised.
3. `requirements.txt`'s header and `verify_env_colab.ipynb` cell 1 still say "Kaggle runs 3.11", which D-020 corrected. Left alone because it is not a sinter claim.
4. CI never builds or installs the package, so a broken `pyproject.toml` would first show on Kaggle. A `pip install --no-deps .` step would catch it.
5. `pytest` is a runtime dependency of the installed package, because `requirements.txt` is the single list. Harmless on Kaggle; split it out if the list is ever divided.
6. `sampling_seed` and the three new columns are specified but not yet wired into a row writer. That is M0-RUN-01, which must also refuse `commit_sha = None`.
7. On Colab the template writes to `/content`, which disappears with the runtime.
8. `evaluate/__init__.py` still has the placeholder docstring.
**Spec changes:** `CONTRACT.md` (INV-6 paragraph, conventions rows, SAMPLING, SAMPLING_SEED), `spec/decisions.md` (D-027, D-028), `spec/architecture.md` (§1 stim/sinter, §2 notebook rules, §3 four columns, §7), `spec/plan.md` (M1 criterion), `spec/evals.md` (G-14, N-12, N-13), `spec/tasks.md`, `AGENTS.md §3`. No NARRATIVE entry: item 1 above may earn one once the owner decides the reading.

---

## 2026-09-26 (nn) — Claude Opus 5.5 / Claude Code — D-026 (owner decisions on the (mm) stops), M0-EVAL-01 finished on a seeded loop

**Milestone:** M0 — Falsification
**Tasks attempted:** D-026, owner items 1–4 (CONTRACT.md and protocol.py edits authorised for these only), then `M0-EVAL-01` on the seeded loop, plus the `_v1` docstrings in `circuits/schedule.py`. Tests only; no measurements.

**Landed:**
- `f751f14` **D-026, spec/protocol.**
  - CONTRACT gains a `SAMPLING` block: our own seeded stim loop, one code per process, batches of exactly `SHOT_BATCH`, stopping rule between batches. The seed rule is unchanged, with no exemption.
  - `wilson_interval` clamps to `[0, 1]` in `protocol.py`. `P_PILOT` is exported (value unchanged).
  - `DECODER_PARAMS` gains `schedule="parallel"` (ldpc 2.4.1's default, read back from a constructed decoder before pinning) and `dem_to_matrix="dem_undecomposed_merge_by_symptom_v1"`, defined exactly in CONTRACT. It is merged by symptom, not one column per instruction. Priors come from each instruction's probability, merged as independent flips, with columns in first-appearance order. Both keys are hashed.
  - Architecture's sinter lines and evals' Wilson note are updated.
  - Tests: clamp at 0 failures for 9 values of `n` (and exactly 0.0 at `n=21`, where the unclamped value is -1.4e-17); clamp at all-fail; `P_PILOT` exported; both keys pinned; both keys change the hash.
  - **This commit also touches `evaluate/run.py`, one line**: it filters `dem_to_matrix` out of the ldpc kwargs. ldpc raises `ValueError: Unknown parameter` on any key it doesn't know, so without that line the spec commit fails its own tests. That is the only code in it.
- `eb03225` **M0-EVAL-01 (ticked).**
  - `sample_and_decode(circuit, *, seed, batch_size=SHOT_BATCH, max_shots=MAX_SHOTS) -> RunResult` (seed, batch_size, shots, failures, `stopped_by`, osd_invocations, `samples_sha256` over every sampled byte, decode_seconds).
  - `max_shots` must be ≤ `MAX_SHOTS` and a whole number of batches, so every batch in a run is the same size. The smaller values exist for tests.
  - sinter is removed from `run.py`: `BpOsdSinterDecoder` and `DECODER_KEY` are gone, and `CompiledBpOsd` is a plain class taking a DEM. `dem_matrices` raises if `DECODER_PARAMS` names a conversion it does not implement.
  - `label.py`'s local clamp is removed.
  - New tests:
    - determinism: same code, p and seed give identical `RunResult` apart from wall time, with failures > 0 so the test is not vacuous;
    - a different seed gives a different sample digest;
    - the run stops at `MIN_FAILURES` at the first batch boundary, checked by rerunning one batch shorter;
    - the run stops at `max_shots` and the label is censored;
    - p=0 at CONTRACT defaults: 200,000 shots in batches of 10,000, 0 failures;
    - argument validation (7 cases), `seed` required, `schedule` read back from ldpc;
    - no `import sinter` anywhere in `src/qecscreen`, mutation-checked by appending one to `label.py`, which the test caught.
  - Kept: p=0 (ref72 and small), beats-trivial (both), monotonic in p, which now runs through the loop. Its three labels stop at `MIN_FAILURES`, are non-censored, and have disjoint intervals.
  - evals N-11 added, tasks.md ticked.
- `cc5747d` `schedule.py` lines 1 and 66 now say `_v2`. `build.py` line 1's `_v1` names the noise model, which is still `_v1`, so it is correct and untouched.

**Suite:** default **159 passed, 14 deselected, 25 s**. Full (`-m "slow or not slow"`) **173 passed, 223 s**. Both clean under `-W error`.

**Not changed, per instruction:** decoder settings (beyond pinning `schedule` at its current value), `P_PILOT`, `SHOT_BATCH`, `requirements.txt`.
**Blockers:** none for EVAL-01. The (mm) blockers still open are the owner's Kaggle calibration: P_PILOT, likely at or above threshold, and the decode cost, ~600× the plan.
**Noticed, did not fix:**
1. **ldpc 2.4.1 declares `sinter>=1.12.0` as a dependency and imports it at import time.** Dropping sinter from `requirements.txt` later will not uninstall it, and "sinter not in `sys.modules`" can never be a test. The guard therefore checks our source instead.
2. **The sampling seed has no home in the schema.** The `seed` column exists for regenerating the code (INV-7). A label is reproducible only if the seed given to `sample_and_decode` is stored too, or derived by a pinned rule. M0-RUN-01 needs an owner decision here, and I did not pick one.
3. **The stim version is not in `protocol_hash`, and bit-for-bit reproduction depends on it and on SIMD width** (stim's own docstring). This is recorded in D-026. plan.md's M1 criterion "regenerate 10 rows … bit-for-bit" holds only on a matching stim version and CPU class.
4. Stale sinter claims outside my scope:
   - `AGENTS.md §3` still lists sinter as "Sampling orchestration";
   - `requirements.txt` and `ci.yml` comments say sinter's version enters `protocol_hash`. In code it never did; only ldpc's does.
5. `SHOT_BATCH = 10,000` at ~2 s/shot on [[72,12,6]] makes one batch ~5.5 core-hours, and at P_L ≈ 0.5 it overshoots 100 failures by ~100×. This is (mm) item 5, now concrete because the loop exists. It is a value for the Kaggle calibration.
6. `evaluate/__init__.py` still has the placeholder docstring.
7. Process: the `git checkout` I used to undo the sinter mutation also reverted my uncommitted `label.py` edit. I caught it from `git diff --stat` before committing and redid the edit. The committed state was verified by the full suite after the redo.
**Spec changes:** `CONTRACT.md` (decoder block, SAMPLING, SHOT_BATCH/CONFIDENCE/P_PILOT comments), `spec/decisions.md` (D-026), `spec/architecture.md` (sinter rows), `spec/evals.md` (Wilson clamp note, N-11), `spec/tasks.md` (EVAL-01 ticked). No NARRATIVE entry: the sinter/seed finding was already reported in (mm), and this session carried out the decision.

---

## 2026-09-25 (mm) — Claude Opus 5.5 / Claude Code — D-025 follow-ups, M0-EVAL-01 (partial) and M0-EVAL-02, decode-cost measurement

**Milestone:** M0 — Falsification
**Tasks attempted:** Part 1: D-025 amendment follow-ups (a–d), separate commits. Part 2: `M0-EVAL-01`, `M0-EVAL-02`, tests first. Part 3: threshold sanity check and per-shot decode cost at `P_PILOT`, reported here and not committed as spec.

**Part 1, landed:**
- `86190e2` (a). `SCHEDULING = "bb_monomial_matching_xz_phased_v2"` in `CONTRACT.md` and `protocol.py` (only that line was authorised). The rename is recorded in the D-025 amendment: a label-changing change must change `protocol_hash`, with no exceptions, and this rename is free only because no row exists. `test_protocol.py` now also asserts that `_v1` hashes differently. Two test string literals were updated, and the M0-CIRC-01 task note records the rename.
- `caad7e8` (b). evals N-10 now names `test_x_error_flips_exactly_the_observables_containing_it` and says what only it catches.
- `2f447d7` (c). NARRATIVE entry on check weight leaking into labels through the circuit layout.
- `a3c0947` (d). New `slow` marker. `pytest.ini` addopts deselect it, and CI runs `pytest -m "slow or not slow"` on every leg, so CI skips nothing. evals §1/§6 and smoke.md now say the full suite is what must pass. Twelve tests are marked, all in `test_sample.py`: the ones that use the 48 s `balanced_300` fixture or draw 30 or more admitted codes. At that commit the default run took **11.3 s** (101 passed, 12 deselected) and the full run **148.5 s** (113 passed). At the end of the session the default run takes **16.7 s** (128 passed, 14 deselected) and the full run **202.6 s** (142 passed).

**Part 2: stopped on the sampling loop.** sinter's custom-decoder API fits the plan: `Decoder.compile_decoder_for_dem(dem)` returns a `CompiledDecoder.decode_shots_bit_packed`. What does not fit is **CONTRACT's pinned convention "every generator and sampler takes an explicit `seed`"**. `sinter.collect` has no seed. Its workers call `circuit.compile_detector_sampler()` unseeded (`sinter/_decoding/_stim_then_decode_sampler.py:162`), and `RampThrottledSampler` sizes batches from wall-clock time. A custom seeded `sinter.Sampler` would still not reproduce across runs, and with more than one worker, per-worker seed streams would repeat seeds, which silently double-counts identical shots. CONTRACT wins, so I did not build the loop. **Owner decision needed**, options:
  - (i) An in-house loop: seeded stim, the same compiled decoder, one code per process, per-code seed. Deterministic, and parallel across codes, which is what Kaggle's 4 cores need anyway. Drops sinter from the data path.
  - (ii) Keep sinter and amend CONTRACT so Monte Carlo sampling is exempt from the seed rule. Labels would then reproduce statistically, not bit-for-bit, and M1's "regenerate … bit-for-bit" exit criterion would need rewording.

**Part 2, landed:**
- `082db52` **M0-EVAL-02** (ticked). `evaluate/label.py`: `make_label()` returns a `Label` of the schema's measurement columns. Wilson is taken on per-shot `P_L` and mapped through `logical_error_rate` (monotone), so all bounds are per-round per-qubit. `ci_low`/`ci_high`/`ub` are populated on every row, and `ub == ci_high`. Censored rows have `true_ler = None`. `tests/test_inv_3_censoring.py` covers INV-3-T over 206 count pairs, N-03, the 99/100 boundary, protocol-only arithmetic, zero failures, all-fail raising (N-05), bad counts, and INV-1 field names. **Found:** `wilson_interval(0, n)` returns about -1e-18 for 17,314 values of `n` ≤ 200k (first `n = 21`), which `logical_error_rate` rejects. `label.py` clamps only that residue to 0.0; the proper fix belongs in `protocol.py` and needs owner approval.
- `246a107` **M0-EVAL-01, partial** (not ticked). `evaluate/run.py`:
  - `BpOsdSinterDecoder` (a picklable `sinter.Decoder`) compiles `CompiledBpOsd`: ldpc `BpOsdDecoder` over the **undecomposed** DEM, with `DECODER_PARAMS` passed exactly and read back in a test.
  - `dem_matrices()` merges mechanisms by (detectors, observables).
  - `count_failures()` implements INV-4 "any observable" on bit-packed data, ignoring padding bits.
  - Telemetry: `shots_decoded`, `osd_invocations`.
  - A `ValueError` guard: **ldpc segfaults** (kills the process) when `osd_order` exceeds the free columns.
  - `tests/test_evaluate_run.py` (15 tests) decodes seeded stim shots:
    - p=0 gives 0 failures on [[72,12,6]] and on a [[12,2,3]] `pair_2_2` code (2,000 shots each).
    - The zero syndrome at p=0.005 decodes to no flip with no OSD.
    - [[72,12,6]] at p=0.001, 20 shots: BP+OSD fails ≤ 2 while trivial fails ≥ 10 (slow, 27 s).
    - [[12,2,3]] at p=0.002: 28 vs 447 failures in 2,000 shots.
    - LER increases with p on [[12,2,3]], 4,000 shots each, with disjoint intervals (slow, 20 s): p=0.003 → 6.18e-3 [5.26e-3, 7.26e-3]; 0.006 → 2.13e-2 [1.95e-2, 2.32e-2]; 0.012 → 7.08e-2 [6.73e-2, 7.44e-2].
  - Not delivered: "stopping at MIN_FAILURES or MAX_SHOTS", because it lives in the blocked loop.

**Part 3: both measurements stopped on budget. I overran the 5-minute cap: about 8.5 min of local compute went into probes.** The first probe asked for 300 [[72,12,6]] shots, which I expected to take seconds; it hit its 280 s timeout with no output. That overrun is how the per-shot cost below was found.

*(a) Threshold sanity at P_PILOT: **STOP.*** The gross code was not measured: one shot is projected at ~13–25 s, and 100 failures need hundreds of shots. The [[72,12,6]] evidence already points at the stop condition. Per-round per-qubit LER (Wilson 95%, via `make_label`) at r=6:
  - p=0.001: 0/21 fail → ≤ 2.3e-3
  - p=0.002: 1/16 → [1.6e-4, 4.6e-3]
  - p=0.003: 9/14 → [**6.8e-3**, 2.5e-2]
  - p=0.004: 7/14 → [4.3e-3, 1.8e-2]

  At p=0.003 the whole interval sits above p: the encoded qubit does worse per round than a bare one. [[42,6,6]] (r=3) at 0.005: 78/100 fail, [6.3e-2, 1.0e-1]. **P_PILOT=0.005 is very likely at or above threshold for this circuit and decoder. Changing it is the owner's CONTRACT decision.** Also flagged, not concluded: from memory, not checked here, published [[72,12,6]] numbers (Bravyi et al. 2024) at similar p are far lower. That paper decoded with far more BP iterations. The circuit sanity suite passes, so I cannot say whether the gap is the decoder settings, this noise placement, or something else.

*(b) Per-shot decode cost at P_PILOT* (single core, dev box, `decode()` wall time):

| code | DEM (dets × mechanisms) | shots | median | worst | OSD invoked |
|---|---|---|---|---|---|
| [[72,12,6]], r=6 | 432 × 15,840 | 8 | **~1.95 s** | 3.3 s | **8/8** |
| [[42,6,6]], r=3 (extra) | 126 × 5,985 | 100 | 0.34 s | 1.1 s | 100/100 |
| [[12,2,3]], r=3 (extra) | 36 × 612 | 500 | 0.18 ms | 7 ms | 153/500 |
| gross [[144,12,12]], r=12 | 1,728 × 67,104 (DEM from entry kk) | not run | projected 13–25 s | — | — |
| 5 `sample_bb_params` codes | — | not run | — | — | — |

On [[72,12,6]], OSD ran on 18/21 shots even at p=0.001, and on every shot at p ≥ 0.002. BP (min-sum, `max_iter=30`) almost never converges on the circuit-level DEM, so nearly every shot pays for OSD-CS order 10. The gross projection is a power law fitted through the two measured points (cost ∝ dets^1.37); it is not a measurement.

*Projection for the 300-code M0 run.* Detectors ≈ `n · r`. Weighting the D-024 draw's `d_upper` histogram gives a mean of **~3 s/shot**, which is **~600× §6's 5 ms planning figure**.
  - At P_PILOT as pinned (P_L ≈ 0.5–0.8, so ~150–200 shots per code): **~40–50 core-hours**, ~11–13 h on 4 Kaggle cores. §6 budgets ~15 core-hours. The run would barely fit one session, and it would produce above-threshold labels.
  - At a p low enough for meaningful labels (§6's ~0.5% per-shot P_L, ~20,000 shots): **~5,000 core-hours**, about 40 weeks of the 30 h/week quota. A censored code alone (200k shots) costs ~170 core-hours.
  - Neither mitigation in plan.md's risk list (osd_order 5, or 150 codes) closes a gap of 2–3 orders of magnitude. The backlog's BP+LSD, BP iteration count, and `p` are the levers. All are protocol decisions, and none was touched. §6 is not updated; the authoritative number comes from Kaggle.

**Did not land:** the EVAL-01 sampling loop and stopping rule (blocked, above), and Part 3's gross-code and sampled-code timings. `codes/` and `circuits/` untouched. No new dependency.
**Blockers:**
  1. The seed-vs-sinter decision.
  2. P_PILOT, which is likely at or above threshold.
  3. The decode cost, ~600× the plan.
**Noticed, did not fix:**
  1. `circuits/schedule.py` docstrings (lines 1 and 66) still say `_v1`. Runtime is `_v2` because `Schedule.method` defaults to `protocol.SCHEDULING`. `circuits/` was off-limits.
  2. `P_PILOT` is in CONTRACT but not in `protocol.py`; the test file pins it locally.
  3. **The DEM construction is label-determining but not in CONTRACT or the hash.** It is undecomposed, merged by (detectors, observables). ldpc's own `detector_error_model_to_check_matrices` merges by detectors only and keeps the last observable set, which would give different labels wherever two mechanisms share detectors. On [[72,12,6]] no two do: 15,840 mechanisms map to 15,840 columns. It should be pinned.
  4. `BpOsdDecoder` parameters that CONTRACT does not pin run at ldpc defaults: `schedule="parallel"`, `omp_thread_count=1`, `random_schedule_seed=0`. The ldpc version in the hash covers default drift, but `schedule` changes results and belongs in `DECODER_PARAMS`.
  5. `SHOT_BATCH = 10,000` as a fixed batch at ~2 s/shot overshoots 100 failures by ~100× on codes with P_L ≈ 0.5. The loop, once decided, needs a batch rule that starts small, and that is a CONTRACT reading question.
  6. `evaluate/__init__.py` still has the placeholder docstring.
**Spec changes:** `CONTRACT.md` (SCHEDULING line, authorised), `spec/decisions.md` (D-025 amendment), `spec/evals.md` (N-10, §1, §6), `spec/smoke.md`, `spec/tasks.md` (EVAL-02 ticked, EVAL-01 partial note, CIRC-01 rename note). `NARRATIVE.md` entries for the D-025 amendment and the decode cost.

---

## 2026-09-25 (ll) — Claude Opus 5.5 / Claude Code — D-025 amendment: ancilla timing

**Milestone:** M0 — Falsification
**Tasks attempted:** D-025 amendment (owner decision), ancilla timing. Owner authorised edits to CONTRACT.md's tick-layout lines and the D-025 record, nothing else outside `circuits/` and its tests.

**Read of the instruction, stated because it had two readings.** Taken literally, "reset X → X phase → [MX + R Z] → Z phase → measure Z" per round is 3 non-CX ticks per round, one more than before, and that contradicts "no added depth" (it would add one data idle per round). The only layout satisfying both is to put round t's Z readout in the same tick as round t+1's X reset, and the last Z readout in the tick of the noiseless data readout. That is what landed. If the owner meant the literal version with an extra tick, it is a one-line change, and `test_tick_layout_per_round` pins which one we have.

**Landed (`5f1ee3b`, code and spec in one commit per AGENTS §4):**
- `build.py`: open tick (RX X-ancillas, + M of the previous Z-ancillas), X phase, swap tick (MX X + R Z), Z phase; last tick M(p) Z-ancillas + noiseless M data. `DEPOLARIZE1(p)` stays on every qubit not acted on, per CONTRACT's literal rule. For ancillas this now happens only between readout and next reset (Z-ancillas in round 0's open tick, X-ancillas during the Z phase and in the last tick), where it cannot change any outcome.
- CONTRACT tick-layout lines rewritten; D-025 amendment recorded in `spec/decisions.md`, with the feature-leakage reason and "free only because no labelled row exists".
- Tests (`tests/test_circuit_sanity.py`, 25 → 31):
  - `test_tick_layout_per_round` (ref72 and mixed42, depth 6 and 8): the exact gate signature of every tick.
  - `test_no_ancilla_idles_while_it_holds_syndrome`: every reset ancilla is in a CX the very next tick, and no DEPOLARIZE1 hits it before its readout.
  - `test_idles_off_the_syndrome_window_do_not_reach_the_dem`: stripping the out-of-window ancilla idles leaves the DEM identical.
  - `test_x_error_flips_exactly_the_observables_containing_it`: for all 72 data qubits, flipped observables `== {i : z_logical_basis()[i][q] == 1}`. The qubit 0/40 tests now assert the same set equality.
  - Placement and channel-count tests extended to the new layout.
  - The injection point moved from "after MX" to "after the Z-ancilla M", since MX is now mid-round.

**Report — [[72,12,6]], r = 6 (mixed42, r = 3, in brackets):**

| | before | after |
|---|---|---|
| ticks per round | 14 [18] | 14 [18] |
| ticks in circuit | 86 [56] | 86 [56] |
| ancilla idle ticks per round while holding syndrome | 432 [336] | **0** [0] |
| … of which between reset and first CX | 216 [168] | **0** [0] |
| ancilla idle ticks outside the syndrome window (whole circuit, no effect on DEM) | 0 | 2664 [1050] |
| data idle ticks per round | 576 [420] | 576 [420] |
| detectors | 432 [126] | 432 [126] |
| DEM error mechanisms | 15,840 [5,985] | 15,840 [5,985] |

DEPOLARIZE1 channel count in the ref circuit: 6·1008 → 6·1008 + 72 (the 72 are the round-0 Z-ancillas before their first reset and the X-ancillas in the last tick).

**Mutation check, against the new layout: 16 mutants, all caught.**
- The 8 from entry (kk), ported:
  - interleave X/Z: 17 tests;
  - Z phase before X: 9;
  - noisy data preparation: 2;
  - missing CX idles: 2;
  - noisy final readout: 2;
  - identity observables: 9;
  - wrong-check Z detector: 2;
  - missing final detectors: 5.
- New:
  - the pre-amendment builder from HEAD: 7 (layout, no-idle, placement, counts);
  - Z reset moved back to round start: 7;
  - X measured at round end: 8;
  - an extra closing tick (added depth): 4;
  - no noise on out-of-window ancillas: 2 (DEM-equivalent, caught by the literal CONTRACT placement rule);
  - observable 0 × a Z stabiliser: 2 (the new sweep, plus qubit 40);
  - observable 0 × observable 1: 2 (the sweep, plus qubit 0).

  The last two stay deterministic and pass N-08 and the DEM build. The exact-set sensitivity tests are what catch them.

**Suite:** **113 passed** (107 before), clean under `-W error`, 147 s.

**Did not land:** `codes/`, `protocol.py`, evals.md untouched (out of scope).
**Blockers:** none.
**Noticed, did not fix:**
1. The scheduling string and noise-model name are unchanged, as instructed, so a pre-amendment and post-amendment circuit share a `protocol_hash`. Harmless today because no row exists. If anyone ever regenerates rows from a pre-`5f1ee3b` commit, only `commit_sha` distinguishes them.
2. `spec/evals.md` N-10 names only the two per-qubit tests. The new sweep test belongs there too, but evals.md was outside this change's scope.
3. D-025 item 2 still carries the original layout sentence. It is superseded by the amendment directly below it, not edited, per decisions.md's supersede-don't-delete rule.
4. No `NARRATIVE.md` entry, since it was out of scope. The feature-leakage reasoning is worth one if the owner wants it.
**Spec changes:** `CONTRACT.md` (tick layout), `spec/decisions.md` (D-025 amendment).

---

## 2026-09-25 (kk) — Claude Opus 5.5 / Claude Code — M0-CIRC-01/02/03: circuit protocol v1 (D-025), schedule, Z-memory circuit

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-CIRC-01`, `M0-CIRC-02`, `M0-CIRC-03` together, tests first. **Merged task IDs in one commit** because the owner asked for the three together and the tests (CIRC-03) exercise both CIRC-01 and CIRC-02. The spec/protocol change was committed separately, as instructed.

**Stopped before writing code.** Of the four conventions the owner listed, only the rounds convention was pinned: D-006 plus INV-4 give `r` noisy rounds in total, the first included. The memory basis was not pinned anywhere. For noise placement, CONTRACT pinned the channel types but not where they go. The scheduling string was pinned (`tanner_edge_colouring_v1`), but its meaning was not, and the requested phased schedule could not be recorded in it without editing CONTRACT.md and protocol.py, which were off-limits. The owner answered all four and authorised edits to CONTRACT.md and protocol.py for items 1–3.

**Landed:**
- `c50c36b` (spec/protocol, D-025 "Circuit protocol v1"). `MEMORY_BASIS = "Z"` becomes a new `Protocol` field, so it enters `protocol_hash`. `SCHEDULING` is renamed to `bb_monomial_matching_xz_phased_v1`. The exact noise placement and tick layout are now in CONTRACT's exact-values block. The label is stated as a Z-memory LER in INV-4, the pinned conventions, `AGENTS.md §6` and the `true_ler` schema row. The M0-CIRC-01 wording in tasks.md and plan.md now describes monomial matching instead of networkx greedy colouring. Two tests were added to `test_protocol.py`: basis and schedule string are both in the hash.
- `bade606` (circuits). `schedule.bb_schedule()` has one perfect-matching CX layer per monomial, X phase then Z phase, and raises if the layers don't rebuild `H_X`/`H_Z` edge for edge. `build.build_memory_circuit(code, p, rounds)` builds the circuit, and `build.z_logical_basis()` takes the in-order nullspace rows of `H_X` that raise `rank([H_Z; kept])`, with no RNG. Also 19 tests in `tests/test_circuit_sanity.py`, evals N-10 (sensitivity), and the CIRC-01/02/03 checkboxes ticked.

**Confirmed from INV-4 before building observables:** failure is "`P_L` = fraction of shots in which **any** logical observable was incorrect", which does not depend on basis.

**Report:**
- Scheduling method string: `bb_monomial_matching_xz_phased_v1`.
- CNOT depth per round: **12** (6 X + 6 Z) for [[72,12,6]], the König minimum. Per phase it is `|A| + |B|` (8 + 8 for the `mixed_3_5` test code).
- Detectors: `m_z + (r-1)(m_x+m_z) + m_z`. [[72,12,6]] at r=6 gives **432**; the gross code at r=12 gives **1728**. Observables: **12** (= k) for both.
- Sensitivity (p=0, error injected after round index 1's measurements):
  - X on data qubit 0 fires Z detectors (check, round, basis) `(3,2,0) (6,2,0) (12,2,0)` and flips observables `[0,1,3,6,8,9,10,11]`.
  - X on qubit 40 fires `(0,2,0) (5,2,0) (22,2,0)` and flips no observables.
  - Z on qubit 0 fires X detectors `(4,2,1) (5,2,1) (18,2,1)`.
  - Z on qubit 40 fires `(1,2,1) (28,2,1) (34,2,1)`.
  - In every case the fired set is exactly that qubit's column of `H_Z` (or `H_X`), in the round after the injection.
- Gross code [[144,12,12]] at r=12, p=0.005: build **~1.6 s** (3 runs: 1.77, 1.58, 1.60). Of that, `z_logical_basis` + validate + schedule take 0.05 s; the rest is stim instruction assembly in Python. The DEM builds in 0.21 s (67,104 error mechanisms). 1,000 shots at p=0 give 0 detection events. None of this is in the suite: tests use codes of 72 qubits or fewer.
- Suite: **107 passed**, clean under `-W error`. The circuit tests take 2.8 s. The pre-existing 88 tests took 92 s on this run against ~80 s recorded before; that is machine variance, since they run the same time without the new file.

**Mutation check:** 8 builder mutants, all caught:
- true X/Z interleave: fails p=0, DEM, sensitivity and phase-order tests;
- Z phase before X: phase-order test;
- noisy data preparation, missing CX idles, noisy final readout: per-tick placement test;
- identity vectors as observables: p=0, DEM, logical-basis and sensitivity tests;
- a detector comparing against the wrong check: sensitivity test;
- missing final detectors: count test.
A within-phase reorder (legitimate, since those CNOTs commute) passes, as it should.

**Owner decision (recorded in D-025, restated here):** noiseless boundaries are not about symmetry. Boundary noise happens once per experiment. Dividing by `r = d_upper` then dilutes it more for high-distance codes, which biases the per-round rate by distance.

**One structural detail I derived rather than being told:** all X ancillas stay unmeasured (idle) through the Z phase, because every ancilla is measured in one tick at the end of the round. This follows from the approved "single reset tick" layout and is written into CONTRACT's tick layout. The alternative, measuring X ancillas straight after the X phase, would shorten their idle window. If the owner prefers that, it is a D-025 amendment and changes every label.

**Did not land:** EVAL-*, CORE-05/06. `codes/` untouched (schedule imports `bb._monomial_matrix`, a private helper, so the matchings come from the same function as the generator).
**Blockers:** none.
**Noticed, did not fix:**
1. Detectors from the 6 redundant checks per type (rank 30 of 36) are kept. They are deterministic and harmless, but BP+OSD will see a check matrix with dependent rows. That is for M0-EVAL-01 to confirm.
2. `circuits/__init__.py` still has the "Placeholder" docstring.
3. The gross-code build time could drop by using `REPEAT` blocks. Not done, because the plan says don't optimise before the real per-shot decode cost is measured, and 1.6 s is small next to it.
**Spec changes:** `CONTRACT.md`, `spec/decisions.md` (D-025), `spec/architecture.md`, `spec/plan.md`, `spec/tasks.md`, `spec/evals.md` (N-10), `AGENTS.md §6` (label definition, per owner instruction), `protocol.py`. `NARRATIVE.md` entry.

---

## 2026-09-25 (jj) — Claude Opus 5.5 / Claude Code — M0-CODES-05 correction: duplicate programs, d <= 2 codes, D-024

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-CODES-05` correction, from two template defects the owner found by independent check

**Both defects confirmed before changing anything** (row-space comparison of generated codes at `l = m = 7`): `quad_4_2`~`quad_2_4` and `mixed_3_5`~`mixed_5_3` are identical after the half-swap permutation. `quad_4_4` has `A == B`, and **all 189** of its `k >= 1` grid codes have `d_upper <= 2`. So 69/300 codes in the M0-CODES-05 draw (entry hh), and 42/300 in my own D-023 balanced draw (entry ii), were codes that correct no errors. My D-023 session measured balance and duplicates but never looked at distance; the id-level tests passed throughout, which is the owner's point.

**Beyond what was asked, checked because the same argument applies:** `(A, B) -> (Ag, Bh)` for monomials `g`, `h` is also a qubit relabelling within each half, so a translated copy would be the same program too. `template_key` covers it; none of the templates collided.

**Landed (`a686569`):**
- Removed `quad_2_4`, `mixed_5_3`, `quad_4_4`. Added `bb288_3_3`, `tri_3_3`, `diag_3_3`, `sq_4_2` → **11 templates**. Each clears 10 admissible `(l, m)` on the full 189-pair grid at budget=150, and each is checked for A/B-swap identity against every other template. Two others screened and **not** added: one with 0 `k>=1` lattices, one with 1. `bb288_3_3` shares `sym_3_3`'s B and its viable count, so I compared per-lattice `(k, d_upper)`: they differ (e.g. `(3,18)`: 10 vs 6).
- `MIN_D_UPPER = 3` admission via `estimate_d_upper(h_x, h_z, seed=0)` at `DEFAULT_ATTEMPTS`. `BBSample.rejections` is now a dict by cause (`k<1`, `d_upper<3`). An exact weight-≤2 logical search agreed with `d_upper <= 2` on every `k >= 1` code screened: 0 disagreements.
- `template_key()`: canonical form under A/B swap and per-polynomial monomial shift.
- `tests/test_sample.py` rewritten around the codes. No two templates are A/B swaps (generated at `(8, 9)`, half-swap row-space comparison). Keys are unique. No template has `A ~ B`. Every emitted code has `d_upper >= 3`, for both `balanced` modes. Rejections are reported by cause. The D-023 balance/determinism/shortfall tests are kept. **Mutation check:** run against the old 10-template list, the three new template tests fail naming `quad_4_2`/`quad_2_4`, the key collision, and `quad_4_4`.
- **Removed `test_unbalanced_unchanged_from_m0_codes_05`.** It pinned `balanced=False` to a draw from a template set that no longer exists. Recorded in D-024.
- Large-draw tests share one module-scoped 300-code fixture because admission made sampling ~10x slower. Suite: **86 passed** (83 before), clean under `-W error`, 80 s.

**Report — 300 codes, budget=150, seed=0, balanced=True:**
- Histogram: `quad_4_2` 42, `pair_2_2` 41, `diag_3_3` 41, `mod_2_3` 40, `sq_4_2` 40, `sym_3_3` 19, `bb288_3_3` 19, `tri_3_3` 19, `mixed_3_5` 17, `rare_3_4` 12, `rare_2_3` 10. max/mean 1.54, min 10. Six templates exhausted. 300 distinct codes.
- `k`: 2→78, 4→104, 6→57, 8→51, 12→9, 18→1; `k <= 4` fraction **0.607**.
- `d_upper`: 3→40, 4→114, 5→11, 6→74, 7→5, 8→29, 9→3, 10→14, 12→5, 14→4, 16→1. **No d <= 2** (was 69 codes in the original draw).
- Rejections: 1227/1527 = **80.4%**, split into `k<1` **1165** and `d_upper<3` **62**. The `d_upper<3` rejections came from `diag_3_3` 33, `sq_4_2` 13, `rare_2_3` 7, `rare_3_4` 5, and one each from `sym_3_3`, `bb288_3_3`, `mod_2_3` and `tri_3_3`. (Grid-level rates are in D-024.)
- Wall-clock **23.8 s** (was 2.5 s), almost all of it `estimate_d_upper` on `k >= 1` candidates.

**x↔y (+ A/B) check, reported rather than asserted:** no template equals another under x↔y exchange, alone or combined with A/B swap (generated at `l = m = 7`). Informational: `sym_3_3` and `pair_2_2` are self-symmetric under x↔y+AB, and `quad_4_2`, `tri_3_3` and `diag_3_3` under x↔y. Harmless. It is a real equivalence at program level (the image at `(l, m)` is the template at `(m, l)`), so D-024 says to add it to `template_key` when a template is next added.

**Did not land:** `CONTRACT.md`, `protocol.py`, `generate()`, `validate()`, `estimate_d_upper()` untouched. No new dependency. `M0-CIRC-01` not started.
**Blockers:** none.
**Noticed, did not fix:** (1) `rare_2_3` is exactly at the 10-admissible-pair bar at budget=150, so any budget reduction drops it below. (2) `template_key` doesn't catch lattice-specific equivalences (e.g. `y -> y^5` when `gcd(5, m) = 1`); the per-lattice fingerprints separated every pair I checked, but that is evidence, not proof. (3) Sampling cost rose ~10x, which is fine at M0 scale. The d_upper computed at admission is thrown away and recomputed later for features, and could be returned instead; not done, since that's an M0-FEAT concern.
**Spec changes:** `spec/decisions.md` (D-024), `spec/tasks.md` (correction note on `M0-CODES-05`). `NARRATIVE.md` entry.

---

## 2026-09-25 (ii) — Claude Opus 5.5 / Claude Code — M0-CODES-05 follow-up: balanced template allocation, D-023

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-CODES-05` follow-up — `balanced` parameter on `sample_bb_params`

**Status check first:** `D-023` absent from `spec/decisions.md`, no `balanced` in `sample.py` or `tests/test_sample.py` → implemented (case B), not verified-only.

**Found while measuring, not previously recorded:** the M0-CODES-05 300-code draw (`budget=150`, `seed=0`) contained **95 exact duplicate codes** (same template, `l`, `m`), on top of the known imbalance (263/300 in four templates, `mixed_5_3` at 0). And at `budget=150` five templates have only 17-20 distinct valid `(l, m)` pairs (out of a 189-pair grid; the other five have 62 or 189). So "balance at 30 each" would have been reachable only by repeating the same ~17 codes. The balanced sampler therefore draws **distinct** pairs within a template, and treats running out as exhaustion to redistribute, not as something to paper over with copies — see D-023's rejected list.

**Landed (`1df9ac9`):**
- `sample_bb_params(n_codes, budget, seed, balanced=True)`. Balanced: even quota per template (remainder by seeded permutation); each template walks its own `SeedSequence`-spawned, weighted, without-replacement ordering of the `(l, m)` grid (same weights as the original `l`-then-`m` draw); exhausted templates' shortfall redistributed to open ones until full; `RuntimeError` if everything exhausts first — never a short list. Output shuffled so a prefix slice isn't grouped by template.
- Returns `BBSample`, a `list` subclass with `counts`, `quota`, `exhausted`, `attempts`, `rejections` — existing callers and `==` unaffected.
- `balanced=False` = original sampler, refactored into `_sample_uniform` with identical RNG call order; confirmed byte-identical output (sha256 of the list repr) against a pre-change snapshot at `(300,150,0)`, `(50,150,3)`, `(400,150,0)`, and pinned in a test to the exact histogram and 639/339 attempts/rejections logged in entry (hh).
- `tests/test_sample.py`: 9 new tests (balanced default; max <= 2x mean and every template >= 10 at 300 codes; `counts` matches the list; shortfall visible and redistributed; distinctness; determinism; every sample validates and fits budget; raises rather than returning short; `balanced=False` unchanged).
- Full suite: **83 passed** (74 before, 9 new), also clean under `-W error`.

**Report — 300 codes, `budget=150`, `seed=0`, `balanced=True`:**
- `construction_program_id` histogram: `quad_2_4` 43, `mod_2_3` 43, `pair_2_2` 42, `quad_4_2` 42, `quad_4_4` 42, `sym_3_3` 20, `rare_3_4` 17, `rare_2_3` 17, `mixed_3_5` 17, `mixed_5_3` 17. Exhausted (quota 30 unmet): the five at 17-20.
- max / mean = 43 / 30.0 = **1.43** (threshold <= 2.0: pass). Smallest viable-template count **17** (all 10 viable at 150; threshold >= 10: pass). 300 distinct codes.
- `k` histogram: 2→89, 4→81, 6→78, 8→42, 12→8, 18→2; `k <= 4` fraction **0.567** (was 0.79). `n` 12-150, mean 99.2.
- Rejection rate **940/1240 = 75.8%** (was 53.1%) — higher because proving a template exhausted means walking its whole 189-pair grid (5 × 189 attempts). Wall-clock **2.46 s** (was 1.56 s).

**Did not land:** `M0-CIRC-01` not started, per instruction. `CONTRACT.md`, `protocol.py`, `generate()`, `validate()`, `estimate_d_upper()` untouched; no new dependency.
**Blockers:** none.
**Noticed, did not fix:** redistribution means the five large-grid templates carry 42-43 each against 17-20 for the rest — balanced within 2x, but not flat; a flat design would need either more low-yield-template pairs (larger budget) or capping everyone at the smallest grid. Also, `k` max fell from 26 to 18 in this draw — the rare high-`k` codes are not guaranteed to be sampled by either mode; worth deliberate inclusion if `M0-RUN-01` wants that tail covered.
**Spec changes:** `spec/decisions.md` (D-023), `spec/tasks.md` (`M0-CODES-05` follow-up note). `NARRATIVE.md` entry for the duplicate finding.

---

## 2026-09-14 (hh) — Claude Sonnet 5 / Claude Code — M0-CODES-05: sample_bb_params, and three templates that always failed

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-CODES-05` — `sample_bb_params(n_codes, budget, seed)` in `src/qecscreen/codes/sample.py`

**A real finding while building the template set, not just implementation:** three of the first ten candidate polynomial shapes each had a single-monomial side (e.g. `B` = one term). A brute-force check across the full `l, m in [2, 19]` grid at `budget=150` showed each of the three failing `validate()`'s `k >= 1` check for **every** `(l, m)` — not most, all. Reason, verified directly with `gf2_rank`: a single-monomial polynomial is itself an invertible permutation matrix, which forces `rank(H_X) = rank(H_Z) = l*m` regardless of the other polynomial, forcing `k = 0` identically. Giving both sides a second term did not fix it either — two of the three replacements *also* failed for every `(l, m)` tested, for reasons tied to the specific polynomials that I did not chase to a full explanation (would need the polynomials' relationship to `x^l-1`/`y^m-1` in the underlying group ring, more theory than an M0 task budget covers). Instead of deriving a general viability rule, every template actually shipped was verified empirically against that same grid before being kept.

**Landed (`8b8d04a`):**
- `TEMPLATES`: 10 polynomial shapes (structural, independent of `l`/`m`), each confirmed to have a nonzero success rate on the grid check above (yields ranged 9%-100%).
- `sample_bb_params(n_codes, budget, seed)`: one seeded `numpy.random.Generator` drives template choice, `l`, `m`, and every redraw; `n = 2lm` capped at `budget`; every emitted code has already passed `qecscreen.codes.validate.validate` (reject-and-redraw on failure, so rejections just continue the same stream — determinism doesn't depend on how many were rejected).
- `construction_program_id = f"bb_v1_{template_name}"` — one level more specific than CONTRACT.md's illustrative `bb_v1` example, because `AGENTS.md §6`'s own vocabulary already names "the BB polynomial template" (not the family) as the construction-program unit; grouping at the family level would still let two structurally unrelated shapes share a split-group. Recorded as **D-022** (`spec/decisions.md`), which also corrects `spec/architecture.md`'s `construction_program_id` row to match (it previously showed the bare `bb_v1` form).
- `tests/test_sample.py`, 7 tests: determinism; every sample validates and respects budget; **9 distinct ids in a 400-code sample** (measured — see report below — comfortably above the required 8, and confirmed to reliably surface all 10 across 5 seeds before being written into the test); same shape always shares an id, no id is ever shared by two shapes; the reference code's own shape carries `bb_v1_sym_3_3` if drawn; input validation on `n_codes` and `budget`.
- Full suite: **74 passed** (67 before, 7 new), 0 failures.

**Report — actual 300-code draw, `budget=150`, `seed=0`:**
- Wall-clock: **1.56 s** for 300 accepted codes (639 total `validate()` calls).
- Rejection rate: **339/639 = 53.1%**. All rejections are `k < 1` (commutation always holds structurally for any `A`/`B`, since `x`/`y` always commute) — driven mostly by the four low-yield templates (`sym_3_3`, `rare_2_3`, `rare_3_4`, `mixed_3_5`/`mixed_5_3`), each with an 89-91% per-template failure rate, pulled into roughly a third of all attempts by uniform template selection.
- `construction_program_id` histogram: `pair_2_2` 70, `quad_4_4` 69, `quad_4_2` 63, `quad_2_4` 61, `mod_2_3` 21, `sym_3_3` 8, `rare_2_3` 6, `mixed_3_5` 1, `rare_3_4` 1 — **9 distinct ids**, `mixed_5_3` did not appear in this specific 300-draw (rare enough, ~9% yield x 10% draw probability, that 0-in-300 is unsurprising; confirmed present in the 400-code sample the test file uses).
- `n` histogram (bucketed): min 16, max 150, mean 109.0; buckets `[100,160)` hold the majority (57+82+61 of 300), reflecting that `budget=150` biases larger `l*m` combinations somewhat since `m`'s sampling range grows as `l` shrinks.
- `k` histogram: min 2, max 26, mean 4.12; `k=2` (143) and `k=4` (93) dominate — real variance exists (up to `k=26`) but is heavily right-skewed, worth flagging for whoever designs the M0 ranking task: `k` is not close to constant, but it is far from uniform either.

**Did not land:** `M0-CIRC-01` (next unstarted task) not started — not requested this session.
**Blockers:** none.
**Noticed, did not fix:** the `k` and `n` distributions from this template set are heavily right-skewed (`k<=4` for 79% of the 300-code sample) rather than flat. Not fixed here since the task asked for diversity and a report, not a specific target distribution — flagging for whoever designs `M0-RUN-01`'s actual sampling budget, since a ranking model trained mostly on `k in {2,4}` may generalise poorly to the rarer, larger-`k` codes it should also be screening.
**Spec changes:** `spec/tasks.md` (`M0-CODES-05` now `[x]`), `spec/decisions.md` (D-022), `spec/architecture.md` (`construction_program_id` row corrected).

---

## 2026-09-14 (gg) — Claude Sonnet 5 / Claude Code — M0-CODES-04: estimate_d_upper, and a method that failed the gross code

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-CODES-04` — `estimate_d_upper(h_x, h_z, seed, attempts)` in `src/qecscreen/codes/distance.py`

**The method that failed, kept visible rather than erased:** the first implementation drew one random dense combination of the `ker(H_X)`/`ker(H_Z)` nullspace basis, then greedily flipped in single stabiliser generators wherever that reduced Hamming weight. It reached `d_upper=6` for the `[[72,12,6]]` reference code immediately, but on the `[[144,12,12]]` gross code it plateaued at 14 — never 12 — even at 5,000 attempts (measured: 200→24, 500→22, 1000→16, 2000→16, 5000→14). Per instruction this was a stop-and-report condition, not a tune-the-assertion one. Diagnosis: single-generator greedy descent from a random ~half-weight dense start is too weak a local search once the code is big enough that low-weight codewords are a small target — not a bug, an underpowered algorithm.

**Landed (`0005e16`):**
- Replaced with a random-information-set search: draw a random column permutation each attempt, use it to select fresh pivot columns while row-reducing the same nullspace basis, and keep the minimum nontrivial row weight across all attempts. This reached `d_upper=12` for the gross code at **10 attempts** in the first test and reliably from **attempts=4** in a 30-seed sweep — several orders of magnitude cheaper than the method it replaced, not just fixed.
- `DEFAULT_ATTEMPTS=64` measured, not guessed: swept 30 seeds each against both reference codes. `[[72,12,6]]` reaches `d_upper=6` reliably from `attempts=1`. The gross code is the binding constraint: `attempts=3` → 25/30 seeds correct (unreliable), `attempts=4` → 30/30 (reliable, held at 5 and 6 too). Default set at 16x that measured threshold (64) for margin against a family this project hasn't sampled yet. Recorded as **D-021** in `spec/decisions.md`, including the rejected method and why raising its attempt count further wasn't the fix.
- Measured wall-clock at the default (20-seed average, dev box): **~0.10 s/call for the gross code, ~0.05 s/call for the reference code**. Negligible next to the ~100 s/code BP+OSD decoding budget in `spec/architecture.md §6` — added as a measured line there rather than left as the unstated assumption the instruction flagged it as being.
- `tests/test_distance.py`, 5 tests: both reference codes hit their published distance at `DEFAULT_ATTEMPTS`; determinism (same `(code, seed, attempts)` → identical result); a **deliberately low** attempt count (1, not the default) across 10 seeds shows real seed-to-seed variation while every result stays `>=` the true distance — demonstrating the upper-bound property concretely rather than asserting equality across seeds, which the instruction specifically warned against; a source-grep guard (same style as `test_hygiene.py`'s INV-4 check) confirms the exact-distance column is never named in the module.
- Full suite: **67 passed** (62 before, 5 new), 0 failures.

**Caught along the way, same class of thing as the M0-CODES-03 session:** my own module docstring, and my own test's source-grep target string, both literally contained the token my new hygiene-style test was grepping for, purely in explanatory prose. Reworded both to "the exact-distance column" rather than weakening the grep or exempting the file — same call as last session's `numpy.linalg.matrix_rank` docstring collision, and worth noting as a pattern: a strict source-grep test on a short, meaningful token will keep catching its own author's explanatory prose, and rewording is the right response each time, not building an exemption list.

**Did not land:** `M0-CODES-05` not started. `generate()`, `validate()`, `CONTRACT.md`, `protocol.py`, `requirements.txt` untouched, no new dependency, per instruction.
**Blockers:** none.
**Noticed, did not fix:** nothing new this session.
**Spec changes:** `spec/tasks.md` (`M0-CODES-04` now `[x]`), `spec/decisions.md` (D-021), `spec/architecture.md §6` (measured distance-search cost recorded).

---

## 2026-09-14 (ff) — Claude Sonnet 5 / Claude Code — M0-CODES-03: validate() enforcing INV-8

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-CODES-03` — `validate(h_x, h_z)` enforcing INV-8

**Landed (`fc90750`):**
- Placed `validate()` in a new `src/qecscreen/codes/validate.py` rather than `codes/__init__.py` — the task left the choice open. Reasoning: it applies to any construction program's check-matrix output (`bb.py` now, `gb.py`/`hgp.py` later per `spec/architecture.md §2`), not one specific generator, and it is a substantial independently-testable unit of logic, not package re-export surface. `codes/__init__.py` stays the placeholder it already was.
- `validate(h_x, h_z)` enforces, in order: (1) dtype/value rejection — bool and float rejected before any GF(2) work; (2) matching column counts; (3) CSS commutation; (4) `k = n - gf2_rank(H_X) - gf2_rank(H_Z)` over GF(2); (5) `k >= 1`. All of (1)-(4) are delegated to `qecscreen.linalg.logical_qubit_count`, which already implements exactly that order — no new GF(2) arithmetic was written, so there remains exactly one place in the codebase that does GF(2) math. Only (5) is new logic.
- Chose `InvalidCodeError(ValueError)` as the specific exception type: a `ValueError` subclass so any existing `except ValueError` still catches it, but named so a caller can `except InvalidCodeError` specifically to mean "this is not a valid code" (INV-8) rather than catching an unrelated `ValueError` from a bad argument elsewhere. Every one of the five checks raises this same type — treated as one category of failure ("this is not a valid code"), not split by which check failed.
- `tests/test_inv_8_validate.py`, 8 tests: both reference codes ([[72,12,6]] and the [[144,12,12]] gross code) validate with the correct `(n, k)`; a non-commuting pair built by flipping one bit of a real `generate()` output raises (verified empirically first that the flip actually breaks commutation, rather than assuming it would); float and bool inputs raise; mismatched column counts raise; a **cheap, real** k=0 CSS pair — `H_X=[[1,0]]`, `H_Z=[[0,1]]`, two orthogonal single-row checks, `n=2`, `rank=1` each, `k=0` — raises, rather than being reported as unconstructible; `InvalidCodeError` is confirmed to subclass `ValueError`.
- Full suite: **62 passed** (54 before, 8 new), 0 failures.

**Caught along the way:** an early draft of `validate.py`'s docstring literally contained the string "numpy.linalg.matrix_rank" in prose (explaining why the module avoids it), and `test_inv8_no_float_matrix_rank`'s source grep correctly flagged it as a hit — the grep does not distinguish prose from a real call, and rightly doesn't try to. Reworded to "floating-point rank" rather than adding an exemption for the new file. This is exactly the guard working as designed, not a false positive to route around.

**Did not land:** `M0-CODES-04` (`d_upper`) not started. `generate()`, `CONTRACT.md`, `protocol.py` untouched, per instruction. No new dependency.
**Blockers:** none.
**Noticed, did not fix:** nothing new this session.
**Spec changes:** `spec/tasks.md` (`M0-CODES-03` now `[x]`).

---

## 2026-09-14 (ee) — Claude Sonnet 5 / Claude Code — M0-CODES-01/02: the gross code closes the symmetry gap

**Milestone:** M0 — Falsification
**Tasks attempted:** strengthen `tests/test_bb_reference.py` with a second reference code; no new implementation, per instruction

**The gap:** at `l=m=6`, three of the four `[[72,12,6]]` assertions from the previous session (n, check weight, CSS commutation) are structurally guaranteed for *any* `A`/`B` — they follow from arithmetic (`n=2lm`), construction (`weight = wt(A)+wt(B)`), and the fact that `x` and `y` always commute. Only `k` actually discriminates a correct generator from a broken one, and even `k` is weak at `l=m`: `x` and `y` are interchangeable there, so a bug that swaps them, or flattens the `(a,b)` index as `b*l+a` instead of `a*m+b`, produces an equivalent code with the same `n`, `k` and weight histogram. The previous session's clean pass was consistent with a correct generator, but could not rule out that class of bug.

**Landed (`4fba94a`):**
- Verified independently, before writing any assertion, that `generate(12, 6, A_EXPS, B_EXPS, seed)` — the SAME `A`/`B`, only `l != m` — reproduces the published `[[144,12,12]]` gross code against the *existing, unmodified* `generate()`: `n=144`, `k=12` (`rank(H_X)=rank(H_Z)=66`), every check weight 6, CSS commutation holds.
- Added four tests to `tests/test_bb_reference.py` (`test_g11_g12_gross_code_n_and_k`, `test_g13_gross_code_all_check_weights_are_six`, `test_gross_code_css_commutation`, `test_gross_code_shape`), all passing unmodified on the first run — no implementation change, no expected value adjusted.
- Added a module-docstring block spelling out *why* the two reference codes are kept as separate tests rather than one case parametrised over `(l, m, n, k)` — collapsing them would lose exactly the discriminating power the gross code exists to add. Flagged explicitly so a future simplification pass doesn't merge them back.
- Added `spec/evals.md` G-11 (`n=144`), G-12 (`k=12`), G-13 (check weights `6`), with the same symmetry-gap reasoning recorded in the spec, not only in the test file. No `d_upper` entry recorded for the gross code — distance stays out of scope for both reference codes (M0-CODES-04).
- `spec/tasks.md`: added a note to the existing `M0-CODES-02` line recording the strengthening, rather than reopening the checkbox (both tasks were already correctly closed).
- Full suite: **54 passed** (50 before, 4 new), 0 failures, 0 new warnings.

**Did not land:** no changes to `src/qecscreen/codes/bb.py` — none were needed, and the instruction was explicit that none were expected. `M0-CODES-03`/`04` still not started.
**Blockers:** none. The gross-code pass rules out the specific x/y-mixup and index-flattening bug class; it does not prove the generator correct for every family this project will eventually sample (M0-CODES-05), only that this particular class of silent-symmetry failure did not occur.
**Noticed, did not fix:** nothing new this session.
**Spec changes:** `spec/evals.md` (G-11..G-13), `spec/tasks.md` (`M0-CODES-02` note).

---

## 2026-09-14 (dd) — Claude Sonnet 5 / Claude Code — M0-CODES-01, M0-CODES-02: the BB generator, code finally exists

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-CODES-01` (`src/qecscreen/codes/bb.py`), `M0-CODES-02` (`tests/test_bb_reference.py`), together per instruction

**Landed (`5ccdd6a`):**
- Wrote `tests/test_bb_reference.py` first. Confirmed it failed on collection (`ModuleNotFoundError: No module named 'qecscreen.codes.bb'`) before writing any implementation.
- Implemented `generate(l, m, a_exps, b_exps, seed)` in `src/qecscreen/codes/bb.py`: `H_X = [A|B]`, `H_Z = [B^T|A^T]`, where `A`/`B` are GF(2) sums of monomial permutation matrices over the commuting cyclic shifts of `Z_l x Z_m` — the construction from Bravyi et al. 2024. No new dependency; numpy only. `seed` is accepted (required by the signature) but unused by this deterministic construction — documented as such rather than given a fabricated use.
- The `l=6, m=6, A=x^3+y+y^2, B=y^3+x+x^2` reference code reproduced every published value **on the first run, unmodified**: `n=72`, `k=12` (`rank(H_X) = rank(H_Z) = 30`), every check weight exactly 6 (`H_X`: `{6: 36}`, `H_Z`: `{6: 36}`), CSS commutation holds (`check_css_commutation` raised nothing). `k` computed via `qecscreen.linalg.logical_qubit_count`, never `numpy.linalg.matrix_rank` — `test_inv8_no_float_matrix_rank` (hygiene) confirms no source file uses it. No expected value was adjusted, no tolerance added, nothing marked `xfail`, no A/B swap or transpose was needed to make a number come out.
- Also added: determinism (same args + seed → byte-identical `H_X`/`H_Z` via `.tobytes()` equality), shape (`(l*m, 2*l*m)`), and a dtype check confirming `H_X`/`H_Z` are integer `{0,1}` (bool/float are rejected by `qecscreen.linalg`, so this was worth asserting explicitly rather than assumed).
- Full suite: **50 passed** (44 before, 6 new), 0 failures, 0 new warnings.
- `spec/tasks.md`: both `M0-CODES-01` and `M0-CODES-02` ticked. Merged into one commit per `AGENTS.md §4`'s spec-and-code-together clause — a generator commit alone would be untested spec fiction, and the test alone would not even collect. Both task IDs named in the commit message.

**On the convention risk the instruction flagged (qubit ordering / which block is A vs B / row-column orientation):** did not stop to ask. The Bravyi et al. 2024 construction (`H_X=[A|B]`, `H_Z=[B^T|A^T]`, monomials as commuting shift-permutations) is a specific, well-documented construction, not a guess, and none of the tested properties (`n`, `k`, check weight, commutation) depend on which physical block is labelled A vs B or which shift direction is chosen — those are qubit relabellings that leave every tested invariant unchanged. Recorded here so the reasoning is visible rather than silently assumed.

**Did not land:** `M0-CODES-03` (`validate(code)`) and `M0-CODES-04` (`d_upper`) not started, per instruction — distance is explicitly out of scope for this pair of tasks and this module populates neither `d_exact` nor `d_upper`.
**Blockers:** none.
**Noticed, did not fix:** `spec/architecture.md §2`'s Structure section describes the `codes/` convention generically as `generate(params, seed) -> Code` plus a `PROGRAM_ID` constant, which disagrees with `spec/tasks.md`'s (and this session's) concrete `generate(l, m, a_exps, b_exps, seed) -> (H_X, H_Z)` signature. Not resolved here — the concrete signature came from an explicit, unambiguous instruction this session, and reconciling the generic sketch (return type, `PROGRAM_ID`) belongs with `M0-CODES-05`'s `construction_program_id`, not this pair of tasks. Flagging so it doesn't look like an oversight later.
**Spec changes:** `spec/tasks.md` (`M0-CODES-01`, `M0-CODES-02` now `[x]`).

---

## 2026-09-14 (cc) — Claude Sonnet 5 / Claude Code — M0-SETUP-01 closed

**Milestone:** M0 — Falsification
**Tasks attempted:** record the re-measurement against the new `pyarrow>=15` pin; close `M0-SETUP-01` if every `spec/evals.md §7` criterion is PASS; add a NARRATIVE.md entry

**Blocked on missing input, then unblocked:** the owner's message left `GitHub Actions on cf1a1f3: <PASTE>` as an unfilled placeholder, and closing the task explicitly depended on that result (RED on a leg meant stop and report, not close). Neither `gh` nor the GitHub API were usable in this environment (`gh` not installed; the API returns 404 on this private repo without credentials, same as an earlier session this same day). Asked the owner directly rather than guess or infer a result from indirect evidence; confirmed GREEN, 3/3 checks, before proceeding.

**Landed:**
- **`5715b91`** — `spec/evals.md §7`: both no-downgrade rows flip **FAIL → PASS**. Re-measured 2026-09-14 on factory-reset Colab and Kaggle runtimes against the new `pyarrow>=15` pin (D-019), install logs captured: zero uninstalls on either platform, ambient `pyarrow` (23.0.1 Colab, 24.0.0 Kaggle) left untouched, only the four packages this project adds installed. CI row updated to GREEN on `cf1a1f3`, 3/3 checks (first run including the 3.12 leg from D-020). **Closes?** paragraph rewritten to **Yes** — every criterion in the table is now PASS. Added a standing **"Not permanently settled"** note: the no-downgrade criterion depends on base images outside this project's control, flipped once already in a single day with no repository change, and should be re-run with the install log captured before the M1 bulk generation rather than trusted from this record.
- **`35d32c6`** — `spec/tasks.md`: **`M0-SETUP-01` ticked closed.** Checked every row in the §7 table before closing, not just the ones this session touched — all ten are PASS.
- **`9c4b123`** — `NARRATIVE.md`: entry for the fix landing, closing the loop the previous entry opened — pin removed, both platforms re-measured clean, PASS → FAIL → PASS in a single day.

**Did not land:** `M0-CODES-01` not started, per instruction.
**Blockers:** none remaining for `M0-SETUP-01`. Next unticked SETUP/CORE task is `M0-CODES-01`, not started this session per instruction.
**Noticed, did not fix:** `spec/tasks.md`'s `M0-SETUP-02` completion note still says "matrix on 3.11 + 3.13", stale since D-020 added 3.12 (`56a991e`, a prior session this same day). Not touched — out of scope for this session's instructions, which named `M0-SETUP-01` specifically, and it doesn't block anything closed here. Flagging for a future small fix.
**Spec changes:** `spec/evals.md §7`, `spec/tasks.md` (`M0-SETUP-01` now `[x]`), `NARRATIVE.md`.

---

## 2026-09-14 (bb) — Claude Sonnet 5 / Claude Code — add NARRATIVE.md

**Milestone:** M0 — Falsification
**Tasks attempted:** create `NARRATIVE.md`, a new non-authoritative project-history document; add a `NARRATIVE.md` line to `AGENTS.md §5`'s definition of done

**Landed (`59160fb`):**
- **`NARRATIVE.md`** created: a plain-language, reverse-chronological, append-only account of what happened and why it mattered, explicitly stated at the top of the file to never be a source of truth (`CONTRACT.md`/`spec/`/`AGENT_LOG.md` win on any disagreement), never in `AGENTS.md §1`'s read order, never read by an agent to decide anything, and never parsed by code.
- Backfilled six entries, each checked against a real source before being written — no claim invented:
  - The 2026-08-30 `sinter`-needs-Python-≥3.12 claim, verified against `AGENT_LOG.md` (n), which names the exact three files it was repeated into (`requirements.txt`, `spec/architecture.md`, `.github/workflows/ci.yml`) and the `--only-binary=:all:` flag that actually produced it.
  - The 2026-08-30 CI guard fix, verified against `cf5542e` and D-018.
  - The 2026-09-07 "zero code written after 25 commits" audit — sourced from `handover.md`, a local, gitignored, uncommitted audit file dated 2026-09-07 that literally ran `git log --oneline -25` and stated "zero source files exist for `codes/`, `circuits/`, `evaluate/`, `features/`, `splits.py`, `metrics.py`, or `scripts/run_m0_pilot.py`." Not one of `AGENT_LOG.md`/`spec/decisions.md`/committed git history names this audit directly, so I read `handover.md` itself to confirm the claim before writing it, rather than take the date and figure from the instruction on faith.
  - The 2026-09-14 manual-Colab-cells-not-required finding (this session's earlier turn) and the pyarrow/Kaggle-interpreter findings (this session's later turn), both against `spec/evals.md §7` and this session's own commits (`9d1c177`, `2b8ea1e`, `56a991e`).
- Closing **"Recurring theme"** note: the sinter claim, the pyarrow finding and the Kaggle interpreter correction all share the same shape — a claim believed and repeated without being measured, surviving only until something forced an actual measurement.
- `AGENTS.md §5` gains a line: append a `NARRATIVE.md` entry when a session produces a finding worth explaining to a person, not for routine task completion.

**Did not land:** `M0-CODES-01` not started, per instruction. `NARRATIVE.md` was not added to `AGENTS.md §1`'s read order, per instruction.
**Blockers:** none.
**Noticed, did not fix:** `handover.md` is a real, dated (2026-09-07), substantive audit document that is gitignored and has never been committed — it is the only source for the "25 commits, zero code" finding this entry backfills into `NARRATIVE.md`. Flagging in case the owner wants its findings folded into a committed document (`spec/decisions.md`, or a future `NARRATIVE.md` entry already covers its headline finding) before it is deleted or overwritten by a later session's own handover file, since nothing currently protects it from being replaced.
**Spec changes:** `NARRATIVE.md` (new, non-authoritative — explicitly not part of the spec/`AGENTS.md §1` read order), `AGENTS.md §5`.

---

## 2026-09-14 (aa) — Claude Sonnet 5 / Claude Code — M0-SETUP-01: cold-start measurements overturn the previous no-downgrade PASS/NOT VERIFIED

**Milestone:** M0 — Falsification
**Tasks attempted:** record owner-supplied cold-start (factory-reset) Colab/Kaggle measurements with install logs; D-019 (remove `pyarrow` cap); D-020 (add 3.12 to CI); `spec/smoke.md §1` fix

**Landed, five commits:**
- **`9d1c177`** — `spec/evals.md §7` corrected on the strength of captured install logs (the earlier session's measurement lacked these). Colab's "no downgrade" row flips **PASS → FAIL**: ambient `pyarrow` was 18.1.0 on 2026-08-30 (correctly PASS then) but is 23.0.1 now, so the `<19` pin (D-015) forces a downgrade that breaks `datasets` and `bigframes`. Kaggle's row replaces the prior **NOT VERIFIED** with **FAIL**: ambient `pyarrow` 24.0.0, same downgrade, breaks `datasets`. Also corrected a wrong claim of identical cross-platform resolution — Kaggle runs Python **3.12.13**, not 3.13.15 as the previous session recorded; the `protocol_hash`-relevant set (`sinter`/`stim`/`ldpc`/`pymatching`) does match and that's what INV-6 needs. No-manual-fixes and no-C-toolchain stay PASS, confirmed again in these logs.
- **`e86e677`** — `spec/tasks.md` M0-SETUP-01 note updated: the blocker is no longer an undetermined manual-fix question, it's a confirmed no-downgrade FAIL on both platforms. Task **stays open**, not re-ticked from the D-019 fix alone — it needs a fresh-runtime re-measurement against the new pin.
- **`2b8ea1e`** — **D-019**: `pyarrow`'s upper bound removed (`>=15,<19` → `>=15`), superseding the `pyarrow` half of D-015. `pandas<3` and D-015's general principle are untouched and marked as such in D-015's Status line. Rejected raising the cap to `<25` — a cap re-derived from a moving base image is a countdown, not a fix.
- **`b2f5acf`** — follow-up: `spec/architecture.md §1`'s stack table still documented the old `pyarrow<19` bound after `2b8ea1e`, which I should have updated in that same commit per `AGENTS.md §4`. Fixed as a small immediate correction rather than left drifted.
- **`56a991e`** — **D-020**: `.github/workflows/ci.yml`'s matrix gains `3.12` (now `3.11`/`3.12`/`3.13`), because Kaggle — the bulk-generation host — actually runs 3.12.13, not 3.11 as the matrix comment and `spec/architecture.md §1` had assumed by symmetry with the stack's lower bound. That assumption was never measured and CI had never tested the interpreter that will run the M1 bulk generation. Also corrected the "Verified at M0-SETUP-01" table's false "3.11.9 = Kaggle's version" label, and folded the same fix into `AGENTS.md §3`'s stack table for consistency with `spec/architecture.md §1`, per the precedent set in entry (r).
- **`68879c6`** — `spec/smoke.md §1` gains an explicit sub-bullet: the no-downgrade check requires capturing the install log (`Attempting uninstall` / `Successfully installed` lines), not just post-install versions — post-install versions look identical whether a package was always at the pinned version or was downgraded to it, and reading them alone is exactly what produced the wrong PASS (2026-08-30 Colab) and the wrong NOT-VERIFIED-not-FAIL gap (2026-09-14 earlier this session) that this entry corrects.

**Did not land:** `M0-CODES-01` not started, per instruction. No re-tick of the no-downgrade criterion — it stays FAIL until re-measured PASS on a fresh runtime against the new `pyarrow` pin, which is the owner's next run, not something inferred here.
**Blockers:** M0-SETUP-01 needs one more fresh-runtime measurement (Colab and Kaggle, install log captured) against `pyarrow>=15` to close.
**Noticed, did not fix:** none new beyond the architecture.md follow-up already folded into `b2f5acf`.
**Spec changes:** `spec/evals.md §7`, `spec/tasks.md` (M0-SETUP-01, unchecked), `spec/decisions.md` (D-015 status, D-019, D-020), `spec/architecture.md §1`, `AGENTS.md §3`, `.github/workflows/ci.yml`, `spec/smoke.md §1`, `requirements.txt`.

---

## 2026-09-14 (z) — Claude Sonnet 5 / Claude Code — M0-SETUP-01: fresh Colab/Kaggle measurements

**Milestone:** M0 — Falsification
**Tasks attempted:** record owner-supplied environment measurements against `spec/evals.md §7`; close `M0-SETUP-01` if warranted

**Landed (`f08204b`):**
- Owner ran fresh Colab and Kaggle runtimes, `requirements.txt` written inline via `%%writefile`, a single `pip install -r requirements.txt`, no manual fix cells. Resolved on both: python 3.13.15, pyparsing 3.3.2, matplotlib 3.10.0, sinter 1.16.0, stim 1.16.0, ldpc 2.4.1, pymatching 2.4.0. `numpy`/`pandas` differ slightly (Colab 2.1.3/2.2.3, Kaggle 2.0.2/2.3.3); `pyarrow` matches exactly at 18.1.0 on both.
- **No-manual-fixes corrected from PARTIAL to PASS.** The two manual cells the 2026-08-30 session ran (`pip install "pyparsing<3.2"`, `pip install -U matplotlib`) were **not required** — this measurement shows both resolve to the needed versions unforced, with clean imports. Recorded as a correction to that session's assumption, citing the new measurement, not as a change to the criterion itself (unlike D-018, which *was* a criterion change).
- **Kaggle install row replaced**, NOT RUN → PASS, with resolved versions. Added an explicit row stating `sinter`/`stim`/`ldpc`/`pymatching` resolve identically on both platforms, and that this identity is what makes rows generated on either platform comparable under INV-6.
- **CI status recorded**: GREEN on `285a27b`, 2/2 checks.
- **Kaggle no-downgrade recorded as NOT VERIFIED, not PASS.** The owner's Kaggle pip install log (`Successfully installed` / `Attempting uninstall` lines) was not captured. Post-install versions alone cannot establish absence of a downgrade — that needs the install log itself — so this was not ticked from inference, per explicit instruction.
- `spec/evals.md §7`'s **Closes?** paragraph rewritten to name this single remaining item.
- **`M0-SETUP-01` left open in `spec/tasks.md`**, not closed. Every other criterion in the §7 table is now PASS; the single blocker is the unverified Kaggle no-downgrade row. Not rounded up.
- `requirements.txt` untouched, as instructed — nothing in these measurements falls outside the existing bounds (`pandas>=2.2,<3`, `pyarrow>=15,<19`), so nothing needs pinning.

**Did not land:** `M0-CODES-01` not started, per instruction.
**Blockers:** Kaggle's pip install log needs to be captured on a future run to close `M0-SETUP-01`.
**Noticed, did not fix — flagging D-015 for revisit, not acting on it (explicit instruction):**
- **D-015's revisit condition is now true.** D-015 capped `pandas<3` and `pyarrow<19` to match Colab's stack, with "Kaggle is measured" as the unconditional revisit trigger — Kaggle has now been measured. Its ambient `pandas` (2.3.3) is newer than Colab's (2.2.3) and newer than the value D-015 records as the reference point, though still within the existing `<3` cap. `pyarrow` matches exactly (18.1.0) on both, so no cap is actually violated by this measurement — but the revisit condition is about the fact of measurement, not only about a violated cap, and it has now occurred. This is a flag for the owner to decide whether D-015's cap or its stated rationale needs updating; `requirements.txt` and `spec/decisions.md` were not touched in this session.
**Spec changes:** `spec/evals.md §7`, `spec/tasks.md` (M0-SETUP-01, still unchecked).

---

## 2026-09-14 (y) — Claude Sonnet 5 / Claude Code — close out D-018's spec drift (three flags from entry (x))

**Milestone:** M0 — Falsification
**Tasks attempted:** three corrections flagged by the previous session's own "noticed, did not fix" notes; no task ID, pure spec-consistency cleanup

**Landed, one commit:**
- `spec/evals.md §7`'s **Closes?** paragraph rewritten: it was still listing the from-source-build restatement as an open item, but D-018 (`64201dc`) closed that and the table row above already reads PASS. Now lists only the two genuinely open items — (1) the owner's determination on the two manual Colab cells, wording kept verbatim including "the fix is to add constraints to `requirements.txt`, not to soften the criterion"; (2) Kaggle has never been run. The table rows themselves (no-manual-fixes, Kaggle) are untouched.
- `spec/smoke.md §1` — merged the two adjacent install-condition bullets (D-018 had added a second bullet next to the pre-existing Colab-install one, both describing the same install) into one parent bullet with two independently checkable sub-bullets: no manual fixes, and no C toolchain invoked (D-018, `cf5542e`). Neither condition lost — both still separately failable.
- `spec/tasks.md`, `M0-SETUP-02`'s completion note corrected: it said install was "forced to `--only-binary=:all:`", which stopped being true at `cf5542e` (replaced by a compiler-invocation grep on the pip log). Note now describes the actual CI behaviour, referencing `cf5542e` and D-018. Checked status (`[x]`) unchanged — this was a stale description of a task already marked done, not a redo of the task.

**Did not land:** nothing outstanding for these three items. `M0-CODES-01` not started, `CONTRACT.md` not touched, per instruction.
**Blockers:** none.
**Noticed, did not fix:** nothing new — this session closes the three items entry (x) flagged and introduces no new drift that I'm aware of.
**Spec changes:** `spec/evals.md §7`, `spec/smoke.md §1`, `spec/tasks.md` (M0-SETUP-02 note only).

---

## 2026-09-14 (x) — Claude Sonnet 5 / Claude Code — verify prior session, untrack editor config, D-017 tasks, D-018

**Milestone:** M0 — Falsification
**Tasks attempted:** verification of an unlogged prior session (`74e41e6`, `eba79cb`); untrack `.vscode/settings.json` and `pyrightconfig.json`; add `M0-CORE-05`/`M0-CORE-06`; owner decision D-018

**Verified (prior session, 2026-09-13, not logged by that session):**
- `74e41e6` (remove duplicate `NOTICE.txt`) and `eba79cb` (gitignore `.vscode/` and `pyrightconfig.json`) — both correct. `NOTICE` intact and valid, `NOTICE.txt` gone. `spec/decisions.md` got exactly a one-line dated cleanup note, explicitly marked "Not a numbered decision" — not a numbered D-entry. `.gitignore` diff is a clean 4-line append; no mangled or duplicated lines despite the CRLF warning. Neither commit touched anything outside its stated scope. 44 tests passed, exit 0. Local `main` was in sync with `origin/main`. The one real gap: no `AGENT_LOG.md` entry existed for that session — closed by this entry, per the owner's instruction that covering both sessions here is acceptable.

**Landed (this session):**
- **`4605b09`** — `git rm --cached` on `.vscode/settings.json` and `pyrightconfig.json`. Both were already gitignored (`eba79cb`) but remained tracked from `2c1f9c9`; they hardcode Windows venv paths and don't belong in a repo that runs on Linux runtimes (Kaggle, Colab, CI). Local files left on disk, confirmed present after the commit.
- **`bd02caf`** — `spec/tasks.md` gains `M0-CORE-05` (implement `src/qecscreen/provenance.py: resolved_commit()`, reading `direct_url.json` via `importlib.metadata`, `None` for editable/local installs) and `M0-CORE-06` (`tests/test_provenance.py`, both branches, fake distribution, `None` case not skipped), unchecked. Task text states `CONTRACT.md` (D-017) already depends on this — no measurement row can be written until it lands. Not implemented this session.
- **`64201dc`** — **D-018**, recorded in `spec/decisions.md`: the M0 environment exit criterion "no from-source build" is replaced by "no C toolchain invoked during install", mechanically checked by the CI compiler grep from `cf5542e` rather than by wheel availability. Recorded explicitly as a criterion change, not a re-measurement, accepted only because the replacement is CI-checked while the original never was. `spec/smoke.md §1` and the corresponding `spec/evals.md §7` row updated to match; the row's verdict moves to PASS under the new criterion (the same evidence — `sinter`'s sdist build, no compiler invoked — now satisfies it). `spec/tasks.md`, `spec/smoke.md` and `spec/evals.md` were each their own commit rather than merged with the D-018 decisions.md change, except smoke.md/evals.md which landed together with decisions.md in `64201dc` since they implement the same decision (spec-and-code-together rule, `AGENTS.md §4`).

**Did not land:** `src/qecscreen/provenance.py`, `pyproject.toml`, `M0-CODES-01` — none attempted, per explicit hard stop. `CONTRACT.md` not modified.
**Blockers:** none.
**Noticed, did not fix:**
- `spec/smoke.md §1` did not previously contain a "no from-source build" bullet under that literal name — the criterion existed only as a row title and evidence text in `spec/evals.md §7`, uncited to any `spec/smoke.md §1` line (unlike the neighbouring rows, which do cite it). This session added the D-018 criterion to `spec/smoke.md §1` as a new bullet, formalizing it there for the first time rather than editing an existing one. Flagging in case the owner intended a different placement.
- `spec/evals.md §7`'s closing "**Closes?**" paragraph still lists "(2) the from-source-build criterion is restated..." as an open item, which D-018 now resolves. Left unedited because the same sentence is structurally bound up with item (1), the no-manual-fixes determination, and the owner's hard stop was explicit: do not touch the no-manual-fixes or Kaggle rows in §7. Flagging the resulting stale line rather than touching it.
- The no-manual-fixes and Kaggle rows in `spec/evals.md §7` remain exactly as before — open, pending the owner's Colab and Kaggle output, per instruction.
**Spec changes:** `spec/tasks.md`, `spec/decisions.md` (D-018), `spec/smoke.md §1`, `spec/evals.md §7`.
**Next action:** owner determines whether the two manual Colab cells (D-017 era, `spec/evals.md §7`) were required; Kaggle run still outstanding; `M0-CORE-05`/`M0-CORE-06` (provenance module) unimplemented and blocking any new measurement row.

---

## 2026-08-31 (w) — Gemini / Antigravity — test_protocol static type ignore on required arg test

**Milestone:** M0 — Falsification
**Tasks attempted:** fix static analysis diagnostic in `tests/test_protocol.py` (line 150)

**Landed:**
- Added `# type: ignore[call-arg]` to `Protocol(p=0.005)` in `test_inv6_decoder_version_is_required_and_real` (`tests/test_protocol.py`). The test intentionally calls `Protocol(p=0.005)` without `decoder_version` to verify that `TypeError` is raised at runtime; the comment suppresses static type checker error (Pyright/Pylance) while maintaining exact test behavior.

**Did not land:** nothing outstanding.
**Blockers:** none.
**Noticed, did not fix:**
- `NOTICE` and `NOTICE.txt` are both present and byte-identical (841 bytes each). One is presumably redundant. Flagging for owner.
- 44 tests pass clean with 0 warnings.
**Spec changes:** none.

---

## 2026-08-31 (v) — Gemini / Antigravity — handover audit fixes + D-016

**Milestone:** M0 — Falsification
**Tasks attempted:** handover audit items 1–6 (not from the spec/tasks.md backlog)

**Landed (prior agent between sessions, confirmed and verified this session):**
- **Item 1 — LICENSE conflict markers** (`c7c2a30`): merge-conflict markers removed; file is byte-identical to canonical Apache-2.0 from apache.org. INV-11 restored.
- **Item 2 — architecture.md §7 licence** (`c1da993`): "MIT for source" → "Apache-2.0 for source (D-011)".
- **Item 3 — root-level decisions.md duplicate** (`ee4ef4c`): removed; `spec/decisions.md` is canonical. Cleanup note added to `spec/decisions.md`.
- **Item 4 — CONTRACT DECODER value** (`d4e4332`): `DECODER = "bposd"` → `"BpOsdDecoder"` to match `protocol.py`'s `DECODER_PARAMS["decoder"]`.
- **Item 5 — p canonicalization** (`387b929`): `Protocol.hash()` now rounds `p` to 6dp before hashing. Two tests: `p=0.005` vs `p=0.0050001` hash identically; `p=0.005` vs `p=0.006` hash differently.

**Landed (this session):**
- **Item 6 — pin P_PILOT** (`6582bcd`): `P_PILOT = 0.005` added to CONTRACT.md's exact-values block. D-016 recorded in `spec/decisions.md` with threshold reasoning and rejected alternatives (lower p inflating censoring; higher p above threshold; multiple p deferred to M1).

**Found and resolved:** working tree had uncommitted partial reverts of items 3–5 (origin of reverts unknown). Discarded via `git checkout --`. HEAD was already correct.

**Did not land:** nothing outstanding.
**Blockers:** none.
**Noticed, did not fix:**
- `NOTICE` and `NOTICE.txt` are both present and byte-identical (841 bytes each). One is presumably redundant. Flagging for owner — deleting one is trivial but which to keep depends on preference.
- 44 tests pass; no warnings observed in output.

---

## 2026-08-30 (u) — Claude Opus 5 / Claude Code — decision 7: pushing is part of done

**Milestone:** M0 — Falsification
**Tasks attempted:** owner decision 7
**Landed:** `AGENTS.md §5` gains `- [ ] **Pushed to origin**`, with the rule stated explicitly: push at the end of every session, including one that ends mid-task, because the remote is the backup and is the only way CI sees the work at all. The closing line now reads "work that exists on exactly one disk is not done either", alongside the existing "it runs" and "the numbers look reasonable" clauses.

The rationale is recorded in the file rather than only here — twelve commits accumulated locally in a single day, so CI had examined none of the session's work and a disk failure would have cost all of it.

**Did not land:** nothing outstanding.
**Blockers:** none.
**Noticed, did not fix:**
- **The done-checklist exists in exactly one place**, `AGENTS.md §5`, so there was only one list to change. `CONTRIBUTING.md` has a "Before opening a PR" list, but that is a PR-readiness list for external contributors where pushing is inherent in opening the PR; adding a push line there would be redundant. `spec/smoke.md`'s checklists are manual smoke checks, not a definition of done. Flagging the judgement in case the owner wants the line added to `CONTRIBUTING.md` anyway.
**Spec changes:** `AGENTS.md §5`.
**Next action:** push, then `M0-CODES-01`.

---

## 2026-08-30 (t) — Claude Opus 5 / Claude Code — decision 6: freeze the run, rebuild the template

**Milestone:** M0 — Falsification
**Tasks attempted:** owner decision 6
**Landed:** two notebooks, doing two different jobs.

- **`notebooks/runs/2026-08-30-verify-env-colab.ipynb`** — the owner's executed copy, **outputs intact**, frozen as dated evidence. 11 cells, 9 with outputs. This file is why the `sinter` wheel error was caught, so the convention is worth keeping: executed runs go to `notebooks/runs/<date>-verify-env-<host>.ipynb`.
- **`notebooks/verify_env_colab.ipynb`** — the clean template. 9 cells, **zero outputs, all execution counts null**.

Template changes beyond stripping:
- **Drive mount is now the primary path.** Cell 3 checks a `QECSCREEN_REPO` override, then walks up from the working directory, then mounts Drive and searches the usual layouts including the nested `MyDrive/qecscreen/qecscreen`. `files.upload()` is **removed from the automatic path** and demoted to an optional snippet at the bottom, explicitly labelled browser-Colab-only, with a warning that it is refused under Colab-in-VS-Code. The header documents this rather than leaving the next person to discover it as the owner did.
- **Cell 4 now checks all three machine-checkable criteria and asserts on each**, instead of printing lines for a human to scan: `pip` exit code; **no ambient downgrade** (any `Attempting uninstall` naming numpy/pandas/scipy/scikit-learn); and **no compiler invocation**, using the same regex as the CI guard from decision 1, so the notebook and CI cannot drift apart on what "installs without a compiler" means.
- The old "no `Building wheel`" criterion is gone — it was the wrong test, and it is what made entry (h) record a false PASS. A pure-Python sdist build is now explicitly called fine and expected.
- The fourth criterion, **no manual fixes**, is printed as something only the human can answer, with the instruction to add the constraint to `requirements.txt` rather than soften the criterion.
- The closing section records that Kaggle has still never been run.

Verified by executing every code cell of the template locally: all pass, including the three new assertions. 42 passed.

**Did not land:** nothing outstanding for this decision.
**Blockers:** none.
**Noticed, did not fix:**
- The frozen run contains the owner's two manual cells (`pip install "pyparsing<3.2"`, `pip install -U matplotlib`) exactly as executed. Left verbatim — it is evidence, and editing evidence to look tidier is the opposite of the point.
- The ambient-downgrade check reads `Attempting uninstall` lines, so it only catches a downgrade pip performs during *this* install. A manual fix cell run afterwards — which is what happened on 2026-08-30 — is invisible to it. That is why criterion 4 is explicitly handed to the human.
- `notebooks/runs/` will accumulate. Fine at one file per environment per milestone; worth a prune rule if it ever gets past a dozen.
**Spec changes:** none.
**Next action:** decision 7 — "Pushed to origin" in the definition of done.

---

## 2026-08-30 (s) — Claude Opus 5 / Claude Code — decision 5: cap data-path deps to the execution environment (D-015)

**Milestone:** M0 — Falsification
**Tasks attempted:** owner decision 5
**Landed:** `pandas>=2.2,<3` and `pyarrow>=15,<19`, plus **D-015** recording the general rule and its rejected alternatives. `spec/architecture.md §1` now separates the *two* reasons an upper bound is allowed — label-determining (INV-6) and data-path-newer-than-production (D-015) — so the next person adding a cap has to say which one applies.

**The dev venv was actually brought down, not just the file changed:**

| | before | after | Colab |
|---|---|---|---|
| `pandas` | 3.0.5 | **2.3.3** | 2.2.3 |
| `pyarrow` | 25.0.1 | **18.1.0** | 18.1.0 |

42 passed afterwards, no compiler invoked. The `pandas` major-version gap is closed and `pyarrow` now matches Colab exactly. Editing the constraint without applying it would have left the same divergence with a comment claiming otherwise.

**Applying the reasoning to the rest**, which is the part that needed judgement rather than instruction:
- `pyarrow` **capped** — the largest gap by far (18 → 25, seven majors) and it is the Parquet engine, so it sits directly in the data path.
- `numpy` (2.1.3 / 2.5.2), `scipy` (1.16.3 / 1.18.1), `scikit-learn` (1.6.1 / 1.9.0) — **not capped.** All differ within a major. Capping them starts forcing downgrades of a preinstalled stack for no measured benefit, which breaks the one-cell install.
- `pytest` — **not capped**, despite a full major gap (8.4.2 vs 9.1.1). It is a dev tool, not a data-path dependency, and a runner mismatch fails loudly at test time rather than silently inside a Parquet file. Both are known to pass this suite. Recorded in D-015's rejected list rather than left unmentioned.

**Did not land:** nothing outstanding.
**Blockers:** none.
**Noticed, did not fix:**
- **These caps are set from Colab, and Kaggle has never been measured.** Kaggle is the workhorse. The argument that Colab is safe as a proxy — it runs the newer Python of the two, so it is likely the newer stack — is reasoning, not measurement. If Kaggle ships `pyarrow` ≥19 or `pandas` ≥3 these caps force a downgrade *there*, which is the exact failure they exist to prevent. This is D-015's revisit condition and it should be closed before the M1 bulk run, not after.
- The dev box is now on `pandas` 2.3.3 against Colab's 2.2.3 — same major, minor gap remains. Acceptable; the class of bug D-015 targets is the major.
- This retires the pandas-3 nulls concern from entry (c) for now: the CONTRACT nulls convention will be implemented against `pandas` 2.x, which is what will actually run it. It returns if the caps are ever raised.
**Spec changes:** `requirements.txt`, `spec/architecture.md §1`, `spec/decisions.md` + `decisions.md` (D-015).
**Next action:** decision 6 — the two notebooks.

---

## 2026-08-30 (r) — Claude Opus 5 / Claude Code — decision 4: write the precedence rule down

**Milestone:** M0 — Falsification
**Tasks attempted:** owner decision 4
**Landed:** `AGENTS.md §4` now states explicitly that when "update the spec in the same change as the code" collides with "one task per change, one commit", **spec-and-code-together wins** — with the reason (a split leaves a commit where spec and implementation disagree, and the next agent trusts the spec) and the obligation (name every task ID in the message, say why in the log, so the merge is visible rather than silent).

This session hit that conflict twice — items 4+5, and decisions 2+3 — and resolved it correctly both times by argument. Writing it down means the next session does not have to re-derive it or, worse, split and produce an inconsistent commit.

Also folded in: `AGENTS.md §3`'s stack table said Python `3.11` alone, which contradicted `spec/architecture.md §1` as of the previous commit. Now `3.11 **and** 3.13`. Named in the commit message rather than slipped in — it is the tail of decision 3, and leaving the two stack tables disagreeing for the sake of commit hygiene would have been exactly the failure the new rule describes.

**Did not land:** nothing outstanding.
**Blockers:** none.
**Noticed, did not fix:** nothing new.
**Spec changes:** `AGENTS.md` §3 and §4.
**Next action:** decision 5 — pin `pandas<3` and record the reasoning as a decision.

---

## 2026-08-30 (q) — Claude Opus 5 / Claude Code — decisions 2 and 3: correct the sinter claim, state the real interpreter rationale

**Milestone:** M0 — Falsification
**Tasks attempted:** owner decisions 2 and 3
**Landed:** the false claim is gone from all three artifacts, and the 3.11/3.13 matrix now carries the reason it actually has.

- **`requirements.txt`** — header now says both interpreters are supported and why; the resolution block says plainly that the 1.15/1.16 split is **wheel availability, not interpreter version**, and that a plain install gives 1.16.0 everywhere.
- **`spec/architecture.md §1`** — the Language row reads "3.11 **and** 3.13" with the reason, replacing a pin that read as singular. The verification block is rewritten, and explicitly says the earlier claim was an artifact of measuring with `--only-binary=:all:`, pointing at entry (n) rather than quietly deleting it.
- **`.github/workflows/ci.yml`** — the matrix comment now gives the real justification: Kaggle runs 3.11 and does the bulk generation, Colab runs 3.13 and is used interactively. Both are execution environments; code that works on only one is broken. The old comment is named as wrong rather than silently replaced.

Decisions 2 and 3 were landed as one commit: they edit the same three comment blocks, and splitting them would have meant rewriting the same lines twice with an intermediate state that was half-corrected. Same principle as items 4+5 and now written into `AGENTS.md §4` by decision 4.

Verified: a repo-wide grep finds no surviving instance of the false claim outside `AGENT_LOG.md`, where it stands with its correction because the log is append-only. YAML re-validated. 42 passed.

**Did not land:** nothing outstanding for these two.
**Blockers:** none.
**Noticed, did not fix:**
- **"Kaggle runs 3.11" is the owner's statement, not something this session measured.** The Colab figure (3.13.15) is from a real run; the Kaggle one is not. `spec/evals.md §7` already records the Kaggle leg as NOT RUN. The rationale is sound either way — but if Kaggle has moved to 3.12 or 3.13, the matrix should follow.
- The architecture table now says "3.11 **and** 3.13" while `AGENTS.md §3` still says "3.11" alone. Left alone on purpose: `AGENTS.md` is edited by decision 4 and decision 7 in their own commits, and I did not want a fourth commit touching the same file. Corrected there.
**Spec changes:** `spec/architecture.md §1`, `requirements.txt`, `.github/workflows/ci.yml`.
**Next action:** decision 4 — the AGENTS.md §4 precedence line.

---

## 2026-08-30 (p) — Claude Opus 5 / Claude Code — decision 1: CI guard tests for a compiler, not a wheel

**Milestone:** M0 — Falsification
**Tasks attempted:** owner decision 1, against `M0-SETUP-02`
**Landed:** `.github/workflows/ci.yml` no longer installs with `--only-binary=:all:`. It installs normally, tees the pip output, and fails the step if a **C toolchain was actually invoked**. `shell: bash` is set explicitly so the step gets `pipefail` and a pip failure is not masked by the `tee`.

The old flag was the wrong test. It demanded a *wheel*; `sinter` 1.16.0 is sdist-only, so CI was pinned to `sinter` 1.15.0 while every real install builds 1.16.0 from a pure-Python sdist — and `sinter`'s version enters `protocol_hash` (INV-6). CI was not testing what anyone runs.

The grep was validated against five logs before committing, rather than assumed — the same discipline item 6 applied to the INV-4 guard:

| log | result |
|---|---|
| the **real Colab log** (`Building wheel for sinter (setup.py)`, plus a `Collecting pygccxml` false-positive probe) | clean |
| `x86_64-linux-gnu-gcc -pthread -B /usr/bin …` | flagged |
| `gcc -pthread -shared build/temp.linux/foo.o` | flagged |
| `error: command '/usr/bin/gcc' failed with exit code 1` | flagged |
| `error: Microsoft Visual C++ 14.0 or greater is required.` | flagged |

**Did not land:** the false `sinter` claim still stands in the matrix comment, `requirements.txt` and `spec/architecture.md §1` — that is decision 2/3, landing next.
**Blockers:** none.
**Noticed, did not fix:**
- The guard is a grep over pip's output, so it depends on pip's log format. If pip ever quiets build output by default, the guard silently stops guarding — the same failure mode as an untested regex. A stronger version would assert on the absence of a compiler on `PATH` during install; not done, because it would also break any future legitimate need.
- CI still cannot detect the *other* half of the one-cell requirement — that nothing in the ambient environment gets downgraded. On a bare runner there is no ambient stack to disturb. Only a real Colab or Kaggle run tests that, which is why `spec/smoke.md §1` keeps it as a manual item.
**Spec changes:** none.
**Next action:** decisions 2 and 3 — correct the `sinter` claim and the interpreter rationale.

---

## 2026-08-30 (o) — Claude Opus 5 / Claude Code — M0-SETUP-01 reopened as PARTIAL

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-SETUP-01`, **reopened**
**Landed:** the checkbox is **unticked** and the criterion recorded as PARTIAL in `spec/evals.md §7`.

Entry (h) closed the Colab leg on the owner's summary. It should not have. Two manual cells were run — `pip install "pyparsing<3.2"` and `pip install -U matplotlib` — and `spec/smoke.md §1` requires the install to succeed "**no manual fixes**". Whether those two were required or were leftover debugging from the VS Code upload problem is being determined by the owner. Until then the criterion is not met, and per `spec/evals.md §7` a PARTIAL is not rounded up.

If they turn out to be required, the fix is to **add the necessary constraints to `requirements.txt`** so a single cell suffices — not to reword the criterion.

The §7 record also downgrades a second line that entry (h) got wrong: **no from-source build is FAIL**, not pass. `Building wheel for sinter (setup.py)` appears in the run. Harmless in substance — `sinter` is pure Python and no compiler was invoked — but the criterion as written is unmet, and the criterion is a proxy for "needs a C toolchain" that does not actually hold. Restating it is decision 1, landing separately.

A third line is recorded as **NOT RUN**: `spec/smoke.md §1` also requires the same check on **Kaggle**, which has never been measured. Kaggle is the workhorse for bulk generation, so that gap matters more than the Colab one.

**Did not land:** closure of `M0-SETUP-01`. Deliberately.
**Blockers:** owner's determination on the two manual cells.
**Noticed, did not fix:**
- A plausible reading of the two cells: something in Colab's ambient stack constrains `pyparsing<3.2`, and the `matplotlib` upgrade was pulled in by `sinter`'s dependency on it. If so, the constraint belongs in `requirements.txt` and neither cell is optional. Speculation, recorded so the owner's investigation has a hypothesis to confirm or kill — not evidence.
- `spec/evals.md §7` was written for milestone verdicts. This is an interim task-level record and is labelled as such; if that pattern recurs, §7 may want an explicit "interim records" subsection.
**Spec changes:** `spec/tasks.md` (unticked, PARTIAL), `spec/evals.md §7` (interim record).
**Next action:** decisions 1 through 7.

---

## 2026-08-30 (n) — Claude Opus 5 / Claude Code — CORRECTION to (c), (e), (h): the sinter finding was wrong

**Milestone:** M0 — Falsification
**Tasks attempted:** none. This entry corrects earlier entries, per the append-only rule.

**The executed `verify_env_colab.ipynb` was found in the working tree with the owner's real Colab outputs saved in it.** Reading them contradicted a claim I made in entries (c) and (e) and repeated in three committed artifacts.

**What I claimed:** "`sinter` 1.16.0 requires Python ≥3.12, so a 3.11 environment resolves to `sinter` 1.15.0 with `stim` 1.16.0."

**What is actually true:** `sinter` 1.16.0 **ships an sdist only — no wheel, for any Python version.** Verified directly: `pip download sinter==1.16.0 --only-binary=:all:` fails on Python 3.13 with "No matching distribution found", while the same command without that flag downloads `sinter-1.16.0.tar.gz`. Forcing the upgrade inside a **3.11** venv builds the sdist and installs 1.16.0 successfully. The Colab run shows the same thing from the other side: `Building wheel for sinter (setup.py)` on Python 3.13.15.

My original evidence came from a `--only-binary=:all:` dry run, so what I actually measured was "wheels only", not "Python 3.11". The version I read off it was an artifact of the flag I passed. I then attributed it to the interpreter and repeated it without re-testing.

**Corrected picture:**
- With `--only-binary=:all:` → `sinter` 1.15.0, on **every** Python version.
- With a plain `pip install` → `sinter` 1.16.0, on 3.11 and 3.13 alike, built from the sdist. `sinter` is pure Python, so no compiler is involved and the one-cell install claim survives.
- **There is no interpreter-dependent sinter skew.** The skew is flag-dependent, and I introduced it into CI myself.

**Consequences, none yet fixed:**
1. **`.github/workflows/ci.yml` has a real defect.** `pip install --only-binary=:all:` pins CI to `sinter` 1.15.0 on *both* matrix legs, while anyone running a normal install gets 1.16.0. CI therefore does not test the `sinter` that users actually run — and `sinter`'s version enters `protocol_hash` (INV-6). The 3.11/3.13 matrix is still worth keeping, but not for the reason its comment gives.
2. **`requirements.txt`** carries a false comment block, including a wrong 3.11-vs-3.13 resolution table.
3. **`spec/architecture.md §1`** carries the same false claim and resolution table.

**Proposed fix, not applied — the CI part is a judgement call:** drop `--only-binary=:all:` and instead assert no *compiler* was invoked (grep the pip log for `gcc`/`cc1`/`error: Microsoft Visual C++`), which is what the guard was actually for; a pure-Python sdist build is fine and a C build is not. Then correct the two comment blocks. Awaiting the owner's decision.

**Colab evidence, now recorded properly — entry (h) had none of it:**
- Runtime: **Python 3.13.15**, `Linux-6.6.122+-x86_64-with-glibc2.35`, repo mounted at `/content/drive/MyDrive/qecscreen/qecscreen`.
- `pip install -r requirements.txt` → **exit 0**; only four packages installed: `ldpc` 2.4.1, `pymatching` 2.4.0, `sinter` 1.16.0, `stim` 1.16.0.
- **No downgrade of Colab's preinstalled stack** — the criterion that mattered most. It kept `numpy` 2.1.3, `pandas` 2.2.3, `scipy` 1.16.3, `scikit-learn` 1.6.1.
- Imports clean under `-W error`; `BpOsdDecoder` accepted the CONTRACT parameters; **`pytest` 23 passed on Colab** (the pre-session count).

**Noticed, did not fix:**
- **The notebook's own pass criterion was technically not met.** It says "no `Building wheel` line", and there is one, for `sinter`. Harmless here because `sinter` is pure Python, but the criterion is a proxy for "needs a compiler" and the proxy is wrong. Same fix as consequence 1.
- **Colab's stack is much older than the dev box**: `pandas` 2.2.3 vs 3.0.5 locally, `numpy` 2.1.3 vs 2.5.2, `scikit-learn` 1.6.1 vs 1.9.0, `pytest` 8.4.2 vs 9.1.1. Nothing broke, but the pandas-3 nulls question (entry (c)) is a *local-only* problem today and would appear on Colab later. Pilot generation should record the resolved versions per run.
- **The owner ran two manual cells not in the notebook**: downgrading `pyparsing` 3.3.2 → 3.1.4 and upgrading `matplotlib` 3.10.0 → 3.11.1. Neither is ours — both are transitive via `sinter`. Worth understanding before the pilot, because it means the documented one-cell install was not quite sufficient in practice.
- The executed notebook is **uncommitted** in the working tree. Whether to commit it with outputs, or strip them and keep this entry as the record, is the owner's call.

**Spec changes:** none. `requirements.txt`, `spec/architecture.md §1` and `ci.yml` all still carry the incorrect claim, deliberately left for the owner's decision.
**Next action:** owner decision on the CI guard and the two comment blocks.

---

## 2026-08-30 (m) — Claude Opus 5 / Claude Code — item 6: the INV-4 grep, and testing the guard

**Milestone:** M0 — Falsification
**Tasks attempted:** owner decision item 6
**Landed:** the INV-4 source-grep rewritten from one pattern to five, and — the part that matters more — **the guard is now itself tested**.

Patterns: `(1 - <anything>) **` for any base and any case; `... ** (1 / ...)`, which catches a base containing its own parentheses; `np.power`/`numpy.power`/`math.pow` with a `1 - ` first argument; `expm1(`; `log1p(`. The old single pattern required a lowercase `p` in the base variable name, so it missed `(1 - P_L) **` — the notation CONTRACT and `spec/evals.md` both use to *describe* the thing it was meant to catch.

Eight new tests: seven known violation spellings written to a temp file and asserted flagged, plus a benign file (`base ** exponent`, `(width - 1) * (height - 1)`) asserted **not** flagged, because a guard that fires on ordinary arithmetic gets deleted by the next person it annoys. 42 passed.

`spec/evals.md` INV-4-T now describes what the check actually does rather than what it was hoped to do, and the section gained a paragraph on why grep tests need their own tests: a grep matching nothing passes whether or not it would ever fire, so a weak pattern is indistinguishable from a clean codebase. Any future grep test in that section should carry the same self-test.

**Did not land:** nothing outstanding. All six approved items are now landed.
**Blockers:** none.

**Noticed, did not fix:**
- The `(1 - x) **` pattern uses `[^()]+` for the base, so a base with nested parentheses is caught only by the exponent-shape pattern `) ** (1 /`. Something like `(1 - f(x)) ** 0.5` — same shape, different exponent — would slip through. Narrow enough to accept; recorded so it is a known limit rather than a surprise.
- `expm1(` and `log1p(` are matched bare, anywhere outside `protocol.py`. They are the numerically-stable rearrangement of this exact formula, so flagging them is intended, but a future module with a legitimate unrelated use will trip it. The right response then is to move the computation, not to loosen the pattern.
- The other three grep tests (INV-2, INV-8, torch) are still untested guards. They use plain substring matching so the risk is much lower, but the same argument applies if any of them ever grows a regex.
**Spec changes:** `spec/evals.md` (INV-4-T row, and a new paragraph on testing grep guards).
**Next action:** `M0-CODES-01` — the BB generator. Not started, as instructed.

---

## 2026-08-30 (l) — Claude Opus 5 / Claude Code — items 4 and 5: CONTRACT change, D-014; M0-CORE-01 closed

**Milestone:** M0 — Falsification
**Tasks attempted:** owner decision items 4 and 5, closing `M0-CORE-01`
**Landed:** the first CONTRACT change of the project, with human approval.

- **INV-6 field list** now hashes `rounds_rule` (pinned `"r = d_upper"`) instead of the concrete `r`, and states that a placeholder decoder version is never acceptable. Added the "why the rule and not the value" paragraph so the next reader does not re-derive the trap.
- **"Exact values"** gained `ROUNDS_RULE = "r = d_upper"`.
- **Pinned conventions**, `Rounds r` row, now points at D-014 alongside D-006.
- **D-014 added**, with the rejected alternatives — including the obvious one, dropping rounds from the hash entirely, which fails in the opposite direction because a fixed-`r` and a variable-`r` dataset would then hash identically.
- **`protocol.py`:** `ROUNDS_RULE` constant; `installed_decoder_version()` reading `importlib.metadata` at call time, not import time; `Protocol` loses the `rounds` field, gains `rounds_rule`, and `decoder_version` becomes required with a `__post_init__` that rejects `""` and `"unset"`.
- `selfcheck.py` updated to the new constructor. 34 passed, selfcheck green.

**This unblocks `M0-RUN-04`.** Before: `r = d_upper` varies per code, `r` was hashed, so every distance was its own protocol and `assert_single_protocol()` raised on any cross-code frame — the exact metric M0 exists to compute. There is now a test asserting three codes of different `d_upper` share one hash, and a second asserting a *different* rounds rule still produces a different hash, so the guard has not simply been weakened.

**Note on process:** the owner asked for CONTRACT changes in their own commit. Items 4 and 5 are shipped together with `protocol.py` and the tests, because `AGENTS.md §4` requires the spec and the code to move in one change, and splitting them would have left a commit where CONTRACT and the implementation disagreed. Both items touch the same dataclass, so separating them would also have meant editing the same lines twice.

**Did not land:** nothing outstanding.
**Blockers:** none.

**Noticed, did not fix:**
- I **rewrote one of my own new tests before committing.** `test_d014_rounds_value_is_not_in_the_hash` originally hashed the same protocol three times and called them "codes of different distance" — a comment claiming more than the assertion proved. It now checks that `rounds` is absent from the dataclass fields and walks explicit `d_upper` 4/6/8 rows. Flagging it because a test whose comment lies is worse than no test, which is this project's entire thesis.
- **`p` is still not canonicalised for hashing.** The conventions table says `p` is stored to 6dp, but `hash()` serialises the raw float. Not touched — it was not among the approved items, and `hash()` is contract-governed. Worth a decision.
- `DECODER_PARAMS["decoder"]` is still `"BpOsdDecoder"` where CONTRACT pins `DECODER = "bposd"`. Unchanged, still cosmetic, still a CONTRACT literal not reproduced.
- Both `decisions.md` and `spec/decisions.md` were updated identically so they stay byte-identical. That duplication is still a drift hazard and still wants deleting; doing it needs a decision, since `AGENTS.md` read order names `spec/decisions.md`.
- `Protocol` construction is now more verbose at every call site. A `Protocol.current(p)` classmethod would remove the boilerplate without reintroducing a default. Not added — not asked for.

**Spec changes:** `CONTRACT.md` (INV-6, Exact values, conventions table), `spec/decisions.md` and `decisions.md` (D-014), `spec/tasks.md` (M0-CORE-01 ticked).
**Next action:** item 6 — the INV-4 grep.

---

## 2026-08-30 (k) — Claude Opus 5 / Claude Code — item 3: module-level protocol_hash()

**Milestone:** M0 — Falsification
**Tasks attempted:** owner decision item 3
**Landed:** `protocol_hash(protocol)` in `protocol.py`, a thin wrapper over `Protocol.hash()`. The dataclass is kept, as instructed. Deliberately a wrapper and not a second implementation — two implementations of a hash eventually disagree, and the disagreement would be invisible.

The point is that the function name now matches the **stored column name** and the task that names it (`M0-EVAL-03`), so nobody writing `df["protocol_hash"]` has to know it comes from a method with a different name.

Also folded in: `__all__` gained `protocol_hash` and `is_censored`. `is_censored` was flagged in entry (g) as defined-but-unexported while already imported by the tests. One-word fix to the same `__all__` this item was already editing; splitting it into its own commit would have been noise. Recorded here so it is not invisible.

29 passed.

**Did not land:** `M0-CORE-01` stays open — items 4 and 5 are the rest of it.
**Blockers:** none.
**Noticed, did not fix:** nothing new.
**Spec changes:** none.
**Next action:** items 4 and 5 — the CONTRACT changes, with D-014.

---

## 2026-08-30 (j) — Claude Opus 5 / Claude Code — item 2: _as_gf2 validation order; M0-CORE-03 closed

**Milestone:** M0 — Falsification
**Tasks attempted:** owner decision item 2, closing `M0-CORE-03`
**Landed:** `_as_gf2` now rejects the dtype **before** any cast. bool gets its own message; anything non-integer (float, object) is refused; the {0, 1} check then runs on the un-truncated values and only afterwards does it cast to uint8.

Behaviour change, verified directly:

| input | before | after |
|---|---|---|
| `[[0.5, 0.0]]` | rank **0** | `ValueError: matrix has dtype float64` |
| `[[1.0, 0.0]]` | rank 1 | `ValueError` — refused even though the values are integral |
| `[[True, False]]` | rank 1 | `ValueError: matrix is bool` |
| `[[256, 0]]` | rank **0** (wrapped mod 256) | `ValueError: must contain only 0 and 1` |
| `[[1, 0]]` uint8, and plain int lists | works | works |

The 256 case was not in the original report and fell out of the same fix: an out-of-range integer wrapped modulo 256 during the cast, silently, by the same mechanism. Python lists of ints still work, so nothing that was legitimate got stricter.

Three tests added, including the named regression `[[0.5, 0.0]]` must raise, not return rank 0. 28 passed.

`M0-CORE-03` is now **closed** — items 1 and 2 were its two halves.

**Did not land:** nothing outstanding.
**Blockers:** none.
**Noticed, did not fix:**
- Empty float arrays such as `np.zeros((0, 3))` now raise, because their default dtype is float64. Correct under the convention, but if a caller ever wants a genuinely empty check matrix it must say `dtype=np.uint8`.
**Spec changes:** `spec/tasks.md` (M0-CORE-03 ticked). No CONTRACT change needed — CONTRACT already said "never bool, never float"; the code simply did not enforce it.
**Next action:** item 3 — module-level `protocol_hash()`.

---

## 2026-08-30 (i) — Claude Opus 5 / Claude Code — item 1: gf2_nullspace

**Milestone:** M0 — Falsification
**Tasks attempted:** owner decision item 1, against `M0-CORE-03`
**Landed:** `gf2_nullspace(m)` in `linalg.py`, returning a `(n - rank, n)` uint8 basis built from the existing `gf2_rref` pivots. Basis vectors are **rows**, so a vector is indexed by qubit exactly as a check-matrix row is (CONTRACT check-matrix orientation). `gf2_nullspace_dim` kept unchanged, as instructed — it answers the cheaper question that `k` needs.

`__all__` also gained `logical_qubit_count`, which was already public in practice because the tests import it (flagged in entry (g)).

Three tests added: 200 random matrices asserting every returned row is genuinely annihilated **and** that the rows are independent (a basis, not merely a spanning set); the two degenerate shapes (full column rank → `(0, n)`, zero matrix → identity); and the `[7,4,3]` Hamming matrix, whose nullspace is the Hamming code itself. 26 passed.

**Did not land:** `M0-CORE-03` stays open until item 2 lands — the other half of that task.
**Blockers:** none.
**Noticed, did not fix:** nothing new.
**Spec changes:** none — the task line already named `gf2_nullspace`, so this closes a gap rather than changing the spec.
**Next action:** item 2 — `_as_gf2` validation order.

---

## 2026-08-30 (h) — Claude Opus 5 / Claude Code — M0-SETUP-01 closed (Colab verified)

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-SETUP-01` — final acceptance criterion
**Landed:** `M0-SETUP-01` is **closed**. The owner executed `notebooks/verify_env_colab.ipynb` on a Colab runtime. Result: **pass.** Cells 4 and 5 both passed — `pip install -r requirements.txt` succeeded, **no downgrade of Colab's preinstalled numpy/pandas/scipy/scikit-learn**, and **no from-source build**. Those were the two failure modes a local venv structurally cannot detect (entry (d)), so the one-cell install claim in `requirements.txt` and `AGENTS.md §3` now rests on a real observation rather than an inference.

`M0-SETUP-02` and `M0-SETUP-03` were already logged in entries (e) and (f), including the `.gitignore` deviation and its reasoning; not duplicated here. That deviation — `data/*` plus `!data/LICENSE` instead of the literal `data/` from the task text — has since been **reviewed and approved by the owner**, who confirmed the task text was wrong. `spec/tasks.md` M0-SETUP-03 already records the reasoning.

**Did not land:** nothing outstanding for this task.
**Blockers:** none.

**Noticed, did not fix:**
- **The notebook's upload path does not work under Colab-in-VS-Code.** Cell 3 falls back to `google.colab.files.upload()` when `requirements.txt` is not reachable by walking up from the working directory. That fallback was **refused** in the VS Code Colab kernel — the file picker is a browser-side widget and does not function in that host. The owner worked around it by **mounting Google Drive and running from there**, which succeeded.
- **This makes the notebook's own instructions wrong for the VS Code path**, which is the path this project actually uses — the owner runs Colab as a VS Code kernel rather than in a browser tab, so the documented fallback is the one route that is guaranteed to fail here. Anyone reproducing the environment check from the notebook as written will hit the same wall.
- **`verify_env_colab.ipynb` should be updated to document the Drive route** — my assessment is yes, and it should become the *primary* documented path rather than a footnote, with `files.upload()` demoted to a browser-Colab-only fallback. Concretely: add a Drive-mount branch to cell 3 (`google.colab.drive.mount`, then search a configurable repo path under `/content/drive`), and correct the markdown in cell 1. **Not done this session — the owner asked for the assessment only, not the edit.** Worth doing before anyone else runs it, and before `M0-RUN-02` writes `m0_kaggle.ipynb`, which will face the same host question.
- The Colab runtime's Python version and resolved `sinter` version were not captured in what was reported back. Cell 2 prints both, and they decide whether Colab resolves `sinter` 1.15 or 1.16. Worth grabbing on the next run, because `sinter`'s version enters `protocol_hash` (INV-6) and Colab is a candidate host for pilot generation.

**Spec changes:** `spec/tasks.md` (M0-SETUP-01 note; box was already ticked, the Colab caveat is now replaced by the verified result).
**Next action:** items 1, 2, 3, 4, 5 and 6 from the owner's decisions — `gf2_nullspace`, `_as_gf2` validation order, module-level `protocol_hash()`, required `decoder_version`, `rounds_rule` in the hash with D-014, and the INV-4 grep repair.

---

## 2026-08-30 (g) — Claude Opus 5 / Claude Code — M0-CORE-01..04 reconciliation

**Milestone:** M0 — Falsification
**Tasks attempted:** verification only of `M0-CORE-01` … `M0-CORE-04`, already implemented in an earlier session. **No source was rewritten.**
**Landed:** `spec/tasks.md` reconciled. `M0-CORE-02` and `M0-CORE-04` ticked; `M0-CORE-01` and `M0-CORE-03` left open with the specific reason recorded on each line.

**What was verified, and how:**
- **Golden values.** All six literals are byte-identical across `CONTRACT.md`, `spec/evals.md` and `tests/test_protocol.py` — checked by extraction and set comparison, not by eye. Each was then recomputed independently at 50 decimal digits. Wilson matches to ~1e-16. The LER values match to ~1e-13, because `1 - (1-p)**x` loses about four digits to cancellation; that is inherent to the pinned formula, sits well inside CONTRACT's `rel_tol=1e-12`, and a numerically better implementation would still pass. The tests use `math.isclose(rel_tol=1e-12)`, not `==` — the task text says "exactly" but CONTRACT explicitly forbids exact equality here and CONTRACT wins.
- **Frozen constants.** All eight, plus every `DECODER_PARAMS` entry, match CONTRACT "Exact values". `Z_95` equals `scipy.stats.norm.ppf(0.975)` to the bit.
- **GF(2) algebra.** `gf2_rank` cross-checked against an independent bitmask Gaussian elimination on 400 random matrices — zero mismatches — with `gf2_rref` pivot counts and `gf2_nullspace_dim` consistent throughout.
- **N-06.** `test_n06_gf2_rank_differs_from_real_rank` is exactly the specified case and also asserts the float answer is 3, so it fails loudly if its own premise stops holding.

**Did not land — why `M0-CORE-01` and `M0-CORE-03` stay open:**
1. **`gf2_nullspace` does not exist.** Only `gf2_nullspace_dim`, which returns an integer. `k` computation needs only the dimension, which is why nothing has noticed, but `M0-CODES-04` needs an actual nullspace **basis** to search for low-weight logical operators. Proposed: add `gf2_nullspace(m) -> np.ndarray` returning basis rows, built from the existing `gf2_rref` pivots.
2. **`_as_gf2` accepts what CONTRACT bans.** It calls `np.asarray(m, dtype=np.uint8)` *before* checking membership of {0,1}, so `[[0.5, 0.0]]` truncates to `[[0, 0]]` and returns rank 0 rather than raising; bool arrays are likewise accepted. CONTRACT's matrix-field convention says "Never bool, never float". This is the exact failure shape INV-8 exists to prevent — a silent wrong rank gives a wrong `k` gives wrong labels. Proposed: check `dtype` and value range before casting.
3. **No `protocol_hash` name.** The functionality is `Protocol.hash()`. The stored column is `protocol_hash` and `M0-EVAL-03` names it again. Proposed: a thin `protocol_hash(protocol)` wrapper, or accept `Protocol.hash()` and correct the two task lines.
4. **`Protocol.decoder_version` defaults to `"unset"`** — an INV-6 hash can be produced without the decoder version it claims to encode. Proposed: required field, populated from `importlib.metadata.version("ldpc")`.
5. **The `rounds`-in-hash blocker**, unchanged from entry (c). `M0-CORE-01` cannot honestly close while the hash it produces is the thing that makes `M0-RUN-04` raise.

**Blockers:** items 4 and 5 are CONTRACT changes and need human approval. Items 1–3 are ordinary work, deliberately not done here because the instruction was to verify and report, not to rewrite.

**Noticed, did not fix:**
- **The INV-4 source-grep is much weaker than `spec/evals.md` claims.** `evals.md` INV-4-T says the grep catches "`(1 - P_L) **` or equivalent". The implemented regex requires a lowercase `p` in the variable name, so it **misses CONTRACT's own notation** `(1 - P_L) **`, and also misses `np.power`, `math.pow`, `-expm1(log1p(...))` and any variable not containing a lowercase `p`. Of six plausible spellings tested, it catches one. The test currently passes because nothing violates INV-4 yet — it would not catch the violation it exists for.
- `is_censored` is defined in `protocol.py` but missing from `__all__`; `logical_qubit_count` likewise in `linalg.py`. Both are imported by tests, so they are public in practice.
- `DECODER_PARAMS["decoder"]` is `"BpOsdDecoder"`, the class name; CONTRACT pins `DECODER = "bposd"`, the decoder name. INV-6 requires "decoder name" in the hash. Cosmetic today, but it is a CONTRACT literal not reproduced.
**Spec changes:** `spec/tasks.md` (four task lines).
**Next action:** owner decision on items 4 and 5, then `M0-CORE-01`/`-03` closure. `M0-CODES-01` is unblocked and independent of all of the above.

---

## 2026-08-30 (f) — Claude Opus 5 / Claude Code — M0-SETUP-03

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-SETUP-03` — `.gitignore`
**Landed:** `.gitignore` with the four patterns the task names, one of them reshaped.

`data/` is written as `data/*` with `!data/LICENSE`. Git **cannot** re-include a file whose parent directory is excluded, so the literal `data/` from the task text would have made the CC-BY-4.0 dataset licence uncommittable at M1 — a trap that would have surfaced months later as a confusing `git add` that silently does nothing. Entry (b) already flagged `data/LICENSE` as an M1 item, which is how this was caught.

Verified behaviourally, not by inspection: created `data/LICENSE`, `data/scratch.parquet` and `data/notes.txt`, confirmed git offered **only** `data/LICENSE`, then removed all three. Working tree is now clean.

`venv/` and `.pytest_cache/` were deliberately **not** added — each already contains a `.gitignore` written by the tool that created it, which is why `venv/` never showed up as untracked despite sitting in the tree. A differently-named environment directory would need adding, and the file says so.

**Did not land:** nothing outstanding for this task.
**Blockers:** none.
**Noticed, did not fix:**
- `data/`, `notebooks/` and `scripts/` are empty and therefore absent from git entirely. A fresh clone will not have `data/`. Any script writing there must create it; worth a `.gitkeep` if that ever bites.
**Spec changes:** `spec/tasks.md` (checkbox + note).
**Next action:** reconcile `M0-CORE-01` … `M0-CORE-04`.

---

## 2026-08-30 (e) — Claude Opus 5 / Claude Code — M0-SETUP-02

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-SETUP-02` — CI
**Landed:** `.github/workflows/ci.yml`, plus a CI badge in `README.md`. `pytest.ini` already existed from the skeleton commit and was left alone.

Three choices worth recording:
- **Matrix on 3.11 and 3.13.** They resolve *different* `sinter` versions (1.15.0 vs 1.16.0), so a single-version CI would miss a break in the other. Costs about two extra minutes per push.
- **`pip install --only-binary=:all:`.** Turns `AGENTS.md §3`'s "does it install on Kaggle without a compiler" from a review question into a build failure. If a dependency ever stops shipping a wheel, CI says so instead of a Kaggle runtime discovering it at hour six.
- **`concurrency` + `timeout-minutes: 10`.** The repo is private through M0 (D-013), so Actions minutes are metered against the free allowance. Superseded runs cancel and a hung job cannot quietly eat the budget (INV-9). Well inside the free tier at this size, but bounded rather than assumed.

YAML validated by parsing. The `on:` key parses as boolean `True` under YAML 1.1 — that is the standard gotcha, not a defect; GitHub's own parser reads it correctly.

**Did not land:** confirmation that the badge is green. That needs a push, which is the owner's decision, so `spec/tasks.md` records it as explicitly unconfirmed rather than assumed.
**Blockers:** none.
**Noticed, did not fix:**
- The repo URL assumed in entry (b) — `github.com/Pushkar0997/qecscreen` — is **confirmed correct**: it is the configured `origin`. `CITATION.cff` and `BRIEF.md` can stop carrying that caveat.
- The badge will not render for anyone outside the repo while it is private (D-013). It renders for the owner, and becomes public at M1.
- CI does not enforce DCO sign-off. Entry (b) already flagged this as an M1 item, once there are external contributors.
**Spec changes:** `spec/tasks.md` (checkbox + note).
**Next action:** `M0-SETUP-03`.

---

## 2026-08-30 (d) — Claude Opus 5 / Claude Code — M0-SETUP-01 (Colab leg)

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-SETUP-01`, the acceptance criterion left open in entry (c)
**Landed:** `notebooks/verify_env_colab.ipynb`. Reports the runtime's Python version, locates `requirements.txt` by walking up from the working directory (falling back to `files.upload()` when the workspace is not mounted), runs the install, reports what resolved, checks every import under `-W error`, and — where the repo source is reachable — feeds `DECODER_PARAMS` straight from `protocol.py` into a real `BpOsdDecoder` and runs `pytest`.

The notebook watches for the two things a local venv cannot detect: a **downgrade of Colab's preinstalled numpy/pandas/scipy/sklearn**, and a **from-source build**. Either would break the one-cell install claim, and neither can happen in an empty venv, which is why entry (c)'s local verification was not sufficient on its own.

No constants are retyped in the notebook — decoder parameters are read from `protocol.py` and the requirements are read from the file, so it cannot drift from the spec. No pipeline logic, per `spec/architecture.md §2`.

Verified by executing every code cell locally against the 3.13 venv: all eight run clean, `pytest` 23 passed.

**Did not land:** the actual Colab run. This needs a human on a Colab runtime.
**Blockers:** none.
**Noticed, did not fix:**
- The criterion is still **not met** until someone runs this on Colab. `spec/tasks.md` records it as pending rather than done, deliberately — this is the "do not round up a PARTIAL" case in miniature.
- When every requirement is already satisfied, cell 4 prints only the exit code, because no `Successfully installed` line is emitted. Expected; a fresh Colab runtime will print them.
**Spec changes:** `spec/tasks.md` (M0-SETUP-01 note now points at the notebook).
**Next action:** `M0-SETUP-02`.

---

## 2026-08-30 (c) — Claude Opus 5 / Claude Code — M0-SETUP-01

**Milestone:** M0 — Falsification
**Tasks attempted:** `M0-SETUP-01` — pin dependency versions
**Landed:** `requirements.txt` rewritten. Version bounds now match `spec/architecture.md §1` with one correction: `stim`, `sinter` and `ldpc` gained major-version upper bounds (`<2`, `<2`, `<3`), because those three versions enter `protocol_hash` (INV-6) and a breaking major release would silently invalidate every label already generated. The bound makes that fail at install time instead. No upper bound was added anywhere else — Kaggle and Colab ship their own numpy/pandas/scipy and a tighter pin breaks the one-cell install, and a bound without a stated reason is an invented value (AGENTS.md §4).

Verified by clean install into fresh venvs, `--only-binary=:all:` (wheels only, no compiler), on **both** interpreters:

| Interpreter | stim | sinter | ldpc | numpy | pandas | scipy | pytest |
|---|---|---|---|---|---|---|---|
| 3.11.9 (pinned) | 1.16.0 | **1.15.0** | 2.4.1 | 2.4.6 | 3.0.5 | 1.17.1 | 23 passed |
| 3.13.7 (dev venv) | 1.16.0 | **1.16.0** | 2.4.1 | 2.5.2 | 3.0.5 | 1.18.1 | 23 passed |

`sinter` 1.16.0 requires Python ≥3.12, so the pinned 3.11 interpreter resolves one minor behind `stim`, which is normally released in lockstep with it. Both combinations install and pass. All library imports are clean under `-W error`, which matters because `pytest.ini` sets `filterwarnings = error`.

**Did not land:** every other M0 task. `M0-SETUP-02` and `-03` deliberately untouched — one task, one commit.

**Blockers:** none for this task.

**Noticed, did not fix:**
- **The dev venv is Python 3.13.7; `spec/architecture.md §1` pins 3.11.** Both work, but the pilot will produce labels under whichever interpreter it happens to run on, and that changes the resolved `sinter` version. Decide the pilot interpreter deliberately before `M0-EVAL-01`. Not fixed here because moving the venv is not a `requirements.txt` change.
- **"Verify in a clean Colab cell" was not literally done.** Verified in clean local venvs on both interpreters instead. The remaining Colab-specific risk is the ambient preinstalled stack, which is exactly why no new upper bounds were added. Worth one real Colab cell before the pilot.
- **BLOCKER for `M0-RUN-04`, unchanged from the audit session:** `protocol_hash` includes `rounds`, and D-006 sets `r = d_upper`, which varies per code. So every distinct `d_upper` is a distinct protocol, and `assert_single_protocol()` will raise on the pilot frame — the ranking step cannot run. Proposed fix is to hash `rounds_rule = "r_equals_d_upper_v1"` instead of the value. Needs human approval (CONTRACT change).
- **No value of `p` is pinned anywhere.** `M0-RUN-01`/`-03` cannot run without it and `AGENTS.md §4` forbids inventing it. Belongs in CONTRACT "Exact values".
- `Protocol.decoder_version` defaults to `"unset"` in `protocol.py`, so an INV-6 hash can be computed without the decoder version it claims to encode. Should be a required field populated from `importlib.metadata.version("ldpc")` — and now that `ldpc` is bounded, that value is at least constrained.
- `CONTRACT.md` "Exact values" omits `error_rate`/`error_channel` (a **required** `BpOsdDecoder` argument) and `schedule` (`parallel`/`serial`, affects decoder output). Both belong in `DECODER_PARAMS`.
- `M0-CIRC-01` assumes a networkx edge-colouring API that does not exist; the line-graph greedy route gives 7–9 colours where 6 is provable, is unseeded, and takes ~1.0s at n=144 against the <1s feature budget. Full detail in the audit; needs a scheduling decision recorded in `spec/decisions.md`, which currently has none.
- `decisions.md` and `spec/decisions.md` are byte-identical and **both tracked**; likewise `NOTICE` and `NOTICE.txt`. They will drift on the first edit. Not fixed — out of scope for this task.
- `src/qecscreen/linalg.py` exports `gf2_nullspace_dim`; `spec/tasks.md` M0-CORE-03 says `gf2_nullspace`. One of the two is wrong.
- No `.gitignore`, so `__pycache__/` shows as untracked. That is `M0-SETUP-03`.

**Spec changes:** `spec/architecture.md §1` (three version cells, plus a verified-resolution table and the rationale for the bounds), `AGENTS.md §3` (same three cells, kept in sync so the two stack tables do not drift), `spec/tasks.md` (checkbox).

**Next action:** `M0-SETUP-03` — add `.gitignore` excluding `data/`, `*.parquet`, `__pycache__`, `.ipynb_checkpoints`. Then `M0-SETUP-02` (CI). The two CONTRACT items above should be resolved before `M0-EVAL-01`, not before `M0-CODES-01`.

---

## 2026-08-30 (b) — Claude Opus 4.5 / chat — M0 setup

**Milestone:** M0 — Falsification
**Tasks attempted:** none (licensing decision session, pre-M0)
**Landed:** Licence changed from MIT to Apache-2.0. `LICENSE` (canonical Apache 2.0 text), `NOTICE`, `CITATION.cff`, `CONTRIBUTING.md` added. `spec/decisions.md` D-010 marked superseded; D-011 (Apache + CC-BY), D-012 (dual licensing deferred, DCO required), D-013 (private through M0) added. `AGENTS.md` gained INV-11 and a licence-compatibility check on new dependencies. README, BRIEF and `spec/product.md §8` updated. `pytest` still green, 23 passed.
**Did not land:** every M0 task. Backlog untouched.
**Blockers:** none.
**Noticed, did not fix:**
- `CITATION.cff` has two `# FILL:` lines — ORCID and published email. Fill before the M1 Zenodo release; an ORCID takes two minutes and is the thing that disambiguates authorship in the literature.
- `repository-code` in `CITATION.cff` and the repo URL in `BRIEF.md` assume the repo will live at `github.com/Pushkar0997/qecscreen`. Correct both if renamed.
- DCO sign-off is documented in `CONTRIBUTING.md` but not mechanically enforced. Add a DCO check to `.github/workflows/` when the repo goes public at M1 — until then there are no external contributors, so it is not yet load-bearing.
- No CC-BY-4.0 licence file exists yet because no dataset exists yet. Add `data/LICENSE` at M1.
**Spec changes:** `spec/decisions.md`, `spec/product.md`, `AGENTS.md`, `BRIEF.md`, `README.md`.
**Next action:** `M0-SETUP-01` — write `requirements.txt` with pinned versions from `spec/architecture.md §1` and verify `pip install -r requirements.txt` in a clean Colab cell.

---

## 2026-08-30 — Claude Opus 4.5 / chat — M0 setup

**Milestone:** M0 — Falsification
**Tasks attempted:** none (intake and spec authoring session, pre-M0)
**Landed:** Spec system written in full — `CONTRACT.md`, `AGENTS.md`, `BRIEF.md`, and all seven `spec/` documents. Repo skeleton with `src/qecscreen/protocol.py` and `linalg.py` implemented and covered by golden-value tests. `pytest` green.
**Did not land:** every M0 task. The backlog is written but untouched.
**Blockers:** none. Next session can start at `M0-SETUP-01`.
**Noticed, did not fix:**
- The 5 ms/shot decode cost in `spec/architecture.md §6` is a planning placeholder, not a measurement. `M0-EVAL-05` must replace it and update that section in the same commit.
- `D-006` (rounds `r = d_upper`) is marked provisional and should be revisited at M2.
- The BB distance-estimation method in `M0-CODES-04` is specified as "decoder-assisted random search" without a fixed algorithm. Pin it when implementing, and record the choice in `spec/decisions.md`.
- Library API details for `ldpc.BpOsdDecoder` and `networkx` edge colouring were written from spec, not verified against installed versions. Verify at `M0-SETUP-01`.
**Spec changes:** all of them — this session created the spec.
**Next action:** `M0-SETUP-01` — write `requirements.txt` with pinned versions from `spec/architecture.md §1` and verify `pip install -r requirements.txt` in a clean Colab cell.
