# BRIEF — qecscreen

*One page. Read in 3 minutes. Rewritten whenever state changes.*

**What this is:** A dataset and ranking model that predict which quantum LDPC codes will perform well at circuit level, replacing the kd²/n formula that AI code-search loops currently screen with.

**Repo:** `<github url — fill on first push>` · **Dataset:** not yet released (M1)

---

## Where things stand

**Milestone:** M0 — Falsification
**Exit criteria:** a recorded verdict on whether cheap structural features beat Φ at Recall@30-of-top-10, on a construction-program-grouped split, with bootstrap CIs
**Progress:** 0 of 30 tasks. Spec system written, repo skeleton in place, `pytest` green.

**Last done:** spec system authored; `protocol.py` and `linalg.py` scaffolded with golden-value tests passing
**Next:** `M0-SETUP-01` — pin `requirements.txt` and verify a clean install in Colab

---

## Prompt for the next session

Copy this into any coding agent:

```
Read AGENTS.md, then CONTRACT.md, then spec/plan.md and spec/tasks.md.
Then read the top 3 entries of AGENT_LOG.md.

Tell me which milestone is active and which task you propose next.
Do not write code yet.
```

---

## Three things most likely to break

1. **The BB generator silently produces a wrong code.** Everything downstream measures something else. Guarded by golden tests G-07..G-10 against the published `[[72,12,6]]` reference — run them before trusting any label.
2. **A random train/test split gets used somewhere.** Score jumps to something wonderful and meaningless. Guarded by INV-2 and a source-grep test, but it is the natural thing to type.
3. **Decode cost turns out much worse than the 5 ms/shot placeholder**, and the M0 pilot does not fit in a Kaggle session. `M0-EVAL-05` measures it early for exactly this reason.

---

## Where everything is

| Need | File |
|---|---|
| What must never break | `CONTRACT.md` |
| Rules for agents | `AGENTS.md` |
| What happened when | `AGENT_LOG.md` |
| What we're building and why | `spec/product.md` |
| Stack, structure, capability register | `spec/architecture.md` |
| Milestones | `spec/plan.md` |
| The backlog | `spec/tasks.md` |
| How correctness is proven | `spec/evals.md` |
| Pre-release checklist | `spec/smoke.md` |
| Why things are the way they are | `spec/decisions.md` |

---

## Standing rules

- **Cost ceiling:** ₹0/month. No servers, no paid APIs, no keys. (INV-9)
- **Anti-metric — never optimise or headline:** `spearman_random_split`, in-distribution R², GitHub stars.
- **Real metric:** Recall@30 of the true top-10, family-holdout, vs the Φ baseline.
- **Publish before polishing:** the M0 write-up goes public within 7 days of the verdict, whatever it says. (INV-10)
- **A negative result closes the project successfully.** See `spec/product.md §7`.
- **Licence:** Apache-2.0 (source), CC-BY-4.0 (dataset). Private through M0, public from M1. See D-011, D-013.
- **Contributions require DCO sign-off** (`git commit -s`) so copyright stays consolidated. See D-012.
