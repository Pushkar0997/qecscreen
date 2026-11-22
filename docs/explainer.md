# How Quantum Error Correction & Screening Work (`qecscreen` Visual Guide)

*A standalone, beginner-friendly walkthrough with ASCII diagrams for students, ML engineers, software developers, and early-stage QEC researchers.*

You do not need a quantum physics PhD to understand what `qecscreen` measures or why it exists. This guide walks step-by-step from a single noisy qubit all the way to machine-learning code screening — explaining every concept visually and connecting it directly to what `qecscreen` computes.

---

## Table of contents

1. [Why we need quantum error-correcting codes](#1-why-we-need-quantum-error-correcting-codes)
2. [What a quantum LDPC code is (and what `n`, `k`, `d_upper` mean)](#2-what-a-quantum-ldpc-code-is-and-what-n-k-d_upper-mean)
3. [Tanner graphs: turning parity checks into a network](#3-tanner-graphs-turning-parity-checks-into-a-network)
4. [Syndrome-extraction circuits: where real hardware noise enters](#4-syndrome-extraction-circuits-where-real-hardware-noise-enters)
5. [Decoders: turning error clues into fixes (`Stim` + `BP+OSD`)](#5-decoders-turning-error-clues-into-fixes-stim--bposd)
6. [Measuring ground truth: shots, LER, and censoring](#6-measuring-ground-truth-shots-ler-and-censoring)
7. [Code screening: why `Φ = kd²/n` is not enough](#7-code-screening-why-φ--kd²n-is-not-enough)
8. [How `qecscreen` evaluates ML screeners fairly](#8-how-qecscreen-evaluates-ml-screeners-fairly)
9. [Quick visual summary: M0 at a glance](#9-quick-visual-summary-m0-at-a-glance)

---

## 1. Why we need quantum error-correcting codes

Classical computer bits (`0` or `1`) almost never flip by accident. **Physical qubits** in today's quantum hardware are the opposite: roughly 1 in 1,000 to 1 in 100 operations fails due to heat, stray electromagnetic fields, or imperfect control pulses.

Worse, qubits suffer from **two** kinds of errors (not just bit flips):
- **X errors (bit flips):** flips `|0>` <-> `|1>` (like a classical bit flipping).
- **Z errors (phase flips):** flips the quantum phase `+` <-> `-` (no classical equivalent).
- **Y errors:** both an X error and a Z error at the same time.

And because of the **no-cloning theorem**, you cannot just copy a qubit three times and take a majority vote directly. Instead, a **quantum error-correcting (QEC) code** spreads `k` protected **logical qubits** across `n` noisy **physical data qubits**, and uses extra helper qubits (**ancilla qubits**) to check *relationships* between data qubits without ever reading the stored quantum data itself.

```text
  WITHOUT QEC:
  +-------------------+      noise (p ~ 0.002)      +-------------------+
  | 1 physical qubit  | --------------------------> | corrupted quickly |
  +-------------------+                             +-------------------+

  WITH A QEC CODE:
  +-----------------------------------------+
  |   n noisy physical data qubits          |
  |   + n_ancilla helper (check) qubits     |   ====>   k reliable logical qubits
  |   + repeated checks + classical decoder |           (much lower failure rate)
  +-----------------------------------------+
```

---

## 2. What a quantum LDPC code is (and what `n`, `k`, `d_upper` mean)

Every QEC code is summarized by three headline numbers written `[[n, k, d]]`:

| Symbol | Name | Plain-English meaning | Analogy |
|---|---|---|---|
| **`n`** | Block length | How many physical **data qubits** the code uses | Total bricks used to build a vault |
| **`k`** | Logical qubits | How many protected qubits you get out of it | How many valuables fit inside |
| **`d`** | Distance | Minimum number of simultaneous qubit errors needed to cause an *undetectable* logical failure | How many locks a burglar must pick at once without tripping an alarm |

> **Important `qecscreen` rule (`INV-5`):** Finding the exact distance `d` of a quantum LDPC code is computationally hard (NP-hard in general). In M0, distances come from a randomized decoder-assisted search that finds low-weight logical errors, giving an **upper bound `d_upper`** (so the true distance satisfies `true distance <= d_upper`). That is why `qecscreen` writes `[[72, 12, <=6]]` and stores `d_upper` separately from `d_exact`.

### What makes a code **LDPC** (and **CSS** / **Bivariate Bicycle**)?

- **CSS code:** Separates error checking into two binary parity-check matrices over GF(2) (modulo-2 arithmetic, where `1 + 1 = 0`):
  - `H_X`: checks that detect **Z (phase-flip)** errors.
  - `H_Z`: checks that detect **X (bit-flip)** errors.
  - To be quantum-valid, every X-check and Z-check must overlap on an **even** number of qubits (`H_X * H_Z^T = 0 mod 2`), so measuring one does not scramble the other.
- **LDPC (Low-Density Parity-Check):** Each check only touches a small, bounded number of data qubits (low **check weight**), and each data qubit only participates in a few checks (low **qubit degree**). Unlike older 2D surface codes (which need huge numbers of physical qubits per logical qubit), quantum LDPC codes can pack many logical qubits (`k`) into a modest number of physical qubits (`n`).
- **Bivariate Bicycle (BB) codes:** The code family tested in M0. A BB code is defined compactly by a grid size `(l, m)` and two short polynomials `A(x, y)` and `B(x, y)`. Changing the polynomial template changes the check weight, connectivity, and qubit budget.

---

## 3. Tanner graphs: turning parity checks into a network

A parity-check matrix (`H_X` or `H_Z`) is hard to read as a grid of 0s and 1s, so QEC researchers draw it as a **Tanner graph** — a two-sided (bipartite) network connecting **data qubits** (`O`) to **check nodes** (`[]`).

An edge connects data qubit `q_i` to check `c_j` whenever entry `(j, i)` of the matrix is `1`:

```text
  Parity-check matrix H_Z             Corresponding Tanner Graph
       q0  q1  q2  q3  q4
  c0 [  1   1   1   0   0 ]           (q0)   (q1)   (q2)   (q3)   (q4)   <-- Data qubits
  c1 [  0   1   1   1   0 ]            |     /  \   /  \   /        |
  c2 [  0   0   1   1   1 ]            |    /    \ /    \ /         |
                                       |   /      X      \          |
  Check weight (row sum) = 3           |  /      / \      \         |
  (each check touches 3 qubits)       [c0]------/   \-----[c1]-----[c2]  <-- Parity checks
                                       ^                    ^
                                       |                    |
                                  Notice a 4-cycle: q1 -> c0 -> q2 -> c1 -> q1 !
```

### Why `qecscreen` extracts features from the Tanner graph

Running a full noisy circuit simulation takes minutes to hours, but computing graph properties of the Tanner graph takes **milliseconds**. Many of the 28 features in `m0_features.parquet` describe this graph directly:

1. **Check weight (`check_weight_min/max/mean`):** How many data qubits each check touches.
   - *Why it matters:* A weight-8 check requires 8 noisy two-qubit gates per round instead of 4. More gates = more noise injected by the checking circuit itself!
2. **Qubit degree (`qubit_degree_*`):** How many checks each data qubit participates in.
3. **Short cycles (`cycle4_count_*`, `cycle6_count_*`, `girth_*`):** Closed loops in the Tanner graph (like `q1 - c0 - q2 - c1 - q1` above, which is a **4-cycle**). **Girth** is the length of the shortest cycle.
   - *Why it matters:* Belief Propagation decoders assume messages arriving at a node are independent. Short loops bounce messages back to themselves, confusing the decoder.
4. **Spectral gap (`lambda2_x`, `lambda2_z`) & components (`n_components_*`):** Measures how well-connected ("expanding") the graph is, and whether it splits into disconnected pieces.

---

## 4. Syndrome-extraction circuits: where real hardware noise enters

A Tanner graph is only a static blueprint. On a real quantum computer, you have to execute a **syndrome-extraction circuit** repeatedly over `r` **rounds** (in M0, `r = d_upper`).

In each round, an **ancilla qubit** is reset, entangled with each of its neighbor data qubits one by one via two-qubit **CX (CNOT) gates**, and finally measured to output a `0` (all good) or `1` (an odd number of errors occurred nearby).

```text
  ONE ROUND OF SYNDROME EXTRACTION (simplified single check of weight 4)

  Time (circuit ticks) --->    t0      t1      t2      t3      t4      t5
                             +----+  +----+  +----+  +----+  +----+  +----+
  Data q0  ------------------+ CX +--+idle+--+idle+--+idle+--+idle+--+----+---
                               |       *       *       *       *
  Data q1  ------------------+idle+--+ CX +--+idle+--+idle+--+idle+--+----+---
                               *       |       *       *       *
  Data q2  ------------------+idle+--+idle+--+ CX +--+idle+--+idle+--+----+---
                               *       *       |       *       *
  Data q3  ------------------+idle+--+idle+--+idle+--+ CX +--+idle+--+----+---
                               *       *       *       |       *
  Ancilla  --[Reset |0>]-----+ @  +--+ @  +--+ @  +--+ @  +--+Meas+--+----+---
                               *       *       *       *       *        |
                                                                        v
                                                                 Syndrome bit
                                                                 (0 or 1)

  Where `*` = noise injected at physical error rate p = 0.002:
    - Two-qubit depolarizing error after every CX gate
    - Single-qubit depolarizing error on idle qubits waiting during a tick
    - Reset and measurement flip errors on ancillas
```

### Why circuit-level performance differs from static math (`Φ = kd²/n`)

Look at the diagram above and notice three things `Φ = kd²/n` **completely ignores**:
1. **Circuit depth (`circuit_ticks`) and gate count (`cx_per_round`, `cx_total`):** Higher check weight means more CX gates and more ticks where other data qubits sit idle accumulating noise.
2. **Error propagation (hook errors):** An error on an ancilla qubit halfway through a round (say at tick `t2`) can copy itself onto *multiple* data qubits (`q2` and `q3`) via later CX gates — turning 1 physical fault into 2 data errors!
3. **Faulty measurements:** Because ancilla measurements themselves can misfire, we cannot trust a single round. We repeat checks for `r` rounds and look for **changes** between consecutive rounds (**detectors**).

In M0, `qecscreen` pins the exact X-then-Z phased gate schedule (`bb_monomial_matching_xz_phased_v2`) so every BB code is measured fairly without ancillas sitting idle while holding a syndrome.

---

## 5. Decoders: turning error clues into fixes (`Stim` + `BP+OSD`)

When we simulate one "shot" (one complete run of `r` rounds of noisy memory), here is what happens inside `qecscreen`:

```text
  +-------------------------+
  |   1. STIM SIMULATOR     |  Runs the noisy circuit for r = d_upper rounds
  |   (uniform noise p=0.002|  Samples random physical errors on gates, idles,
  |    pinned seed)         |  resets, and measurements.
  +-----------+-------------+
              |
              |  Outputs:
              |   (a) Detector syndrome bits (the error clues)
              |   (b) Actual logical observable flips (hidden answer key)
              v
  +-------------------------+
  |   2. BP+OSD DECODER     |  Sees ONLY the syndrome clues — NOT the errors!
  |   (ldpc 2.4.1)          |
  |                         |  Stage A — BP (Belief Propagation):
  |                         |    Fast iterative message-passing on the
  |                         |    detector error graph (up to 30 iterations).
  |                         |    Solves most easy shots quickly.
  |                         |
  |                         |  Stage B — OSD (Ordered Statistics Decoding):
  |                         |    If BP fails to converge (often due to short
  |                         |    cycles or degenerate errors), OSD runs a
  |                         |    slower Gaussian-elimination search (order 10)
  |                         |    using BP's soft probabilities to find a valid fix.
  +-----------+-------------+
              |
              |  Outputs: Predicted logical observable flip (0 or 1)
              v
  +-------------------------+
  |   3. COMPARE WITH TRUTH |
  |   Prediction == Actual? |  YES --> Shot SUCCEEDED (error corrected!)
  |                         |  NO  --> Shot FAILED (logical failure +1)
  +-------------------------+
```

**Why decoding is the compute bottleneck:**
Stim can sample thousands of noisy shots in a fraction of a second, but running **BP+OSD** (especially when BP stalls and falls back to OSD-10) took **1.1 to 2.3 seconds per shot** on larger M0 codes — adding up to **76.3 CPU core-hours** for just 242 small codes.

---

## 6. Measuring ground truth: shots, LER, and censoring

One shot only tells you "pass" or "fail". To estimate a code's true failure probability accurately, we repeat shots in batches of 256:

```text
  Start code (shots = 0, failures = 0)
         |
         v
  +--------------------------------------+
  | Run 256 noisy shots & decode them    |<----------------------+
  +------------------+-------------------+                       |
                     |                                           |
                     v                                           |
           failures >= 100 ? ---- NO ----> shots >= 40,960 ? ---- NO
                     |                             |
                    YES                           YES
                     |                             |
                     v                             v
         +-----------------------+     +---------------------------+
         |   UN-CENSORED ROW     |     |      CENSORED ROW         |
         | Compute true_ler and  |     | Too few failures to guess |
         | 95% Wilson CI         |     | a reliable point estimate:|
         | (enough precision!)   |     |   censored = True         |
         +-----------------------+     |   true_ler = null         |
                                       |   true_ler_ub = 95% upper |
                                       |                 bound     |
                                       +---------------------------+
```

### How `true_ler` is normalized (`INV-4`)

Suppose a code protecting `k` logical qubits runs for `r` rounds and fails in fraction `P_L = failures / shots` of the runs. A code with `k = 12` logical qubits running for `r = 6` rounds has `72` logical-qubit-rounds of exposure, whereas a `k = 2, r = 3` code has only `6`.

To compare codes fairly on the same per-round, per-logical-qubit scale, `qecscreen` uses one pinned formula everywhere:

```text
  true_ler = 1 - (1 - P_L) ** (1 / (r * k))
```

Lower `true_ler` = better code.

### Why good codes cost 40x more to measure

A bad code might fail 10% of the time — reaching 100 failures in just ~1,024 shots (the M0 median).
A great code might fail only 0.25% of the time — needing **24,320 to 40,960 shots** to reach 100 failures (or hitting the 40,960-shot cap as a censored row, like the #2 code in M0 with 93 failures).

**This cost asymmetry is the entire reason screening matters:** you want to reserve your 40,000-shot budgets for genuinely promising codes, not waste CPU hours verifying bad ones.

---

## 7. Code screening: why `Φ = kd²/n` is not enough

In an automated QEC code-discovery loop (driven by search algorithms, RL, or LLMs), the pipeline has two stages:

```text
  Thousands of candidate codes generated
                   |
                   v
  +----------------------------------------------------+
  |  STAGE 1: CHEAP SCREENING (milliseconds per code)  |
  |  Score every candidate WITHOUT running Stim/BP+OSD |
  |                                                    |
  |   Old way:  Φ = k * (d_upper)^2 / n                |
  |   New way:  ML screener (e.g., LightGBM on 28      |
  |             graph + circuit features)              |
  +------------------------+---------------------------+
                           |
                           | Keep only the top K picks (e.g., top 30)
                           v
  +----------------------------------------------------+
  |  STAGE 2: EXPENSIVE SIMULATION (hours per batch)   |
  |  Run full Stim + BP+OSD circuit-level simulation   |
  |  on the shortlisted candidates only                |
  +----------------------------------------------------+
```

### What went wrong with `Φ = kd²/n` in M0?

In M0, all 10 genuinely lowest-error codes had **light checks** (weight 4, from template `pair_2_2`) and only **`k = 2`** logical qubits, giving them a small `Φ <= 1.64`.

Because `Φ` multiplies directly by `k`, it promoted dozens of heavier-check codes with `k = 6, 8, or 12` straight to the top of its list — even though their heavier parity-check circuits produced far higher circuit-level error rates!

```text
  RANKING BY Φ = kd²/n (M0):
    Rank   1 ..  30 :  High-k, heavier-check codes   -->  0 of the true top-10!
    Rank  31 ..  70 :  More high-k codes             -->  (Recall@30 = 0.000)
    Rank  71 .. 242 :  All 10 true best codes buried down here!

  RANKING BY LightGBM ON 28 CHEAP FEATURES (M0, leave-one-program-out):
    Overall ordering across all 242 codes: Spearman = 0.871  (vs Φ = 0.242)
    Top-30 shortlist catches 2 of the true top-10: Recall@30 = 0.200 [0.000, 0.600]
```

---

## 8. How `qecscreen` evaluates ML screeners fairly

Machine-learning benchmarks in science can accidentally fool themselves. `qecscreen` enforces two strict evaluation rules:

### Rule A: Never split rows randomly (`INV-2`)

Codes generated by the same polynomial template (e.g., `bb_v1_pair_2_2`) are close cousins. If you split individual codes randomly into train and test sets, the model sees nearly identical siblings during training and memorizes them — giving an inflated score that collapses on any genuinely new code construction.

Instead, `qecscreen` uses **grouped splits**:

```text
  BANNED — Random row split (leaks sibling codes):
    Train: [ pair_2_2 #1, pair_2_2 #3, quad_4_2 #2, ... ]
    Test:  [ pair_2_2 #2, quad_4_2 #1, ... ]   <-- too easy! Siblings memorized.

  REQUIRED — Leave-one-program-out (M0) / Held-out family (M2+):
    Fold 1:  Train on 10 templates  --->  Test on ALL of pair_2_2  (unseen recipe!)
    Fold 2:  Train on 10 templates  --->  Test on ALL of quad_4_2  (unseen recipe!)
    ...
    Fold 11: Train on 10 templates  --->  Test on ALL of tri_3_3   (unseen recipe!)
```

### Rule B: Measure both shortlist discovery (`Recall@30`) and global ordering (`Spearman`)

```text
  Suppose all 242 codes are sorted by TRUE measured LER (best on left):

  True Top 10:   [ 1  2  3  4  5  6  7  8  9 10 ]  [ 11 ........ 242 ]
                   \____________________________/
                                 |
         How many of these 10 landed inside the model's Top 30 picks?
         ---> Recall@30-of-top-10  (Headline screening metric)

  Meanwhile, how well does the model's order match ALL 242 positions left-to-right?
         ---> Spearman rank correlation  (Global ordering metric)
```

---

## 9. Quick visual summary: M0 at a glance

Why did M0 produce the verdict **PROCEED, with the headline criterion FAILED**?

```text
  THE M0 EXPERIMENT (242 BB codes, n <= 72, p = 0.002)
  ====================================================

  1. Did LightGBM beat Φ at catching the top 10 in its top 30 (Recall@30)?
       Model: 0.200 [0.000, 0.600]
       Φ:     0.000 [0.000, 0.000]
       Gap:   +0.200 [0.000, 0.600]  <-- 95% CI touches 0  ==>  HEADLINE FAIL

       Why? All 10 true best codes came from ONE template (pair_2_2), so one
       single held-out fold decided the entire Recall@30 metric. (Not label
       noise: the label-noise ceiling is a clean 1.000.)

  2. Did the kill condition fire (is Φ already good enough)?
       Model Spearman: 0.871 [0.838, 0.894]
       Φ Spearman:     0.242 [0.118, 0.354]
       Gap:            +0.629 [0.521, 0.750]  <-- clearly > 0 ==>  DO NOT KILL

  3. Verdict: PROCEED to M1 (widen to GB + HGP families, larger n, multiple p)
     so that top codes span multiple templates and families, eliminating the
     single-fold bottleneck.
```

---

## Where to go next

- **[README.md](../README.md)** — Install `qecscreen`, load the 242-row M0 Parquet snapshot, and test your own screening score in 10 lines of Python.
- **[docs/m0-writeup.md](m0-writeup.md)** — Full scientific write-up of Milestone 0, including per-template sub-threshold scaling, exploratory single-feature checks, limitations, and exact SHA-256 reproducibility records.
- **[NARRATIVE.md](../NARRATIVE.md)** — Plain-language engineering journal of the surprises and bugs encountered while building M0.
- **[CONTRACT.md](../CONTRACT.md)** — The exact mathematical invariants and pinned simulation constants enforced by `qecscreen`'s test suite.
