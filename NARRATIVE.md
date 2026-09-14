# NARRATIVE.md — qecscreen

A plain-language running account of what happened in this project and what each thing
revealed. It exists so the project's story can be told later — in a README, a write-up, a
grant application, an interview — without reconstructing it from git archaeology.

**Hard rules:**

- This file is **never** a source of truth. `CONTRACT.md`, `spec/` and `AGENT_LOG.md` are.
  Where this file and a spec document disagree, the spec document wins and this file is wrong.
- It is **not** in `AGENTS.md §1`'s read order and must never be added to it.
- No agent ever reads it to decide anything, and no code ever parses it.
- It is **append-only**. Earlier entries are never rewritten, even when they turn out to have
  been mistaken — a mistaken entry gets a later entry correcting it, the same discipline
  `AGENT_LOG.md` uses.
- It is committed, not gitignored.

Reverse chronological — newest first.

---

## 2026-09-14 — The pyarrow pin that went stale in three weeks

A criterion recorded as PASS in August became false in September without a single line of
this repository changing. On 2026-08-30, Colab's ambient `pyarrow` was 18.1.0, matching a
`<19` upper bound set specifically to match it. By 2026-09-14, Colab's ambient `pyarrow` had
moved to 23.0.1 and Kaggle's was at 24.0.0 — so the same pin that once protected against a
downgrade now caused one, uninstalling a newer, working `pyarrow` and replacing it with 18.1.0
on both platforms, breaking `datasets` and `bigframes` in the process. The interesting part is
how close this came to going unnoticed: a first re-measurement checked only post-install
package versions, saw 18.1.0 on both Colab and Kaggle, and read that agreement as a clean
pass — when it was actually both platforms being silently downgraded to the exact same number.
Only reading the raw pip install log, with its `Attempting uninstall: pyarrow` line, exposed
what the resolved version number alone could not show. The pin was removed rather than raised,
because a cap chosen from a snapshot of someone else's base image is a countdown, not a fix.

## 2026-09-14 — Kaggle was never running the interpreter everyone assumed

The stack table's Python row implied, by symmetry with its own lower bound, that Kaggle ran
Python 3.11. Nobody had ever measured it. When Kaggle was actually run, it turned out to ship
Python 3.12.13, not 3.11 — meaning CI's test matrix had, since the day it was introduced, never
once tested the interpreter that will actually run this project's bulk data generation. The fix
was to add 3.12 to the matrix and stop inferring a platform's behaviour from a stack table's
lower bound.

## 2026-09-14 — The manual pip-fix cells nobody needed

Two manual cells had survived in the frozen Colab notebook since 2026-08-30 — a `pyparsing<3.2`
pin and a `matplotlib` upgrade — and it was genuinely unknown whether they had been load-bearing
or just leftover debugging. A fresh run using a single `pip install -r requirements.txt`, no
manual cells at all, resolved `pyparsing` to 3.3.2 and `matplotlib` to 3.10.0 anyway, both
importing clean. The two cells had been unnecessary the whole time; the environment simply
needed a clean run to find that out.

## 2026-09-07 — The audit that found the project hadn't started

A read-only audit counted the last 25 commits and found every one of them was setup, spec or
CI work — not one line of code that generates a quantum code existed yet. `codes/`, `circuits/`,
`evaluate/`, `features/`, `splits.py`, `metrics.py` and `scripts/run_m0_pilot.py` were all still
unwritten, even though the project's spec and tooling machinery looked, on paper, mature. It was
the moment the gap between "the infrastructure feels done" and "the thing the project exists to
build has not begun" became explicit instead of quietly assumed away.

## 2026-08-30 — The CI guard that tested the wrong thing

The install guard in CI used `--only-binary=:all:` to reject anything that looked like it needed
compiling, on the theory that a wheel-only install proves no C toolchain is needed. It didn't
prove that — it proved something narrower, and misleadingly so: `sinter` 1.16.0 ships no wheel
at all, for any Python version, so the wheels-only flag silently fell back to the older `sinter`
1.15.0 on every interpreter, meaning CI was never testing the `sinter` version real installs
actually got. The fix, later formalised as decision D-018, replaced the wheel-availability check
with a grep for an actual compiler invocation in the install log — the thing the guard had been
trying to test all along.

## 2026-08-30 — The sinter claim that was never true

An agent claimed `sinter` 1.16.0 required Python 3.12 or newer, and the claim was repeated into
three separate committed files — `requirements.txt`, `spec/architecture.md`, and
`.github/workflows/ci.yml` — before anyone checked it against real evidence. The real explanation
was mundane: the measurement behind the claim had been run with `--only-binary=:all:`, a
wheels-only install flag. Since `sinter` 1.16.0 has no wheel for any Python version, that flag
falls back to 1.15.0 regardless of interpreter — and the fallback got misread as an interpreter
requirement instead of a flag artifact.

---

## Recurring theme

2026-08-30's sinter claim, 2026-09-14's pyarrow finding, and 2026-09-14's Kaggle interpreter
correction all share the same shape: something was believed and repeated without ever being
directly measured, and each one survived only until an actual measurement forced the question.
