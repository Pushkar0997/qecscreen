# product.md — qecscreen

## 1. One-line definition

A public labelled dataset and a trained ranking model that predict which quantum LDPC codes will perform well **at circuit level**, replacing the kd²/n formula that AI-driven code-search loops currently screen candidates with.

## 2. The problem

Searching for better quantum error-correcting codes has become an AI problem in the last six months. IBM, the Max Planck Institute, and NTU have all published LLM- or RL-driven search loops that generate thousands of candidate codes and must decide which few deserve expensive evaluation.

They all screen with the same cheap algebraic proxy: Φ = kd²/n.

In July 2026 the OmniQEC paper demonstrated that this proxy **does not align with circuit-level logical error rate ranking** — several of their discovered codes beat the reference `[[144,12,12]]` bivariate bicycle code at circuit level despite scoring worse on Φ. The same paper names circuit-level evaluation as its main computational bottleneck and explicitly calls for more efficient statistical estimation of logical performance.

So the field is filtering its search space with a ruler it knows is bent, and the people using it have said so in print. Nobody has published a better screening function, and nobody has released the labelled data that would let one be trained.

## 3. Target user

**Primary:** researchers building automated QEC code-discovery loops. Concretely and by name — the OmniQEC group at NTU (Yuxuan Du), IBM Quantum (Juan Cruz-Benito, Andrew Cross), the Marquardt group at MPI Erlangen, and the Bayesian-optimisation group behind arXiv:2601.18562. Roughly a dozen labs, all of whom publish code and are reachable by email.

**Secondary:** anyone doing qLDPC resource estimation who wants a fast first-pass ranking, and the maintainers of QEC tooling (Riverlane's Deltakit, QUITS) who might want this as a component.

**Explicitly not the target:** people learning quantum computing, hardware teams, surface-code decoder researchers, and anyone who wants a GUI. This is a library and a Parquet file for people who already know what BP+OSD is.

## 4. Core promise

> After using this, a researcher can rank 10,000 candidate qLDPC codes in seconds and spend their simulation budget on a shortlist that actually contains the good ones.

Everything gets measured against that sentence. The metric that expresses it is Recall@k, not R².

## 5. Non-goals

Point here when scope creep is proposed.

- **Not a decoder.** DeepMind, NVIDIA and Riverlane are all in that space with far more resources. We consume decoders; we do not write one.
- **Not a code-discovery agent.** We are not competing with OmniQEC or IBM's OpenEvolve work. We supply them. Building our own search loop would put us in a fight we lose and would remove our reason to be adopted.
- **Not a replacement for Stim or exact simulation.** The model screens; simulation decides. This is INV-1 and it is also the positioning.
- **No surface-code work.** Crowded, and the proxy problem does not exist there in the same form.
- **No web app, dashboard, hosted API or GUI.** Costs money (INV-9) and nobody in the target group wants one.
- **No hardware execution.** Nothing in this project touches a real device, which is why it is free.
- **No new code families invented by us.** We generate from published construction programs. Inventing families is a different paper.

## 6. Success metrics

Ranked. Only the top one drives decisions.

1. **Recall@30 of the true top-10, on a held-out code family**, versus the Φ baseline on the same holdout. Target: a clear and reproducible margin over Φ. "Clear" means the gap survives resampling; the exact threshold is set in `spec/evals.md` before M2 results are looked at.
2. `spearman_family_holdout` — the rank correlation, as the continuous companion to (1).
3. Adoption: at least one external group using the dataset or the package, evidenced by a citation, an issue, or a fork with commits.

**Anti-metric — do not optimise:** `spearman_random_split`, and its cousin in-distribution R². A model that memorises construction templates scores brilliantly here while being worthless in an actual search loop. It will be tempting because it is the number that goes up. It is banned from headlines by INV-2.

Second anti-metric: **GitHub stars.** Twelve labs matter. Twelve stars from the right twelve people is the entire goal; two thousand from elsewhere changes nothing.

## 7. Kill criteria

Stop if, at the end of M0:

- Φ already achieves high rank correlation with true circuit-level LER on the pilot set, **and**
- cheap structural features fail to beat it by a margin that survives resampling.

In that case the honest conclusion is that the OmniQEC mismatch is narrower than it looked, and the correct output is a short public write-up saying so with the data attached. That is a real contribution and it costs two weeks instead of five months. It is a successful outcome of this project, not a failure of it.

## 8. Business lens — what this is paid in

Recorded here so nobody later mistakes "no revenue model" for "no thought given to it."

**Stage:** idea. Live checks are value creation, timing, and founder–market fit. Moat, pricing and unit economics are noise at this stage and analysing them would be theatre.

**Value creation:** real and narrow. A named bottleneck, named in print, by the people who have it.

**Timing:** the AI-for-QEC search boom is roughly six months old and every entrant inherited the same broken filter. This window is narrow — expect someone else to attempt this within a year.

**Founder–market fit:** the hard part is ML engineering on quantum-generated data, not quantum theory. That is the actual claimed combination. It is also honestly a step up from the existing portfolio, which is why M0 is a two-week falsification rather than a five-month build.

**The currency is adoption and credibility, not revenue.** Distribution beats capability here: ten right people beat ten thousand strangers. The channel, in order:

1. Publish the dataset on Zenodo before the model works — datasets get used even when models disappoint.
2. Unitary Foundation Discord and their global $4,000 microgrant programme, which exists precisely for open-source quantum tooling.
3. Riverlane and Unitary Foundation's Deltakit Community Fund ($2,000–$4,000 plus mentorship, rolling quarterly) — **check the export-control eligibility clause for India before counting on this one.**
4. Direct email to the four named groups with the benchmark attached.
5. arXiv quant-ph, once M2 closes.

**Commercial optionality, deliberately left open and not pursued:** a validated screening model is the kind of component a QEC tooling vendor would want. Apache-2.0 keeps that door open, and D-012 keeps the stronger option — dual licensing under AGPL plus a paid commercial licence — technically available by requiring DCO sign-off from any external contributor. Do not build toward it; do not close it.

**On compensation, stated plainly so it is not confused with credit:** no permissive licence requires anyone to pay for commercial use. The money reachable from this project in the next year is grant money — the Unitary Foundation microgrant and the Riverlane/Unitary Deltakit fund, both $2,000-$4,000 — and both require an open licence. Credit is protected by CC-BY-4.0 on the dataset, the Apache `NOTICE` file, a Zenodo DOI, an ORCID, and `CITATION.cff`. Those five together are what make the work traceable to you; the licence alone is not.

**What would make this a bad use of five months:** building M3 and M4 before anyone outside has looked at M1. That is the failure this plan is shaped to prevent.

## 9. Glossary

- **Φ (phi)** — the incumbent code-level proxy, kd²/n. The thing to beat.
- **qLDPC** — quantum low-density parity-check code. Sparse checks, finite rate.
- **BB code** — bivariate bicycle code, the family from Bravyi et al. 2024 that IBM's roadmap uses.
- **LER** — logical error rate, per round per logical qubit as pinned in CONTRACT INV-4.
- **Screening** — cheap ranking to allocate expensive evaluation.
- **Recall@k** — of the truly best 10 codes, how many appear in the model's top k.
- **Censored row** — a measurement with too few logical failures to be a point estimate.
