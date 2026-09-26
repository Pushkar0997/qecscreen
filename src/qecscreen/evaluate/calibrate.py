"""Decoder calibration: measure the pinned BP+OSD against BP+LSD before the pilot.

This run produces the numbers the owner will use to choose the decoder,
``P_PILOT``, ``SHOT_BATCH`` and possibly ``MAX_SHOTS``. It changes none of
them and recommends nothing: every protocol constant is read from
``qecscreen.protocol`` as it stands.

**Paired design.** For each ``(p, code)`` cell the syndromes are sampled once,
from a stim sampler seeded with ``protocol.sampling_seed(code_id, h)`` where
``h`` is the pinned protocol's hash at that ``p``, and every decoder decodes
exactly the same shots, one shot at a time, all decoders per shot. A decoder
difference is then measured on shared noise: McNemar's exact test on the
shots where exactly one of the two decoders fails.

**Limits.** A cell stops when every decoder has ``MIN_FAILURES`` failures, at
``max_shots``, or at the wall-clock cap (checked between shots), and records
which. Every cell runs in its own worker process, at most ``processes`` at a
time, and a worker still alive ``cap + cell_kill_margin_seconds`` after it
started is killed: a hang inside ``decode()`` cannot be interrupted by the
between-shot cap. The killed cell's file has ``status: "killed"`` and the
sampling seed, batch, shot and decoder that were running, so the syndrome can
be reproduced locally, plus the partial tally the worker last flushed. Resume
treats it as done and never retries it: the same seed would hang again.
Before any sampling the run prints an upper bound on its wall time,
``ceil(cells / processes) * (cap + margin)``, and refuses to start if that
exceeds ``max_hours``: no cell outlives its kill deadline, so list
scheduling cannot take longer.

**Not dataset rows.** Every file written has ``"calibration": true``; the
output directory may not be under a directory named ``data``; and
``qecscreen.evaluate.rows.reject_calibration`` refuses all of it. One result
file per cell; on restart, completed cells are skipped.

``code_id`` follows CONTRACT's ``{program_id}-{sha256(params_json)[:12]}``
with ``params_json`` the canonical (sorted keys, no whitespace) JSON of ``l``,
``m``, ``a_exps`` and ``b_exps``. The dataset's own ``code_id`` function does
not exist yet (M0-RUN-01); if it canonicalises differently, calibration and
pilot ids for the same code will differ, which affects nothing here.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import multiprocessing
import multiprocessing.connection
import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from ldpc import BpLsdDecoder
from scipy.stats import binomtest

from qecscreen.circuits.build import build_memory_circuit
from qecscreen.codes.bb import generate
from qecscreen.codes.distance import estimate_d_upper
from qecscreen.codes.sample import sample_bb_params
from qecscreen.codes.validate import validate
from qecscreen.evaluate.label import make_label
from qecscreen.evaluate.rows import CALIBRATION_MARKER
from qecscreen.evaluate.run import (
    _BPOSD_KWARGS,
    CompiledBpOsd,
    dem_matrices,
    detector_error_model,
)
from qecscreen.protocol import (
    MAX_SHOTS,
    MIN_FAILURES,
    SHOT_BATCH,
    Protocol,
    installed_decoder_version,
    protocol_hash,
    sampling_seed,
    wilson_interval,
)
from qecscreen.provenance import record

__all__ = [
    "CALIBRATION_CODE_SEED",
    "DECODERS",
    "DEFAULT_PS",
    "REFERENCE_CODES",
    "CalibrationConfig",
    "code_id",
    "select_spanning",
    "calibration_codes",
    "mcnemar_exact",
    "run_cell",
    "run_calibration",
    "summarize",
    "format_summary",
]

# Seed for drawing the six sampled calibration codes and the 300-code
# population the pilot projection is made over. Chosen to be a value no pilot
# run uses (every seed in the tests and decisions so far is < 10): M0-RUN-01
# must not draw its codes with it, so that the pilot is not tuned on its own
# codes.
CALIBRATION_CODE_SEED = 20260926

DEFAULT_PS = (0.001, 0.0015, 0.002, 0.003)

_SYM_3_3 = {"a_exps": [[3, 0], [0, 1], [0, 2]], "b_exps": [[0, 3], [1, 0], [2, 0]]}
REFERENCE_CODES = {
    "ref72": {"construction_program_id": "bb_v1_sym_3_3", "l": 6, "m": 6, **_SYM_3_3},
    "gross144": {"construction_program_id": "bb_v1_sym_3_3", "l": 12, "m": 6, **_SYM_3_3},
}

# BP settings shared by every decoder: the pinned ones, exactly.
_BP_KWARGS = {k: _BPOSD_KWARGS[k] for k in ("bp_method", "max_iter", "ms_scaling_factor", "schedule")}

# name -> (ldpc class name, every keyword it is constructed with). BP+OSD is
# the pinned label-path decoder, built by run.CompiledBpOsd itself. The two
# LSD variants differ from it only in the post-processor and from each other
# only in lsd_order.
DECODERS: dict[str, tuple[str, dict[str, Any]]] = {
    "bposd": ("BpOsdDecoder", dict(_BPOSD_KWARGS)),
    "bplsd_cs_0": ("BpLsdDecoder", {**_BP_KWARGS, "lsd_method": "lsd_cs", "lsd_order": 0}),
    "bplsd_cs_4": ("BpLsdDecoder", {**_BP_KWARGS, "lsd_method": "lsd_cs", "lsd_order": 4}),
}
_REFERENCE_DECODER = "bposd"

_PLAN_FILE = "plan.json"
_SUMMARY_FILE = "summary.json"
_FORMAT = "qecscreen_decoder_calibration_v1"


@dataclasses.dataclass(frozen=True)
class CalibrationConfig:
    """Everything a calibration run depends on. Defaults are the full grid.

    Shrink the grid with ``ps``, ``decoders``, ``reference_codes`` and
    ``n_sampled_codes``; ``codes`` adds explicit BB parameter mappings
    (``l``, ``m``, ``a_exps``, ``b_exps``, optionally
    ``construction_program_id``). ``population_size`` codes are drawn with
    ``code_seed`` at ``budget``; the ``n_sampled_codes`` calibration codes are
    chosen from them to span their ``d_upper`` range, and the pilot projection
    is made over all of them (0 skips both). ``budget = 150`` is the budget
    every M0 measurement so far has used; it is not a pinned value.
    """

    ps: tuple[float, ...] = DEFAULT_PS
    decoders: tuple[str, ...] = tuple(DECODERS)
    reference_codes: bool = True
    n_sampled_codes: int = 6
    population_size: int = 300
    budget: int = 150
    code_seed: int = CALIBRATION_CODE_SEED
    codes: tuple[Mapping[str, Any], ...] = ()
    cell_wall_seconds: float = 1200.0
    # Hard kill at cell_wall_seconds + this, counted from the worker's start.
    # Covers the cap's overrun of one shot per decoder (~1 min on the largest
    # code, from AGENT_LOG (mm)'s cost fit) and the worker's imports; small
    # enough that the default grid's bound, 8 x 22 min, stays under 3 h.
    cell_kill_margin_seconds: float = 120.0
    max_shots: int = MAX_SHOTS
    sample_batch: int = 256
    processes: int = 4
    max_hours: float = 3.0

    def __post_init__(self) -> None:
        if not self.ps or any(not 0.0 < p < 1.0 for p in self.ps) or len(set(self.ps)) != len(self.ps):
            raise ValueError(f"ps must be distinct values in (0, 1); got {self.ps!r}")
        if not self.decoders or len(set(self.decoders)) != len(self.decoders):
            raise ValueError(f"decoders must be distinct and non-empty; got {self.decoders!r}")
        unknown = set(self.decoders) - set(DECODERS)
        if unknown:
            raise ValueError(f"unknown decoders {sorted(unknown)}; known: {sorted(DECODERS)}")
        if not 0 <= self.n_sampled_codes <= self.population_size:
            raise ValueError("n_sampled_codes must be in [0, population_size]")
        if not 0 < self.max_shots <= MAX_SHOTS:
            raise ValueError(f"max_shots must be in (0, MAX_SHOTS={MAX_SHOTS}]")
        if self.sample_batch < 1 or self.processes < 1:
            raise ValueError("sample_batch and processes must be >= 1")
        if min(self.cell_wall_seconds, self.cell_kill_margin_seconds, self.max_hours) <= 0:
            raise ValueError("cell_wall_seconds, cell_kill_margin_seconds and max_hours must be > 0")

    def to_json(self) -> dict[str, Any]:
        return json.loads(json.dumps(dataclasses.asdict(self)))


def code_id(construction_program_id: str, l: int, m: int, a_exps, b_exps) -> str:
    """``{program_id}-{sha256(params_json)[:12]}`` (CONTRACT, IDs)."""
    params = {
        "a_exps": [list(map(int, e)) for e in a_exps],
        "b_exps": [list(map(int, e)) for e in b_exps],
        "l": int(l),
        "m": int(m),
    }
    params_json = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return f"{construction_program_id}-{hashlib.sha256(params_json.encode('utf-8')).hexdigest()[:12]}"


def _describe(params: Mapping[str, Any], name: str | None = None) -> dict[str, Any]:
    """A code record: parameters, ``code_id``, ``n``, ``k`` and ``d_upper`` (seed 0)."""
    l, m = int(params["l"]), int(params["m"])
    a_exps = [list(map(int, e)) for e in params["a_exps"]]
    b_exps = [list(map(int, e)) for e in params["b_exps"]]
    pid = params.get("construction_program_id", "bb_v1_explicit")
    h_x, h_z = generate(l, m, [tuple(e) for e in a_exps], [tuple(e) for e in b_exps], seed=0)
    n, k = validate(h_x, h_z)
    d_upper, _ = estimate_d_upper(h_x, h_z, seed=0)
    cid = code_id(pid, l, m, a_exps, b_exps)
    return {
        "name": name or cid,
        "code_id": cid,
        "construction_program_id": pid,
        "l": l,
        "m": m,
        "a_exps": a_exps,
        "b_exps": b_exps,
        "n": int(n),
        "k": int(k),
        "d_upper": int(d_upper),
    }


def select_spanning(candidates: Sequence[Mapping[str, Any]], count: int) -> list[Mapping[str, Any]]:
    """``count`` candidates spanning the ``d_upper`` range, deterministically.

    Targets are ``count`` values evenly spaced from the smallest to the
    largest ``d_upper``; each target takes the unused candidate nearest to
    it, ties broken by ``n`` then ``code_id``. The extremes are always
    included when ``count >= 2``.
    """
    if count > len(candidates):
        raise ValueError(f"cannot choose {count} from {len(candidates)} candidates")
    if count == 0:
        return []
    pool = sorted(candidates, key=lambda c: (c["d_upper"], c["n"], c["code_id"]))
    lo, hi = pool[0]["d_upper"], pool[-1]["d_upper"]
    targets = [lo] if count == 1 else [lo + (hi - lo) * i / (count - 1) for i in range(count)]
    chosen: list[Mapping[str, Any]] = []
    used: set[str] = set()
    for t in targets:
        best = min(
            (c for c in pool if c["code_id"] not in used),
            key=lambda c: (abs(c["d_upper"] - t), c["n"], c["code_id"]),
        )
        chosen.append(best)
        used.add(best["code_id"])
    return chosen


def calibration_codes(config: CalibrationConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(codes to calibrate on, pilot-projection population)`` for ``config``."""
    codes: list[dict[str, Any]] = []
    if config.reference_codes:
        codes += [_describe(p, name) for name, p in REFERENCE_CODES.items()]
    population: list[dict[str, Any]] = []
    if config.population_size:
        drawn = sample_bb_params(config.population_size, config.budget, seed=config.code_seed)
        population = [_describe(p) for p in drawn]
        taken = {c["code_id"] for c in codes}
        pool = [c for c in population if c["code_id"] not in taken]
        codes += [dict(c) for c in select_spanning(pool, config.n_sampled_codes)]
    codes += [_describe(p) for p in config.codes]
    ids = [c["code_id"] for c in codes]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate calibration codes: {ids}")
    return codes, population


