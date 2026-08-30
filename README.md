# qecscreen

**Status: pre-M0. No results yet. Nothing here has been validated.**

Screening for quantum LDPC code search: predicting which codes will perform well
*at circuit level*, so that automated code-discovery loops spend their simulation
budget on candidates that are actually good.

## Why

Automated QEC code discovery has become an active area in 2026 — LLM-guided and
RL-driven search loops generating thousands of candidate codes. They all screen
candidates with the same cheap algebraic proxy, Φ = kd²/n, and recent work has
shown that this proxy does not align with circuit-level logical error rate
ranking. The field is filtering its search space with a ruler it knows is bent.

This project tests whether cheap structural features can screen better, and
releases the labelled dataset that would let anyone else try.

## What is here right now

The spec system and a small validated core. No dataset, no model, no claims.

```
CONTRACT.md     invariants that must never break — read this first
AGENTS.md       rules for AI coding agents
BRIEF.md        one-page status; start here if you are the maintainer
spec/           product, architecture, plan, tasks, evals, smoke, decisions
src/qecscreen/  protocol constants, GF(2) linear algebra
tests/          golden values and source-hygiene checks
```

## Install

```bash
pip install -r requirements.txt
pytest
python -m qecscreen.selfcheck
```

Runs entirely on CPU. No quantum hardware, no API keys, no paid services.

## Honest caveats

- The headline metric, when there is one, will be **held-out code family**
  performance. Random-split numbers are inflated and are banned from headlines.
- Code distances are upper bounds unless explicitly marked exact.
- A negative result — that Φ is fine and cheap features do not beat it — is a
  valid and intended outcome of the first milestone.

## Licence and citation

Source is licensed under the **Apache License 2.0** — see `LICENSE` and `NOTICE`.
Any released dataset is licensed separately under **CC-BY-4.0**; attribution is a
condition of that licence, not a courtesy.

If you use this in academic work, cite it using `CITATION.cff`.

Copyright 2026 Pushkar Kumar. Licensing the source permissively does not transfer
copyright; the author retains it.
