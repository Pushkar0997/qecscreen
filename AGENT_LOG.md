# AGENT_LOG

Append-only. **Newest entry at the top.** Never edit past entries — append corrections as new ones.

Every session writes an entry, including failed sessions. "Noticed, did not fix" may not be empty without a reason.

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