# --- one cell ---------------------------------------------------------------


def _make_decoder(name: str, dem, mats):
    cls, kwargs = DECODERS[name]
    if cls == "BpOsdDecoder":
        compiled = CompiledBpOsd(dem)  # the label path's decoder, guard included
        return compiled.decoder
    return BpLsdDecoder(mats.check_matrix, error_channel=mats.priors.tolist(), **kwargs)


def _ler_fields(p: float, rounds: int, k: int, shots: int, failures: int) -> dict[str, Any]:
    """INV-4 rate and Wilson interval via ``make_label`` (INV-3 censoring kept)."""
    if shots == 0:
        return {"censored": True, "ler": None, "ler_ci_low": None, "ler_ci_high": None}
    if failures == shots:  # the per-round rate is undefined (N-05)
        return {"censored": False, "ler": None, "ler_ci_low": None, "ler_ci_high": None,
                "all_shots_failed": True}
    lab = make_label(p=p, rounds=rounds, k=k, shots=shots, failures=failures, decode_seconds=0.0)
    return {"censored": lab.censored, "ler": lab.true_ler,
            "ler_ci_low": lab.true_ler_ci_low, "ler_ci_high": lab.true_ler_ci_high}


def mcnemar_exact(only_a_fails: int, only_b_fails: int) -> float:
    """Two-sided exact McNemar p-value on the discordant pairs."""
    n = only_a_fails + only_b_fails
    return 1.0 if n == 0 else float(binomtest(only_a_fails, n, 0.5).pvalue)


