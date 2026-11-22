# BRIEF — qecscreen

*One page. Read in 3 minutes. Rewritten whenever project state changes.*

**What this is (in plain English):** Automated quantum error correction (QEC) code searches generate thousands of candidate quantum LDPC codes, but running realistic noisy circuit simulations on every candidate is far too slow. Today, search loops filter candidates with a quick math formula (`Φ = kd²/n`) that ignores circuit-level noise and decoder difficulty. `qecscreen` provides real, reproducible circuit-level error-rate measurements and a benchmark suite to test whether cheap structural models can screen candidate codes better than `Φ`.

**Repo:** `https://github.com/Pushkar0997/qecscreen` (public) · **Dataset:** M0 snapshot committed under `evidence/m0-verdict/2026-10-03-1131f10/data/` (CC BY 4.0); Zenodo DOI planned for M1.

---

## Where things stand

**Currently active milestone:** **None.** M0 closed on **2026-10-03**; **M1 has not started** (owner's call).

**M0 outcome — PROCEED, headline criterion FAILED (`spec/evals.md §7`):**
- **Dataset produced:** 242 of 244 enumerated bivariate bicycle (BB) codes (`n ≤ 72`, `d_upper ≥ 3`, 11 templates, `p = 0.002`, Z-memory, `Stim 1.16.0` + `ldpc 2.4.1` BP+OSD; 76.3 core-hours on free Kaggle CPUs; 2 `mixed_3_5` codes excluded under D-036; 1 code censored at 40,960 shots).
- **Headline metric (`Recall@30-of-top-10`, leave-one-program-out):** LightGBM **0.200** `[0.000, 0.600]` vs. `Φ` **0.000** `[0.000, 0.000]`. Difference `[0.000, 0.600]` includes zero → **FAIL**. All top-10 codes came from one template (`pair_2_2`), so one held-out fold decided the entire headline metric. Label-noise ceiling is `1.000` (measurements are sharp; the miss is model extrapolation).
- **Global ranking (`Spearman`, leave-one-program-out):** LightGBM **0.871** `[0.838, 0.894]` vs. `Φ` **0.242** `[0.118, 0.354]` (lead **+0.629** `[0.521, 0.750]`) → **kill condition not met**, so the project proceeds.
- **Published write-up:** [docs/m0-writeup.md](docs/m0-writeup.md) (INV-10 satisfied on 2026-10-03).

**Last done:** M0 closed, write-up published, M0 Parquet snapshot committed with CC BY 4.0 licence, and documentation/READMEs rewritten for broader readability.
**Next:** Decide whether to start **M1 (Dataset v0.1)** — decompose M1 tasks in `spec/tasks.md` (add GB and HGP families, 3 qubit budgets, 3 values of `p`, ~2,000 rows, fix colliding-monomial enumeration before pinning, and publish a Zenodo DOI).

---

## Prompt for the next agent session

Copy this into any coding agent:

```text
Read AGENTS.md, then CONTRACT.md, then spec/plan.md and spec/tasks.md.
Then read the top 3 entries of AGENT_LOG.md.

Tell me which milestone is active and which task you propose next.
Do not write source changes yet.
```

---

## Three things to watch out for going into M1

1. **Enumeration hygiene before pinning.** Two M0 `mixed_3_5` codes had coinciding monomials (`x³ = x` at `l = 2`) that passed matrix checks but failed syndrome scheduling (`D-036`). Reject unbuildable parameter sets *before* freezing M1's population digest.
2. **Never let random splits or mixed protocols slip in.** Random row splits inflate scores via template siblings (`INV-2`), and mixing rows across different `protocol_hash` values invalidates every comparison (`INV-6`). Keep automated guards green.
3. **Measure decode cost before bulk runs.** M0 decode cost was ~1–2 s/shot on small BB codes (76.3 core-hours total). Adding GB/HGP families, larger `n`, and lower `p` will shift CPU cost sharply — always run a timed probe first (`spec/architecture.md §6`).

---

## Where everything is

| Need | File |
|---|---|
| Plain-English overview, results & usage | `README.md` |
| Detailed M0 write-up (accessible + technical) | `docs/m0-writeup.md` |
| Plain-language project history | `NARRATIVE.md` |
| What must never break (invariants & protocol) | `CONTRACT.md` |
| Rules for coding agents | `AGENTS.md` |
| Session-by-session changelog | `AGENT_LOG.md` |
| What we are building and why | `spec/product.md` |
| Stack, structure, capability register, compute budget | `spec/architecture.md` |
| Milestones (M0–M4) | `spec/plan.md` |
| Task checklist & backlog | `spec/tasks.md` |
| How correctness is proven & M0 verdict (§7) | `spec/evals.md` |
| Pre-release checklist | `spec/smoke.md` |
| Numbered design decisions (`D-001`–`D-037`) | `spec/decisions.md` |

---

## Standing rules

- **Cost ceiling:** ₹0/month. CPU-only; no paid APIs, no servers, no keys (`INV-9`).
- **Anti-metrics (never optimize or headline):** `spearman_random_split`, in-distribution R², GitHub stars.
- **Real headline metric (from M2):** `Recall@30-of-top-10` on a **held-out code family** vs. `Φ`.
- **Honesty & transparency:** Never round up a failed headline; publish verdicts promptly (`INV-10`); never conflate `d_upper` with exact distance (`INV-5`) or predictions with measurements (`INV-1`).
- **Licences:** Apache-2.0 for source (`LICENSE`, `NOTICE`); CC BY 4.0 for released datasets (`evidence/m0-verdict/2026-10-03-1131f10/data/LICENSE`).
- **Contributions require DCO sign-off** (`git commit -s`) per `CONTRIBUTING.md` (`D-012`).
