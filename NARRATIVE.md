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

## 2026-09-25 — Where the noise sits decides which codes look good

Building the simulated experiment meant pinning details the protocol had left open. One of them
turned out to matter for the ranking itself, not just for tidiness. Each code is run for as many
rounds as its distance, then its error rate is divided by that number of rounds. Noise at the
very start and end of an experiment happens once, not once per round. After the division it gets
spread thinner over the long runs of strong codes than over the short runs of weak ones. That
tilts the per-round number by distance, which is the ranking the project exists to measure. The
fix is to make the start and end noiseless, so every bit of noise lives inside the rounds that
get divided out. The same session confirmed, by deliberately breaking the circuit, that mixing
the two kinds of checks in an arbitrary order really does measure the wrong thing: Stim refuses
to build an error model for that circuit at all.


## 2026-09-25 — The tests checked the names, not the codes

An independent check by the owner found two things the test suite had waved through. First,
two pairs of "different" code recipes were the same recipe written two ways: swapping the two
polynomials just relabels the qubits. That let near-identical codes sit on both sides of the
train/test split the project's headline metric depends on. Second, one recipe used the same
polynomial twice, which guarantees distance at most 2. Codes like that correct nothing, and
they made up 14-23% of the samples drawn so far. Every test had passed, because every test
checked that the *labels* were consistent and none checked the *codes*. The fix removes the
duplicates, adds a rule that nothing below distance 3 gets in, and rewrites the tests to
generate the codes and compare them. The lesson for the rest of the project: a
consistency check on identifiers can't catch errors in the objects they point to.

## 2026-09-25 — Nearly a third of the "diverse" sample was the same codes twice

The first code sampler drew polynomial templates uniformly, which sounds fair until you notice
that some templates produce a valid code 100% of the time and others 9%. The 300-code sample it
made put 263 codes in four templates and none at all in one. Because the headline evaluation
holds out whole templates, that quietly shrank a ten-way holdout to about four. Looking closer
for the fix turned up something worse: 95 of those 300 codes were exact repeats. The rebalanced
sampler gives every template a fair share of *distinct* codes, and where a template simply
doesn't have enough distinct valid codes at this size (five have only 17-20), it says so and
hands the remainder to the others, rather than padding with copies to look even.

## 2026-09-14 — The pyarrow loop closed in a single day

The same day the stale `pyarrow<19` pin was found forcing a downgrade on both Colab and Kaggle,
it was fixed and checked. The upper bound was removed, both platforms were re-measured from a
factory reset against the new pin, and both came back clean — zero uninstalls, the ambient
`pyarrow` (23.0.1 on Colab, 24.0.0 on Kaggle) left alone, only the four packages this project
actually adds. A criterion recorded as PASS in August had gone to FAIL in September without a
line of this repository changing; by the end of the same day it was PASS again, this time
because the repository actually changed.

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