def _tally(
    decoders: Sequence[str],
    p: float,
    rounds: int,
    k: int,
    shots: int,
    fails: Mapping[str, list[bool]],
    seconds: Mapping[str, float],
    converged: Mapping[str, int],
    digests: Mapping[str, Any],
) -> dict[str, Any]:
    """Per-decoder results and paired comparisons over the first ``shots`` shots."""
    per_decoder = {}
    for name in decoders:
        f = int(sum(fails[name]))
        per_decoder[name] = {
            "ldpc_class": DECODERS[name][0],
            "params": DECODERS[name][1],
            "failures": f,
            **_ler_fields(p, rounds, k, shots, f),
            "decode_seconds": seconds[name],
            "ms_per_shot": 1000.0 * seconds[name] / shots if shots else None,
            "bp_converged": converged[name],
            "bp_convergence_fraction": converged[name] / shots if shots else None,
            "syndromes_sha256": digests[name].hexdigest(),
        }

    paired = {}
    if _REFERENCE_DECODER in decoders:
        ref = np.array(fails[_REFERENCE_DECODER], dtype=bool)
        for name in decoders:
            if name == _REFERENCE_DECODER:
                continue
            other = np.array(fails[name], dtype=bool)
            only_ref, only_other = int((ref & ~other).sum()), int((~ref & other).sum())
            paired[f"{name}_vs_{_REFERENCE_DECODER}"] = {
                f"only_{_REFERENCE_DECODER}_fails": only_ref,
                f"only_{name}_fails": only_other,
                "both_fail": int((ref & other).sum()),
                "neither_fails": int((~ref & ~other).sum()),
                "mcnemar_exact_p": mcnemar_exact(only_ref, only_other),
            }
    return {"shots": shots, "decoders": per_decoder, "paired": paired}


