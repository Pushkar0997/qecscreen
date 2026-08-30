# AGENT_LOG

Append-only. **Newest entry at the top.** Never edit past entries — append corrections as new ones.

Every session writes an entry, including failed sessions. "Noticed, did not fix" may not be empty without a reason.

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
