"""Re-projection of the M0 pilot from the 7e91f82 decoder calibration (owner's Part 2, 2026-09-28).

Evidence, not package code: this file records exactly how ``reprojection.json``
was produced. It decodes nothing. It enumerates code populations and calls
``qecscreen.evaluate.calibrate.summarize`` on the committed calibration
output with other ``population``, ``max_shots`` and ``shot_batch`` values.

Decoder: pinned BP+OSD (``bposd``) only.
Grid: p in {0.0015, 0.002}; budget (max n) in {48, 60, 72, 96};
max_shots in {10000, 20000, 50000}; shot_batch 256.

Population at a budget: every admissible (template, l, m) on the balanced
sampler's grid (``validate`` passes, ``estimate_d_upper(seed=0) >= 3``),
checked equal to ``sample_bb_params(<that many>, budget, CALIBRATION_CODE_SEED)``.
At budget 96, where more than 300 exist, the 300-code balanced draw with
``CALIBRATION_CODE_SEED`` is projected as well.

"Above threshold at p" for a template, read from the calibration's BP+OSD
cells at that p (per-round per-qubit LER, 95% Wilson): it has at least two
completed codes, the largest code's interval does not lie wholly below the
smallest's, and every completed code's interval lies wholly above p.
Templates with fewer than two completed calibration codes have no reading.

Run from the repository root: ``python evidence/reprojection/2026-09-28/reproject.py``.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from qecscreen.codes import sample as S
from qecscreen.evaluate.calibrate import CALIBRATION_CODE_SEED, _describe, summarize
from qecscreen.provenance import record

CAL = Path("evidence/calibration/2026-09-27-7e91f82")
OUT = Path(__file__).with_name("reprojection.json")
PS = (0.0015, 0.002)
BUDGETS = (48, 60, 72, 96)
MAX_SHOTS_GRID = (10_000, 20_000, 50_000)
SHOT_BATCH = 256
DECODER = "bposd"
CORES = 4


def population(budget: int) -> list[dict]:
    pairs, _ = S._lm_grid(budget)
    admitted = sorted((S._pid(t), l, m) for t in range(len(S.TEMPLATES)) for (l, m) in pairs
                      if S._rejection_cause(t, l, m) is None)
    drawn = S.sample_bb_params(len(admitted), budget, seed=CALIBRATION_CODE_SEED)
    assert sorted((p["construction_program_id"], p["l"], p["m"]) for p in drawn) == admitted
    return [_describe(p) for p in drawn]


def threshold_readings(summary: dict) -> dict:
    """Per p, per template with >= 2 completed codes: the reading defined above."""
    out: dict = {}
    for p in PS:
        by_t: dict = {}
        for c in summary["per_cell"]:
            if c["p"] == p:
                by_t.setdefault(c["code_id"].split("-")[0], []).append(c)
        out[p] = {}
        for t, cs in sorted(by_t.items()):
            if len(cs) < 2:
                continue
            cs.sort(key=lambda c: c["n"])
            lo = {c["name"]: c["decoders"][DECODER]["ler_ci"] for c in cs}
            small, large = lo[cs[0]["name"]], lo[cs[-1]["name"]]
            improves = large[1] < small[0]
            above_p = all(ci[0] > p for ci in lo.values())
            out[p][t] = {"codes": [c["name"] for c in cs], "larger_separately_lower": improves,
                         "every_interval_above_p": above_p,
                         "above_threshold": (not improves) and above_p}
    return out


def main() -> None:
    base = summarize(CAL)
    readings = threshold_readings(base)
    measured = {t for p in PS for t in readings[p]}
    pops = {b: population(b) for b in BUDGETS}
    draw300 = {c["code_id"] for c in (_describe(p) for p in
               S.sample_bb_params(300, 96, seed=CALIBRATION_CODE_SEED))}
    pops["96_draw300"] = [c for c in pops[96] if c["code_id"] in draw300]
    assert len(pops["96_draw300"]) == 300

    rows = []
    for label, pop in pops.items():
        counts = dict(sorted(Counter(c["construction_program_id"] for c in pop).items()))
        for p in PS:
            above = [t for t, r in readings[p].items() if r["above_threshold"]]
            for max_shots in MAX_SHOTS_GRID:
                s = summarize(CAL, population=pop, max_shots=max_shots, shot_batch=SHOT_BATCH)
                (proj,) = [x for x in s["pilot_projection"] if x["p"] == p and x["decoder"] == DECODER]
                rows.append({
                    "population": str(label), "p": p, "max_shots": max_shots, "shot_batch": SHOT_BATCH,
                    "codes": len(pop), "per_template": counts,
                    "d_upper_range": [min(c["d_upper"] for c in pop), max(c["d_upper"] for c in pop)],
                    "core_hours": proj["core_hours"],
                    "max_code_core_hours": proj["max_code_core_hours"],
                    # One code per process: no packing beats the longest single code.
                    "wall_hours_4_cores": max(proj["core_hours"] / CORES, proj["max_code_core_hours"]),
                    "censored_overall": proj["censored_overall"],
                    "top_third_by_d_upper": proj["top_third_by_d_upper"],
                    "above_threshold_templates": above,
                    "fraction_from_above_threshold_templates":
                        sum(counts.get(t, 0) for t in above) / len(pop),
                    "fraction_from_templates_without_reading":
                        sum(v for t, v in counts.items() if t not in measured) / len(pop),
                    "fit_codes": proj["fit_codes"],
                    "seconds_per_shot_model": proj["seconds_per_shot_model"],
                    "interpolation_brackets": proj["interpolation_brackets"],
                    "outside_fit_range": proj["outside_fit_range"],
                })
    OUT.write_text(json.dumps({
        "calibration": True,
        "source": str(CAL), "decoder": DECODER, "cores": CORES,
        "threshold_readings": {str(p): r for p, r in readings.items()},
        "provenance": record(),
        "rows": rows,
    }, indent=1), encoding="utf-8")
    for r in rows:
        c, t = r["censored_overall"], r["top_third_by_d_upper"]
        print(f"{r['population']:>10} p={r['p']:<6} max_shots={r['max_shots']:>6} codes={r['codes']:>3} "
              f"core_h={r['core_hours']:9.1f} wall_h={r['wall_hours_4_cores']:8.1f} "
              f"cens={c['projected_censored']}+{c['unknown']}?/{r['codes']} "
              f"top={t['projected_censored']}+{t['unknown']}?/{t['codes']} "
              f"above_thr={r['fraction_from_above_threshold_templates']:.3f} "
              f"no_reading={r['fraction_from_templates_without_reading']:.3f} "
              f"outside={len(r['outside_fit_range'])} {r['interpolation_brackets']}")
    assert not math.isnan(sum(r["core_hours"] for r in rows))


if __name__ == "__main__":
    main()