# Besides every batch end, a worker flushes its partial tally this often, so a
# killed cell keeps most of what it decoded even when one batch outlasts the
# cap (the largest codes decode a few dozen shots per cell).
_FLUSH_SECONDS = 30.0


def run_cell(
    code: Mapping[str, Any],
    p: float,
    decoders: Sequence[str],
    *,
    wall_seconds: float,
    max_shots: int,
    sample_batch: int,
    progress: Any = None,
    partial_path: str | os.PathLike | None = None,
    decoder_factory: Any = None,
) -> dict[str, Any]:
    """Sample one ``(p, code)`` cell once and decode every shot with every decoder.

    ``progress``, if given, is a 3-slot integer array that receives ``(batch
    index, shot index within the batch, decoder index)`` before every
    ``decode()`` call, so the parent can say what was running if it has to
    kill this process. ``partial_path``, if given, receives the tally over
    every shot completed so far (all decoders done on it) at each batch end
    and every ``_FLUSH_SECONDS``. ``decoder_factory(name, dem, mats)``
    replaces ``_make_decoder``; it exists for tests.
    """
    make_decoder = decoder_factory or _make_decoder
    start = time.monotonic()
    rounds = int(code["d_upper"])
    circuit = build_memory_circuit(code, p, rounds)
    dem = detector_error_model(circuit)
    mats = dem_matrices(dem)
    obs_matrix = mats.observables_matrix
    h = protocol_hash(Protocol(p=p, decoder_version=installed_decoder_version()))
    seed = sampling_seed(code["code_id"], h)
    decs = {name: make_decoder(name, dem, mats) for name in decoders}
    setup_seconds = time.monotonic() - start

    k = circuit.num_observables
    fails: dict[str, list[bool]] = {name: [] for name in decoders}
    n_fails = dict.fromkeys(decoders, 0)
    seconds = dict.fromkeys(decoders, 0.0)
    converged = dict.fromkeys(decoders, 0)
    digests = {name: hashlib.sha256() for name in decoders}
    samples = hashlib.sha256()
    sampler = circuit.compile_detector_sampler(seed=seed)
    shots = 0
    stopped_by = None
    batch_index = -1
    last_flush = time.monotonic()

    def flush() -> None:
        if partial_path is not None:
            _write_json(Path(partial_path), {
                CALIBRATION_MARKER: True, "format": _FORMAT, "status": "partial",
                **_tally(decoders, p, rounds, k, shots, fails, seconds, converged, digests),
            })

    while stopped_by is None:
        dets, obs = sampler.sample(sample_batch, separate_observables=True)
        batch_index += 1
        rows = zip(dets.astype(np.uint8), obs.astype(np.uint8))
        for shot_in_batch, (syndrome, actual) in enumerate(rows):
            if all(f >= MIN_FAILURES for f in n_fails.values()):
                stopped_by = "min_failures"
            elif shots >= max_shots:
                stopped_by = "max_shots"
            elif time.monotonic() - start >= wall_seconds:
                stopped_by = "wall_clock"
            if stopped_by:
                break
            if time.monotonic() - last_flush >= _FLUSH_SECONDS:
                flush()
                last_flush = time.monotonic()
            samples.update(syndrome.tobytes())
            samples.update(actual.tobytes())
            for i, (name, dec) in enumerate(decs.items()):
                if progress is not None:
                    progress[0], progress[1], progress[2] = batch_index, shot_in_batch, i
                digests[name].update(syndrome.tobytes())
                t = time.perf_counter()
                correction = dec.decode(syndrome)
                seconds[name] += time.perf_counter() - t
                converged[name] += bool(dec.converge)
                failed = bool(((obs_matrix @ correction) % 2 != actual).any())
                fails[name].append(failed)
                n_fails[name] += failed
            shots += 1
        else:
            flush()
            last_flush = time.monotonic()

    return {
        CALIBRATION_MARKER: True,
        "format": _FORMAT,
        "status": "completed",
        "p": p,
        "code": dict(code),
        "rounds": rounds,
        "num_detectors": dem.num_detectors,
        "num_mechanisms": int(mats.priors.size),
        "protocol_hash_pinned": h,
        "sampling_seed": seed,
        "sample_batch": sample_batch,
        "stopped_by": stopped_by,
        "wall_seconds": time.monotonic() - start,
        "setup_seconds": setup_seconds,
        "samples_sha256": samples.hexdigest(),
        **_tally(decoders, p, rounds, k, shots, fails, seconds, converged, digests),
        "provenance": record(),
    }


def _cell_path(out_dir: Path, p: float, cid: str) -> Path:
    return out_dir / f"cell_p{p:.6f}_{cid}.json"


def _partial_path(out_dir: Path, p: float, cid: str) -> Path:
    return out_dir / f"partial_p{p:.6f}_{cid}.json"


