# AGENT_LOG

Append-only. **Newest entry at the top.** Never edit past entries — append corrections as new ones.

Every session writes an entry, including failed sessions. "Noticed, did not fix" may not be empty without a reason.

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
