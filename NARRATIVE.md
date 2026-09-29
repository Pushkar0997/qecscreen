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

## 2026-09-29 — The first real session, and why the best codes were the ones going unmeasured

Before spending a week of compute on the pilot, the first Kaggle session ran only 12 of the
244 codes, spread evenly from smallest to largest, as a probe. The plan had leaned on a cost
model built from eight calibration codes, and that model guessed each code's failure rate by
borrowing it from the calibration code most like it. The probe showed how far off those
borrowed guesses were: one code failed 137 times less often than its borrowed rate said.

That mattered because of what happens at the shot limit. A code is only given a measured
error rate once it has failed 100 times; otherwise it is recorded as an upper bound. Three
of the 12 codes hit the 10,240-shot limit first. They were the three that failed least,
which makes them the likeliest to be the best codes, and the project's headline metric is
about finding exactly those. The limit was cutting information from the top of the ranking.
The owner raised it fourfold, to 40,960, enough for all three, and restarted the pilot. Scaled
up from the probe's measured 3.7 core-hours, the full pilot should cost about 110, under the
158 set aside. The same observation raised a question for later: the rules rank censored codes
at the bottom, as if they were the worst, when they are more likely the best.

---

## 2026-09-28 — Choosing the pilot from the measurements, and one number that did not divide

With the calibration in hand, the owner fixed the pilot. It keeps the standard decoder. The
faster one was rejected because it doesn't just fail more often: how much more often varies
from code to code, so it would change which codes look best, and that ranking is exactly what
this project measures. The noise level drops from 0.5% to 0.2%. At 0.2% two of the three
recipes measured behaved as a code should, with bigger codes doing better. The third did not,
and its codes stay in the dataset as a known property rather than being filtered out. The
pilot is now every admissible code up to 72 qubits, 244 of them, listed out in full rather
than sampled. So the old target of "at least 250 rows" became "all 244". A criterion changed
because the population is now defined, not drawn.

The shot limit was meant to be 10,000, in batches of 256. But 10,000 is not a whole number
of 256-shot batches. The project's own rules say both that every batch is exactly 256 shots
and that the limit is never exceeded, and those two rules cannot both hold at 10,000. The
code already refused such a setting, so the clash was caught before anything ran, and the
owner chose 10,240, forty full batches. The reason for a cap near 10,000 is a clock, not
statistics. At about 2.3 seconds per simulated shot on the largest pilot codes, 20,000 shots
of one code would outlast a 12-hour Kaggle session. That is also why a code interrupted
mid-run now picks up after its last finished batch. It re-creates the same random stream and
skips what it already decoded, so the result is the same as if nothing had been interrupted.

---

## 2026-09-28 — Asking every decoder about the same shots, and the cost wall behind it

The project had two decoders to choose between: the slow standard one it had pinned, and a much
faster newer one. An earlier comparison of about 60 simulated shots saw no difference between
them. The calibration run on Kaggle did it differently. It generated each batch of noise once
and made every decoder decode exactly the same shots, then counted only the shots where the
two disagreed. On shared noise the difference is plain. In 15 of the 27 settings tested, the
faster decoder failed 1.2 to 2.5 times as often as the standard one, at odds against chance
of hundreds to one or more. The other settings either had too few shots to tell, or, in one
case at the highest noise, both decoders failed on nearly the same shots. It was never better.
Sixty separately drawn shots could never have
seen that, because the difference was buried in the luck of the draw. The gap also shrank as
the noise rose and differed from code to code. So one decoder's results cannot be converted
into the other's with a fixed correction factor.

The second finding is that "below threshold" is not one fact about bivariate bicycle codes. The
idea is that making a code bigger should make it better, provided the noise is weak enough.
Whether that happened depended on which polynomial recipe built the code:
- For one recipe, the bigger code was clearly better at every noise level from 0.15% up.
- For the recipe of the famous 144-qubit "gross" code, the bigger code was clearly better
  only at 0.2%.
- For a third recipe, the bigger code was no better at any level tested, and both sizes
  protected their information worse than an unprotected qubit would.

A single project-wide noise level can therefore put some families of codes in their useful
regime and others outside it.

The third finding is the cost. Labelling one gross-sized code honestly means decoding until
it has failed 100 times. With the pinned decoder that takes about 30 CPU-hours at 0.2% noise,
and the uncertainty allows several times more. The largest code in the calibration could not
even be held in memory with four copies running side by side. At that price the project
cannot measure the large codes it most wants to rank. That is the case for a screening
surrogate in one number: a cheap score that decides which few codes are worth 30 CPU-hours
each.

## 2026-09-25 — The decoder costs seconds per shot, not milliseconds

The compute budget assumed each simulated experiment would take about 5 milliseconds to decode.
The first real measurement on the reference code took about two seconds, several hundred times
more. The cause is that the fast first stage of the decoder almost never finishes on its own on
realistic noise, so nearly every shot falls through to the slow backup stage. The same small
measurement suggested something worse: at the error rate the project planned to use, the
encoded information did worse per round than an unprotected qubit would. That means the codes
would be ranked in a regime where none of them works. Both findings are from a few dozen shots
on a laptop and need confirming at scale, but together they mean the first real data run cannot
start as planned. The error rate, the decoder settings or the decoder itself has to change
first, and that is a decision for the project owner.

## 2026-09-25 — A feature leaking into the label through the circuit layout

The first version of the simulated experiment reset all the helper qubits at the start of each
round. The helpers that read out the Z checks then sat idle through the whole first half of the
round, picking up noise before they had done anything. That extra noise makes their readings
less reliable, and in this experiment those are the readings that protect the stored
information. How long they waited depended on the code: a code with heavier checks has a longer
first half, so its helpers wait longer and it looks worse. Check weight is one of the cheap
features the screening model is meant to learn from. A model trained on those labels could have
learned "heavier checks are worse" from how the circuit was laid out, not from anything about
the code, and the project would have reported a screening signal that its own measurement
pipeline had manufactured. The fix resets each helper just before it is used and reads it out
just after, without making the rounds any longer. It also got a new protocol name, because a
change that alters labels has to be distinguishable from the old version in the data. Both
changes were free only because no labels had been generated yet.

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