def _write_json(path: Path, obj: Mapping[str, Any]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _cell_worker(job: Mapping[str, Any], progress: Any) -> None:
    """Worker process entry point: run one cell and write its file."""
    result = run_cell(
        job["code"], job["p"], job["decoders"], wall_seconds=job["wall_seconds"],
        max_shots=job["max_shots"], sample_batch=job["sample_batch"], progress=progress,
        partial_path=job["partial_path"], decoder_factory=job["decoder_factory"],
    )
    _write_json(Path(job["path"]), result)


def _start_worker(ctx: Any, job: Mapping[str, Any], progress: Any) -> Any:
    """Start one cell's worker process. Separate so tests can see every start."""
    proc = ctx.Process(target=_cell_worker, args=(job, progress), daemon=True)
    proc.start()
    return proc


def _write_unfinished(job: Mapping[str, Any], status: str, progress: Any, **extra: Any) -> None:
    """The result file of a cell whose worker was killed (or died on its own).

    Records what reproduces the syndrome being decoded: the sampling seed and
    batch size, and the batch, shot and decoder from the shared progress
    array. Keeps the partial tally the worker last flushed, which covers shots
    ``0 .. partial.shots - 1`` with every decoder done on each; everything
    decoded after that flush is lost, including the shot that was running.
    """
    code, p = job["code"], job["p"]
    h = protocol_hash(Protocol(p=p, decoder_version=installed_decoder_version()))
    batch_index, shot_in_batch, decoder_index = (int(v) for v in progress[:3])
    started = batch_index >= 0  # False if the worker never reached a decode
    partial_file = Path(job["partial_path"])
    partial = json.loads(partial_file.read_text(encoding="utf-8")) if partial_file.exists() else None
    _write_json(Path(job["path"]), {
        CALIBRATION_MARKER: True,
        "format": _FORMAT,
        "status": status,
        "p": p,
        "code": dict(code),
        "rounds": int(code["d_upper"]),
        "protocol_hash_pinned": h,
        "sampling_seed": sampling_seed(code["code_id"], h),
        "sample_batch": job["sample_batch"],
        "batch_index": batch_index if started else None,
        "shot_in_batch": shot_in_batch if started else None,
        "shot_index": batch_index * job["sample_batch"] + shot_in_batch if started else None,
        "decoder": job["decoders"][decoder_index] if started else None,
        "reproduce": (
            "build_memory_circuit(code, p, rounds).compile_detector_sampler(seed=sampling_seed); "
            "call .sample(sample_batch, separate_observables=True) batch_index + 1 times; the "
            "syndrome is row shot_in_batch of the last call, as uint8"
        ),
        "partial": partial,
        "provenance": record(),
        **extra,
    })
    partial_file.unlink(missing_ok=True)


def _run_jobs(jobs: Sequence[Mapping[str, Any]], processes: int, kill_after: float) -> None:
    """Run every job in its own process, at most ``processes`` at once.

    A worker still alive ``kill_after`` seconds after it started is killed and
    its cell written as ``killed``; one that exits without writing its result
    is written as ``died``. Either way the run goes on to the next cell.
    """
    ctx = multiprocessing.get_context("spawn")  # no fork of a threaded kernel
    pending = list(jobs)
    running: dict[Any, tuple[Mapping[str, Any], Any, float, Any]] = {}
    while pending or running:
        while pending and len(running) < processes:
            job = pending.pop(0)
            progress = ctx.Array("q", [-1, -1, -1], lock=False)
            proc = _start_worker(ctx, job, progress)
            running[proc.sentinel] = (job, progress, time.monotonic() + kill_after, proc)
        timeout = max(0.0, min(r[2] for r in running.values()) - time.monotonic())
        multiprocessing.connection.wait(list(running), timeout=timeout)
        for sentinel, (job, progress, deadline, proc) in list(running.items()):
            name = Path(job["path"]).name
            if not proc.is_alive():
                proc.join()
                del running[sentinel]
                if proc.exitcode == 0 and Path(job["path"]).exists():
                    Path(job["partial_path"]).unlink(missing_ok=True)
                    print("done:", name, flush=True)
                else:
                    _write_unfinished(job, "died", progress, exitcode=proc.exitcode)
                    print(f"DIED (exit code {proc.exitcode}):", name, flush=True)
            elif time.monotonic() >= deadline:
                proc.kill()
                proc.join()
                del running[sentinel]
                _write_unfinished(job, "killed", progress, killed_after_seconds=kill_after)
                print(f"KILLED after {kill_after:.0f} s:", name, flush=True)


# --- the run ----------------------------------------------------------------


def _check_out_dir(out_dir: Path) -> Path:
    resolved = out_dir.resolve()
    if "data" in resolved.parts:
        raise ValueError(
            f"calibration output may not live under a directory named 'data' ({resolved}): "
            "data/ holds dataset rows, and calibration output is not dataset rows"
        )
    return resolved


def run_calibration(
    config: CalibrationConfig, out_dir: str | os.PathLike, *, _decoder_factory: Any = None
) -> dict[str, Any]:
    """Run (or resume) the calibration grid into ``out_dir``; return the summary.

    Writes ``plan.json`` (config and code ids), one ``cell_*.json`` per
    ``(p, code)``, and ``summary.json``. A restart with the same config skips
    every cell whose file exists, ``killed`` and ``died`` ones included; a
    different config refuses to reuse the directory. Raises before any
    sampling if the projected wall time exceeds ``config.max_hours``.
    ``_decoder_factory`` is a test seam handed to ``run_cell`` in each worker;
    it must be picklable.
    """
    out = _check_out_dir(Path(out_dir))
    out.mkdir(parents=True, exist_ok=True)

    codes, population = calibration_codes(config)
    plan = {
        CALIBRATION_MARKER: True,
        "format": _FORMAT,
        "config": config.to_json(),
        "codes": codes,
        "population": [
            {key: c[key] for key in ("code_id", "construction_program_id", "n", "k", "d_upper")}
            for c in population
        ],
        "provenance": record(),
    }
    plan_path = out / _PLAN_FILE
    if plan_path.exists():
        old = json.loads(plan_path.read_text(encoding="utf-8"))
        ignore = ("processes", "max_hours")
        same = {k: v for k, v in old.get("config", {}).items() if k not in ignore} == {
            k: v for k, v in plan["config"].items() if k not in ignore
        } and old.get("codes") == plan["codes"] and old.get("population") == plan["population"]
        if not old.get(CALIBRATION_MARKER) or not same:
            raise ValueError(f"{out} holds a different calibration run; use a new out_dir")
    else:
        _write_json(plan_path, plan)

    print("calibration codes:")
    for c in codes:
        print(f"  {c['name']:>9}  {c['code_id']}  [[{c['n']},{c['k']},<={c['d_upper']}]]")

    cells = [(p, c) for p in config.ps for c in codes]
    todo = [(p, c) for p, c in cells if not _cell_path(out, p, c["code_id"]).exists()]
    kill_after = config.cell_wall_seconds + config.cell_kill_margin_seconds
    bound_h = math.ceil(len(todo) / config.processes) * kill_after / 3600.0
    print(
        f"{len(cells)} cells, {len(cells) - len(todo)} already done (killed ones included, "
        f"never retried), {len(todo)} to run on {config.processes} processes, each capped at "
        f"{config.cell_wall_seconds / 60:.1f} min and killed at {kill_after / 60:.1f} min.\n"
        f"projected wall time <= {bound_h:.2f} h (<= {bound_h * config.processes:.1f} core-hours); "
        f"limit {config.max_hours:.2f} h"
    )
    if bound_h > config.max_hours:
        raise RuntimeError(
            f"projected {bound_h:.2f} h exceeds max_hours={config.max_hours}; shrink the grid "
            "(ps, decoders, codes) or the cell cap before starting (AGENTS.md §7)"
        )

    # Largest circuits first, so the long cells do not all land at the end.
    todo.sort(key=lambda pc: -pc[1]["n"] * pc[1]["d_upper"])
    jobs = [
        {"code": c, "p": p, "decoders": tuple(config.decoders),
         "wall_seconds": config.cell_wall_seconds, "max_shots": config.max_shots,
         "sample_batch": config.sample_batch, "decoder_factory": _decoder_factory,
         "path": str(_cell_path(out, p, c["code_id"])),
         "partial_path": str(_partial_path(out, p, c["code_id"]))}
        for p, c in todo
    ]
    _run_jobs(jobs, config.processes, kill_after)

    summary = summarize(out)
    _write_json(out / _SUMMARY_FILE, summary)
    print(format_summary(summary))
    return summary


# --- summary ----------------------------------------------------------------


def _load_cells(out: Path, plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    cfg = plan["config"]
    cells = []
    for p in cfg["ps"]:
        for c in plan["codes"]:
            path = _cell_path(out, p, c["code_id"])
            if not path.exists():
                continue
            cell = json.loads(path.read_text(encoding="utf-8"))
            decs = cell["decoders"] if cell.get("status") == "completed" else cfg["decoders"]
            if (not cell.get(CALIBRATION_MARKER) or cell["p"] != p
                    or cell["code"]["code_id"] != c["code_id"]
                    or sorted(decs) != sorted(cfg["decoders"])):
                raise ValueError(f"{path} does not belong to this calibration run")
            cells.append(cell)
    return cells


def _shots_needed(shots: int, failures: int) -> dict[str, Any]:
    """Estimated shots to ``MIN_FAILURES`` at this cell's failure fraction."""
    if shots == 0:
        return {"estimate": None, "range": [None, None], "exceeds_max_shots": None}
    lo, hi = wilson_interval(failures, shots)
    rng = [math.ceil(MIN_FAILURES / hi), math.ceil(MIN_FAILURES / lo) if lo > 0 else None]
    if failures:
        est = math.ceil(MIN_FAILURES * shots / failures)
        exceeds: bool | None = est > MAX_SHOTS
    else:
        est = None
        exceeds = True if rng[0] > MAX_SHOTS else None
    return {"estimate": est, "range": rng, "exceeds_max_shots": exceeds}


def _run_shots(needed: int | None, exceeds: bool | None) -> tuple[int, int]:
    """Shots a label run would take: (at ``SHOT_BATCH`` granularity, unbatched).

    Unknown (no failures, not provably censored) and censored are costed at
    ``MAX_SHOTS``.
    """
    if needed is None or exceeds:
        return MAX_SHOTS, MAX_SHOTS
    return min(math.ceil(needed / SHOT_BATCH) * SHOT_BATCH, MAX_SHOTS), min(needed, MAX_SHOTS)


def _separated(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool | None:
    if a["ler_ci_low"] is None or b["ler_ci_low"] is None:
        return None
    return a["ler_ci_high"] < b["ler_ci_low"] or b["ler_ci_high"] < a["ler_ci_low"]


def _project_pilot(
    cells: Sequence[Mapping[str, Any]], population: Sequence[Mapping[str, Any]], decoder: str
) -> dict[str, Any] | None:
    """Core-hours and censoring for ``population`` from one ``(p, decoder)``'s cells.

    Seconds per shot: least-squares power law in ``n * d_upper`` (~detectors)
    over the calibration codes. Failure fraction: the calibration code nearest
    in ``d_upper``, then ``n``. Both are extrapolations from a handful of
    codes, reported as such.
    """
    obs = [c for c in cells if c["shots"] > 0]
    if not obs or not population:
        return None
    size = np.array([c["code"]["n"] * c["rounds"] for c in obs], dtype=float)
    sec = np.array([c["decoders"][decoder]["decode_seconds"] / c["shots"] for c in obs])
    if len(set(size)) >= 2 and (sec > 0).all():
        slope, icept = np.polyfit(np.log(size), np.log(sec), 1)
    else:
        slope, icept = 0.0, float(np.log(max(sec.mean(), 1e-12)))

    per_code = []
    for code in population:
        near = min(obs, key=lambda c: (abs(c["code"]["d_upper"] - code["d_upper"]),
                                       abs(c["code"]["n"] - code["n"]), c["code"]["code_id"]))
        need = _shots_needed(near["shots"], near["decoders"][decoder]["failures"])
        batched, unbatched = _run_shots(need["estimate"], need["exceeds_max_shots"])
        s = float(np.exp(icept + slope * np.log(code["n"] * code["d_upper"])))
        per_code.append((code, need["exceeds_max_shots"], batched * s, unbatched * s))

    top = sorted(per_code, key=lambda r: (-r[0]["d_upper"], -r[0]["n"], r[0]["code_id"]))
    top = top[: math.ceil(len(top) / 3)]
    n_cens = sum(r[1] is True for r in top)
    n_unknown = sum(r[1] is None for r in top)
    core_h = sum(r[2] for r in per_code) / 3600.0
    return {
        "population_codes": len(per_code),
        "core_hours": core_h,
        "core_hours_unbatched": sum(r[3] for r in per_code) / 3600.0,
        "unknown_costed_at_max_shots": sum(r[1] is None for r in per_code),
        "top_third_by_d_upper": {
            "codes": len(top),
            "d_upper_min": min(r[0]["d_upper"] for r in top),
            "projected_censored": n_cens,
            "projected_not_censored": len(top) - n_cens - n_unknown,
            "unknown": n_unknown,
            "censored_fraction": n_cens / len(top),
        },
        "seconds_per_shot_model": {"form": "exp(a + b*log(n*d_upper))", "a": float(icept),
                                   "b": float(slope), "fit_codes": len(obs)},
        "failure_fraction_model": "nearest calibration code in d_upper, then n",
    }


def summarize(out_dir: str | os.PathLike) -> dict[str, Any]:
    """Summary of a calibration directory: measurements and projections, no advice."""
    out = Path(out_dir)
    plan = json.loads((out / _PLAN_FILE).read_text(encoding="utf-8"))
    loaded = _load_cells(out, plan)
    # Killed or died cells are listed with what reproduces the syndrome and the
    # partial tally they kept; they take no part in the comparisons below.
    cells = [c for c in loaded if c["status"] == "completed"]
    unfinished = [
        {key: c[key] for key in ("status", "p", "sampling_seed", "sample_batch", "batch_index",
                                 "shot_in_batch", "shot_index", "decoder", "partial")}
        | {"code_id": c["code"]["code_id"], "name": c["code"]["name"]}
        for c in loaded if c["status"] != "completed"
    ]
    decoders = plan["config"]["decoders"]

    size_scaling = []
    for p in plan["config"]["ps"]:
        by_name = {c["code"]["name"]: c for c in cells if c["p"] == p}
        if "ref72" in by_name and "gross144" in by_name:
            for d in decoders:
                a, b = by_name["ref72"]["decoders"][d], by_name["gross144"]["decoders"][d]
                size_scaling.append({
                    "p": p, "decoder": d,
                    "ref72": {k: a[k] for k in ("failures", "ler", "ler_ci_low", "ler_ci_high")}
                    | {"shots": by_name["ref72"]["shots"]},
                    "gross144": {k: b[k] for k in ("failures", "ler", "ler_ci_low", "ler_ci_high")}
                    | {"shots": by_name["gross144"]["shots"]},
                    "intervals_separate": _separated(a, b),
                })

    per_cell = []
    for c in cells:
        entry = {"p": c["p"], "code_id": c["code"]["code_id"], "name": c["code"]["name"],
                 "n": c["code"]["n"], "k": c["code"]["k"], "d_upper": c["code"]["d_upper"],
                 "shots": c["shots"], "stopped_by": c["stopped_by"], "decoders": {}}
        for d in decoders:
            r = c["decoders"][d]
            need = _shots_needed(c["shots"], r["failures"])
            batched, unbatched = _run_shots(need["estimate"], need["exceeds_max_shots"])
            sec = r["decode_seconds"] / c["shots"] if c["shots"] else None
            entry["decoders"][d] = {
                "failures": r["failures"], "ler": r["ler"],
                "ler_ci": [r["ler_ci_low"], r["ler_ci_high"]],
                "ms_per_shot": r["ms_per_shot"],
                "bp_convergence_fraction": r["bp_convergence_fraction"],
                "shots_to_min_failures": need,
                "core_hours": None if sec is None else batched * sec / 3600.0,
                "core_hours_unbatched": None if sec is None else unbatched * sec / 3600.0,
            }
        entry["paired"] = c["paired"]
        per_cell.append(entry)

    pilot = []
    for p in plan["config"]["ps"]:
        for d in decoders:
            proj = _project_pilot([c for c in cells if c["p"] == p], plan["population"], d)
            if proj is not None:
                pilot.append({"p": p, "decoder": d, **proj})

    return {
        CALIBRATION_MARKER: True,
        "format": _FORMAT,
        "constants_used": {"MIN_FAILURES": MIN_FAILURES, "MAX_SHOTS": MAX_SHOTS,
                           "SHOT_BATCH": SHOT_BATCH},
        "code_ids": {c["name"]: c["code_id"] for c in plan["codes"]},
        "cells_done": len(loaded),
        "cells_total": len(plan["config"]["ps"]) * len(plan["codes"]),
        "stopped_by": {s: sum(c["stopped_by"] == s for c in cells)
                       for s in ("min_failures", "max_shots", "wall_clock")}
        | {s: sum(c["status"] == s for c in loaded) for s in ("killed", "died")},
        "unfinished_cells": unfinished,
        "size_scaling": size_scaling,
        "per_cell": per_cell,
        "pilot_projection": pilot,
    }


def _fmt(x: float | None, spec: str = ".2e") -> str:
    return "-" if x is None else format(x, spec)


def format_summary(summary: Mapping[str, Any]) -> str:
    """The summary as text, for printing. Measurements and projections only."""
    lines = [f"cells {summary['cells_done']}/{summary['cells_total']}, "
             f"stopped by {summary['stopped_by']}"]
    for u in summary["unfinished_cells"]:
        kept = u["partial"]["shots"] if u["partial"] else 0
        lines.append(
            f"  {u['status'].upper()}: p={u['p']} {u['code_id']} sampling_seed={u['sampling_seed']} "
            f"batch={u['batch_index']} shot_in_batch={u['shot_in_batch']} (shot {u['shot_index']}) "
            f"decoder={u['decoder']}; partial kept: {kept} shots"
        )
    lines.append("\nsize scaling (per-round LER, 95% Wilson):")
    for s in summary["size_scaling"]:
        a, b = s["ref72"], s["gross144"]
        lines.append(
            f"  p={s['p']:<7} {s['decoder']:<11} [[72]] {a['failures']}/{a['shots']} "
            f"[{_fmt(a['ler_ci_low'])}, {_fmt(a['ler_ci_high'])}]  gross {b['failures']}/{b['shots']} "
            f"[{_fmt(b['ler_ci_low'])}, {_fmt(b['ler_ci_high'])}]  separate={s['intervals_separate']}"
        )
    lines.append("\nper cell:")
    for c in summary["per_cell"]:
        lines.append(f"  p={c['p']:<7} {c['name'][:28]:<28} [[{c['n']},{c['k']},<={c['d_upper']}]] "
                     f"shots={c['shots']} ({c['stopped_by']})")
        for d, r in c["decoders"].items():
            need = r["shots_to_min_failures"]
            lines.append(
                f"      {d:<11} fail={r['failures']:<5} ms/shot={_fmt(r['ms_per_shot'], '.1f'):<8} "
                f"bp_conv={_fmt(r['bp_convergence_fraction'], '.2f'):<5} "
                f"shots_to_100={need['estimate']} range={need['range']} "
                f">MAX_SHOTS={need['exceeds_max_shots']} core_h={_fmt(r['core_hours'], '.3g')}"
            )
        for k, v in c["paired"].items():
            lines.append(f"      {k}: {v}")
    lines.append("\n300-code pilot projection (per p, decoder):")
    for pr in summary["pilot_projection"]:
        t = pr["top_third_by_d_upper"]
        lines.append(
            f"  p={pr['p']:<7} {pr['decoder']:<11} core_h={pr['core_hours']:.1f} "
            f"(unbatched {pr['core_hours_unbatched']:.1f}, {pr['unknown_costed_at_max_shots']} at MAX_SHOTS) "
            f"top-third censored {t['projected_censored']}/{t['codes']} (+{t['unknown']} unknown)"
        )
    return "\n".join(lines)
