# AGENT_LOG

Append-only. **Newest entry at the top.** Never edit past entries — append corrections as new ones.

Every session writes an entry, including failed sessions. "Noticed, did not fix" may not be empty without a reason.

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
