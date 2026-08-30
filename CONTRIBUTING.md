# Contributing

Thanks for looking. A short note on process, because one detail here is
impossible to fix later.

## Sign your commits off (DCO)

Every commit must carry a `Signed-off-by` line:

```bash
git commit -s -m "feat(codes): M0-CODES-01 add BB generator"
```

That line certifies you wrote the contribution and have the right to submit it
under this project's licence. See https://developercertificate.org/.

**Why this is enforced from day one:** the project may later be offered under a
second, commercial licence alongside Apache-2.0 (see `spec/decisions.md` D-012).
That is only possible while copyright ownership stays consolidated. Once a
non-trivial contribution lands without sign-off, relicensing needs that person's
permission, and in practice the option disappears. Requiring sign-off costs
nothing today and cannot be retrofitted.

## Before opening a PR

1. Read `AGENTS.md` and `CONTRACT.md`. The invariants in `CONTRACT.md` are not
   style preferences — several of them exist because violating them produces
   plausible, confident, wrong numbers.
2. `pytest` passes, including the source-hygiene tests.
3. One task, one commit, task ID from `spec/tasks.md` in the message.
4. If behaviour diverged from the spec, update the spec in the same PR.

## Adding a dependency

Check licence compatibility with Apache-2.0 redistribution. A GPL or AGPL
dependency would force this project to relicense — open an issue rather than a
PR. Record accepted additions in `spec/decisions.md`.

## Data

Never commit a Parquet file or anything under `data/`. Dataset releases go to
Zenodo with a DOI, and a published DOI is never deleted or overwritten — a
correction is a new version.
