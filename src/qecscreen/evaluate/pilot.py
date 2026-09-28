"""M0-RUN-01: the M0 pilot, run as a chain of Kaggle sessions (D-031, D-032, D-033).

The pilot labels every code of the M0 population (``m0_population()``: the 244
admissible BB codes at n <= 72, enumerated) at ``P_PILOT`` with the pinned
BP+OSD. One Kaggle session cannot do it, so the work is cumulative across
sessions. **All of it lives in one pilot directory:**

- ``manifest.json``: what every session must agree on (``MANIFEST_KEYS``);
- ``population.parquet``: the population, with ``n``, ``k``, ``d_upper`` and
  ``n_d_upper`` (``n * d_upper``);
- one checkpoint directory per ``code_id`` (``qecscreen.evaluate.checkpoint``);
- ``stale/``: partial checkpoints that could not be continued, moved aside,
  never deleted;
- one ``session_NNN.json`` summary per session.

**Session start** (``run_session``). With ``previous`` (a notebook's earlier
output, attached under ``/kaggle/input``), the one pilot directory under it
is copied verbatim into ``out_dir`` and checked file by file, and against the
file inventory the previous session recorded, so an output Kaggle truncated
is refused rather than resumed. The first session writes the manifest; every
later one refuses to start if the protocol hash, the installed ldpc or stim,
the commit or the population digest differ, and says which. The population is
enumerated every session and checked against ``POPULATION_SIZE`` and
``POPULATION_SHA256``, pinned here, so a change to enumeration fails loudly.

**Scheduling.** One spawned worker per code, ``processes`` at a time, longest
first by ``n * d_upper``. Each runs ``sample_and_decode`` with the code's
checkpoint directory and the session deadline, which it checks between
batches: it flushes its shard and exits cleanly, so the session ends before
Kaggle's limit rather than by being killed. No new worker starts after the
deadline. A partial code whose shards were written on another ``cpu_class``,
or whose re-drawn shots do not reproduce its digests (D-032), is moved to
``stale/<code_id>-<cpu_class>-<utc>/`` and restarted from batch 0. A worker
that dies is recorded with its exit code and retried in the next session;
a code that dies in two sessions is failed and not run again (AGENTS §4: two
failures, stop). A finished code is never re-run.

**Final assembly** (``assemble_measurements``) builds every row, checks one
protocol and all 244 rows, and writes ``data/m0_measurements.parquet``. It
refuses while any code is unfinished.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import multiprocessing
import multiprocessing.connection
import os
import shutil
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from qecscreen import provenance
from qecscreen.circuits.build import build_memory_circuit
from qecscreen.codes import ids
from qecscreen.codes.bb import generate
from qecscreen.codes.distance import estimate_d_upper
from qecscreen.codes.sample import admissible_codes
from qecscreen.codes.validate import validate
from qecscreen.evaluate.checkpoint import (
    RESULT_FILE,
    CodeCheckpoint,
    ProvenanceMismatchError,
    SampleDigestMismatchError,
)
from qecscreen.evaluate.rows import build_row, reject_calibration, rows_table
from qecscreen.evaluate.run import sample_and_decode
from qecscreen.protocol import (
    MAX_SHOTS,
    P_PILOT,
    SHOT_BATCH,
    Protocol,
    assert_single_protocol,
    protocol_hash,
    sampling_seed,
)

__all__ = [
    "BUDGET",
    "EXIT_STALE",
    "MANIFEST_KEYS",
    "MEASUREMENTS_FILE",
    "POPULATION_SHA256",
    "POPULATION_SIZE",
    "PROCESSES",
    "SESSION_WALL_HOURS",
    "PilotConfig",
    "PilotRefusal",
    "assemble_measurements",
    "locate_pilot",
    "m0_population",
    "population_digest",
    "run_session",
]

# D-031: M0's population is every admissible code at n <= 72.
BUDGET = 72
POPULATION_SIZE = 244
# population_digest(m0_population()). Pinned so that any change to the
# templates, the (l, m) grid, validate or estimate_d_upper fails loudly here.
POPULATION_SHA256 = "5008e14eb8292df8549aa5fddada442938ce52f91950e4612dfbb85dc6e3d94f"

PROCESSES = 4  # Kaggle's 4 cores, one code per process (D-026)
SESSION_WALL_HOURS = 10.5  # owner, 2026-09-28 (D-033): under Kaggle's 12 h, with margin

MEASUREMENTS_FILE = "m0_measurements.parquet"  # owner, 2026-09-28, under data/ (architecture §2)
MANIFEST_FILE = "manifest.json"
POPULATION_FILE = "population.parquet"
STALE_DIR = "stale"
FORMAT = "qecscreen_m0_pilot_v1"
EXIT_STALE = 75  # a worker's exit code for "this partial checkpoint cannot be continued"

# Every session must agree on these with the first (D-033).
MANIFEST_KEYS = ("protocol_hash", "decoder_version", "stim_version", "commit_sha",
                 "population_sha256", "p", "batch_size", "max_shots")

_POPULATION_KEYS = ("code_id", "construction_program_id", "params_json", "n", "k", "d_upper")
_POPULATION_SCHEMA = pa.schema([
    pa.field("code_id", pa.string()),
    pa.field("construction_program_id", pa.string()),
    pa.field("params_json", pa.string()),
    pa.field("n", pa.int64()),
    pa.field("k", pa.int64()),
    pa.field("d_upper", pa.int64()),
    pa.field("n_d_upper", pa.int64()),
])


class PilotRefusal(RuntimeError):
    """A session refuses to start, or assembly refuses to write."""


@dataclasses.dataclass(frozen=True)
class PilotConfig:
    """One session's settings. The notebook sets ``previous`` and nothing else.

    ``previous`` is ``None`` or a path (under ``/kaggle/input``) holding
    exactly one pilot directory. The underscored fields are for tests only:
    a small population, small batches, and a hook run first in each worker.
    """

    previous: str | None = None
    session_wall_hours: float = SESSION_WALL_HOURS
    processes: int = PROCESSES
    _population: tuple[Mapping[str, Any], ...] | None = None
    _batch_size: int = SHOT_BATCH
    _max_shots: int = MAX_SHOTS
    _worker_setup: Callable[[Mapping[str, Any]], None] | None = None

    def __post_init__(self) -> None:
        if self.session_wall_hours < 0 or self.processes < 1:
            raise ValueError("session_wall_hours must be >= 0 and processes >= 1")
        if not 0 < self._max_shots <= MAX_SHOTS or self._max_shots % self._batch_size:
            raise ValueError("max_shots must be a whole number of batches, at most MAX_SHOTS")


# --- population ---------------------------------------------------------------


def _record(params: Mapping[str, Any]) -> dict[str, Any]:
    pj = ids.params_json(params["l"], params["m"], params["a_exps"], params["b_exps"])
    rec = {"code_id": ids.code_id(params["construction_program_id"], pj),
           "construction_program_id": params["construction_program_id"], "params_json": pj}
    if {"n", "k", "d_upper"} <= set(params):
        n, k, d = params["n"], params["k"], params["d_upper"]
    else:
        h_x, h_z = generate(params["l"], params["m"], [tuple(e) for e in params["a_exps"]],
                            [tuple(e) for e in params["b_exps"]], seed=0)
        n, k = validate(h_x, h_z)
        d, _ = estimate_d_upper(h_x, h_z, seed=0)
    return {**rec, "n": int(n), "k": int(k), "d_upper": int(d), "n_d_upper": int(n) * int(d)}


def population_digest(records: Sequence[Mapping[str, Any]]) -> str:
    """sha256 of the population's canonical JSON, sorted by ``code_id``."""
    canon = sorted(({k: r[k] for k in _POPULATION_KEYS} for r in records), key=lambda r: r["code_id"])
    return hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def m0_population() -> list[dict[str, Any]]:
    """The M0 population (D-031), checked against ``POPULATION_SIZE`` and ``POPULATION_SHA256``."""
    records = [_record(p) for p in admissible_codes(BUDGET)]
    digest = population_digest(records)
    if len(records) != POPULATION_SIZE or digest != POPULATION_SHA256:
        raise PilotRefusal(
            f"the enumerated M0 population has {len(records)} codes and digest {digest}; pinned: "
            f"{POPULATION_SIZE} and {POPULATION_SHA256}. Enumeration changed (templates, (l, m) "
            "grid, validate or estimate_d_upper); the pilot cannot continue on another population"
        )
    return records


def _code(rec: Mapping[str, Any]) -> dict[str, Any]:
    """A population record as the mapping ``build_memory_circuit`` and ``build_row`` take."""
    return {**json.loads(rec["params_json"]), **{k: rec[k] for k in (
        "code_id", "construction_program_id", "n", "k", "d_upper")}}


def _read_population(pilot: Path) -> list[dict[str, Any]]:
    return pq.read_table(pilot / POPULATION_FILE).to_pylist()


# --- files --------------------------------------------------------------------


def _utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(root: Path) -> dict[str, str]:
    """Every file under ``root``: relative posix path -> sha256. ``.tmp`` files excluded."""
    return {p.relative_to(root).as_posix(): _sha256(p)
            for p in sorted(root.rglob("*")) if p.is_file() and not p.name.endswith(".tmp")}


def _write_json(path: Path, obj: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _summaries(pilot: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(pilot.glob("session_*.json"))]


def _is_pilot_manifest(path: Path) -> bool:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("format") == FORMAT
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return False


def locate_pilot(previous: str | os.PathLike[str]) -> Path:
    """The one pilot directory under ``previous``; refuses zero or several."""
    root = Path(previous)
    if not root.is_dir():
        raise PilotRefusal(f"PREVIOUS={root} is not a directory")
    found = sorted({m.parent for m in root.rglob(MANIFEST_FILE) if _is_pilot_manifest(m)})
    if len(found) != 1:
        raise PilotRefusal(
            f"PREVIOUS={root} holds {len(found)} pilot directories, not exactly one: "
            f"{[str(f) for f in found]}. Attach only the previous session's output"
        )
    return found[0]


def _copy_previous(previous: str, out: Path) -> Path:
    src = locate_pilot(previous)
    if out.exists() and any(out.iterdir()):
        raise PilotRefusal(
            f"OUT_DIR={out} is not empty; a session with PREVIOUS copies into an empty OUT_DIR. "
            "To continue in this same session, set PREVIOUS = None"
        )
    if out.resolve().is_relative_to(src.resolve()) or src.resolve().is_relative_to(out.resolve()):
        raise PilotRefusal(f"OUT_DIR={out} and the previous pilot {src} overlap")
    source = _files(src)
    summaries = _summaries(src)
    if summaries:  # what the previous session wrote, against what was attached
        missing = {p: h for p, h in summaries[-1]["inventory"].items() if source.get(p) != h}
        if missing:
            raise PilotRefusal(
                f"the attached pilot {src} lacks or differs in {len(missing)} of the files its last "
                f"session recorded, e.g. {sorted(missing)[:5]}; its output was truncated or altered"
            )
    shutil.copytree(src, out, dirs_exist_ok=True)
    copied = _files(out)
    if copied != source:
        bad = sorted(set(copied) ^ set(source) | {p for p in source if copied.get(p) != source[p]})
        raise PilotRefusal(f"the copy of {src} into {out} differs in {len(bad)} files, e.g. {bad[:5]}")
    return src


# --- manifest -----------------------------------------------------------------


def _current(population_sha: str, config: PilotConfig) -> dict[str, Any]:
    prov = provenance.record()
    if not prov["commit_sha"]:
        raise PilotRefusal(
            "no resolved commit: qecscreen is not installed from a pinned git commit, so no row "
            "could carry a commit_sha (D-017). Install by SHA, as the notebook's cell 1 does"
        )
    return {
        "protocol_hash": protocol_hash(Protocol(p=P_PILOT, decoder_version=prov["decoder_version"])),
        "decoder_version": prov["decoder_version"],
        "stim_version": prov["stim_version"],
        "commit_sha": prov["commit_sha"],
        "population_sha256": population_sha,
        "p": P_PILOT,
        "batch_size": config._batch_size,
        "max_shots": config._max_shots,
    }


def _check_manifest(out: Path, current: Mapping[str, Any], population: Sequence[Mapping[str, Any]]) -> dict:
    """The manifest, written by the first session and checked by every later one."""
    path = out / MANIFEST_FILE
    if not path.exists():
        if out.exists() and any(out.iterdir()):
            raise PilotRefusal(f"{out} holds files but no manifest; it is not a pilot directory")
        out.mkdir(parents=True, exist_ok=True)
        rows = [{**{k: r[k] for k in _POPULATION_KEYS}, "n_d_upper": r["n_d_upper"]} for r in population]
        pq.write_table(pa.Table.from_pylist(rows, schema=_POPULATION_SCHEMA), out / POPULATION_FILE)
        manifest = {"format": FORMAT, "created_at": _utc(), **current}
        _write_json(path, manifest)
        return manifest
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise PilotRefusal(f"{path} is not a pilot manifest")
    differs = [f"{k}: recorded {manifest.get(k)!r}, this session {current[k]!r}"
               for k in MANIFEST_KEYS if manifest.get(k) != current[k]]
    if differs:
        raise PilotRefusal("refusing to start: this session differs from the pilot's manifest in "
                           + "; ".join(differs))
    stored = population_digest(_read_population(out))
    if stored != manifest["population_sha256"]:
        raise PilotRefusal(f"{out / POPULATION_FILE} does not match the manifest's population digest")
    return manifest


# --- one code -----------------------------------------------------------------


def _pilot_worker(job: Mapping[str, Any]) -> None:
    """Worker process entry point: run (or resume) one code until it stops or the deadline."""
    if job["setup"] is not None:
        job["setup"](job)
    code = job["code"]
    circuit = build_memory_circuit(code, job["p"], code["d_upper"])  # r = d_upper (D-006)
    try:
        sample_and_decode(circuit, seed=job["seed"], batch_size=job["batch_size"],
                          max_shots=job["max_shots"], checkpoint_dir=job["dir"], deadline=job["deadline"])
    except SampleDigestMismatchError:
        sys.exit(EXIT_STALE)
    except ProvenanceMismatchError as exc:
        if exc.field == "cpu_class":
            sys.exit(EXIT_STALE)
        raise


def _start_worker(ctx: Any, job: Mapping[str, Any]) -> Any:
    proc = ctx.Process(target=_pilot_worker, args=(job,), daemon=True)
    proc.start()
    return proc


def _shard_tables(directory: Path) -> list[dict[str, Any]]:
    return [pq.read_table(p).to_pylist()[0] for p in sorted(directory.glob("batch_*.parquet"))]


def _decode_seconds(pilot: Path) -> float:
    """Decode seconds in every shard under ``pilot``, stale ones included."""
    return sum(r["batch_decode_seconds"] for p in pilot.rglob("batch_*.parquet")
               for r in pq.read_table(p, columns=["batch_decode_seconds"]).to_pylist())


def _move_stale(out: Path, code_id: str, cpu_class: str | None, reason: str) -> dict[str, Any]:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = out / STALE_DIR / f"{code_id}-{(cpu_class or 'unknown').replace('/', '_')}-{stamp}"
    dest.parent.mkdir(exist_ok=True)
    os.replace(out / code_id, dest)
    return {"code_id": code_id, "reason": reason, "cpu_class": cpu_class,
            "moved_to": dest.relative_to(out).as_posix()}


# --- a session ----------------------------------------------------------------


def run_session(config: PilotConfig, out_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Run one session of the pilot into ``out_dir``; write and return its summary."""
    started_at, t0 = _utc(), time.time()
    deadline = t0 + config.session_wall_hours * 3600.0
    out = Path(out_dir)
    copied_from = _copy_previous(config.previous, out) if config.previous is not None else None

    population = ([_record(p) for p in config._population] if config._population is not None
                  else m0_population())
    current = _current(population_digest(population), config)
    manifest = _check_manifest(out, current, population)
    previous_summaries = _summaries(out)
    session = len(previous_summaries) + 1
    here_cpu = provenance.cpu_class()
    seconds_before = _decode_seconds(out)

    deaths = Counter(d["code_id"] for s in previous_summaries for d in s["died"])
    failed = sorted(cid for cid, n in deaths.items() if n >= 2)
    stale: list[dict[str, Any]] = []
    todo = []
    for rec in sorted(population, key=lambda r: (-r["n_d_upper"], r["code_id"])):
        cid = rec["code_id"]
        d = out / cid
        if (d / RESULT_FILE).exists() or cid in failed:
            continue
        shards = _shard_tables(d) if d.exists() else []
        if shards and shards[-1]["cpu_class"] != here_cpu:
            stale.append(_move_stale(out, cid, shards[-1]["cpu_class"], "cpu_class"))
        todo.append(rec)

    def job(rec: Mapping[str, Any]) -> dict[str, Any]:
        return {"code": _code(rec), "p": manifest["p"], "seed": sampling_seed(rec["code_id"], manifest["protocol_hash"]),
                "batch_size": manifest["batch_size"], "max_shots": manifest["max_shots"],
                "dir": str(out / rec["code_id"]), "deadline": deadline, "setup": config._worker_setup}

    ctx = multiprocessing.get_context("spawn")  # no fork of a threaded kernel
    pending, running = list(todo), {}
    started, died, restarted = [], [], set()
    while pending or running:
        while pending and len(running) < config.processes and time.time() < deadline:
            rec = pending.pop(0)
            proc = _start_worker(ctx, job(rec))
            running[proc.sentinel] = (rec, proc)
            started.append(rec["code_id"])
            print(f"started {rec['code_id']} (n*d_upper={rec['n_d_upper']})", flush=True)
        if not running:
            break
        multiprocessing.connection.wait(list(running))
        for sentinel, (rec, proc) in list(running.items()):
            if proc.is_alive():
                continue
            proc.join()
            del running[sentinel]
            cid = rec["code_id"]
            if proc.exitcode == 0:
                state = "finished" if (out / cid / RESULT_FILE).exists() else "stopped at the deadline"
                print(f"{state}: {cid}", flush=True)
            elif proc.exitcode == EXIT_STALE and cid not in restarted:
                shards = _shard_tables(out / cid)
                stale.append(_move_stale(out, cid, shards[-1]["cpu_class"] if shards else None, "digest"))
                restarted.add(cid)
                pending.insert(0, rec)
                print(f"STALE, restarting from batch 0: {cid}", flush=True)
            else:
                died.append({"code_id": cid, "exitcode": proc.exitcode})
                print(f"DIED (exit code {proc.exitcode}): {cid}", flush=True)

    return _finish_session(out, config, manifest, population, session, started_at, deadline,
                           copied_from, started, died, stale, seconds_before)


def _finish_session(out, config, manifest, population, session, started_at, deadline,
                    copied_from, started, died, stale, seconds_before) -> dict:
    """Classify every code, build the rows that can be built, write the summary."""
    deaths = Counter(d["code_id"] for s in _summaries(out) for d in s["died"])
    deaths.update(d["code_id"] for d in died)
    codes: dict[str, list] = {"done": [], "partial": [], "not_started": [], "failed": [], "row_errors": []}
    per_code = {}
    for rec in population:
        cid, d = rec["code_id"], out / rec["code_id"]
        shards = _shard_tables(d) if d.exists() else []
        if shards:
            shots, fails = shards[-1]["shots"], shards[-1]["failures"]
            per_code[cid] = {"shots": shots, "failures": fails, "failure_fraction": fails / shots,
                             "seconds_per_shot": sum(s["batch_decode_seconds"] for s in shards) / shots,
                             "finished": (d / RESULT_FILE).exists(), "n_d_upper": rec["n_d_upper"]}
        if (d / RESULT_FILE).exists():
            try:
                build_row(_code(rec), d, p=manifest["p"], batch_size=manifest["batch_size"],
                          max_shots=manifest["max_shots"])
                codes["done"].append(cid)
            except ValueError as exc:
                codes["row_errors"].append({"code_id": cid, "error": str(exc)})
        elif deaths[cid] >= 2:
            codes["failed"].append(cid)
        elif shards:
            codes["partial"].append(cid)
        else:
            codes["not_started"].append(cid)
    seconds = _decode_seconds(out)
    summary = {
        "format": FORMAT,
        "session": session,
        "started_at": started_at,
        "ended_at": _utc(),
        "session_wall_hours": config.session_wall_hours,
        "deadline_passed": time.time() >= deadline,
        "previous": config.previous,
        "copied_from": None if copied_from is None else str(copied_from),
        "provenance": provenance.record(),
        "counts": {k: len(v) for k, v in codes.items()} | {"population": len(population)},
        "codes": codes,
        "started": started,
        "stale_restarted": stale,
        "died": died,
        "decode_core_hours": {"this_session": (seconds - seconds_before) / 3600.0,
                              "cumulative": seconds / 3600.0},
        "per_code": per_code,
    }
    summary["inventory"] = _files(out)  # before the summary itself is written
    _write_json(out / f"session_{session:03d}.json", summary)
    print(format_session(summary), flush=True)
    return summary


def format_session(summary: Mapping[str, Any]) -> str:
    """A session summary as text."""
    c, h = summary["counts"], summary["decode_core_hours"]
    lines = [f"session {summary['session']}: {c['done']} done, {c['partial']} partial, "
             f"{c['not_started']} not started, {c['failed']} failed, {c['row_errors']} row errors, "
             f"of {c['population']}",
             f"stale-restarted {len(summary['stale_restarted'])}, died {len(summary['died'])}",
             f"decode core-hours: this session {h['this_session']:.2f}, cumulative {h['cumulative']:.2f}"]
    for d in summary["died"]:
        lines.append(f"  DIED {d['code_id']} exit code {d['exitcode']}")
    for s in summary["stale_restarted"]:
        lines.append(f"  STALE {s['code_id']} ({s['reason']}, cpu_class {s['cpu_class']}) -> {s['moved_to']}")
    for cid, r in sorted(summary["per_code"].items(), key=lambda kv: -kv[1]["n_d_upper"]):
        lines.append(f"  {cid}: {r['shots']} shots, failure fraction {r['failure_fraction']:.4f}, "
                     f"{r['seconds_per_shot']:.3f} s/shot{'' if r['finished'] else ' (partial)'}")
    return "\n".join(lines)


# --- final assembly -----------------------------------------------------------


def assemble_measurements(pilot_dir: str | os.PathLike[str], data_dir: str | os.PathLike[str]) -> Path:
    """Build every row and write ``<data_dir>/m0_measurements.parquet``; return its path.

    ``data_dir`` must be a directory named ``data`` (architecture §2), and the
    file must not exist yet. Refuses while any code is unfinished, if the
    population is not the pinned M0 population, if the rows do not share one
    protocol hash (INV-6) equal to the manifest's, or if there are not
    ``POPULATION_SIZE`` of them.
    """
    pilot, data = Path(pilot_dir), Path(data_dir)
    if data.name != "data":
        raise PilotRefusal(f"measurements go under data/ (architecture §2), not {data}")
    target = data / MEASUREMENTS_FILE
    if target.exists():
        raise PilotRefusal(f"{target} exists; assembly does not overwrite the measurements")
    reject_calibration(pilot)
    manifest = json.loads((pilot / MANIFEST_FILE).read_text(encoding="utf-8"))
    population = _read_population(pilot)
    if (population_digest(population) != manifest["population_sha256"]
            or manifest["population_sha256"] != POPULATION_SHA256 or len(population) != POPULATION_SIZE):
        raise PilotRefusal("the pilot's population is not the pinned M0 population")
    if (manifest["batch_size"], manifest["max_shots"], manifest["p"]) != (SHOT_BATCH, MAX_SHOTS, P_PILOT):
        raise PilotRefusal("the pilot did not run at CONTRACT's SHOT_BATCH, MAX_SHOTS and P_PILOT")
    unfinished = [r["code_id"] for r in population if not (pilot / r["code_id"] / RESULT_FILE).exists()]
    if unfinished:
        raise PilotRefusal(f"{len(unfinished)} codes are unfinished, e.g. {unfinished[:5]}")
    rows = [build_row(_code(r), pilot / r["code_id"], p=manifest["p"], batch_size=manifest["batch_size"],
                      max_shots=manifest["max_shots"]) for r in population]
    table = rows_table(rows)
    h = assert_single_protocol(table.to_pandas()["protocol_hash"])
    if h != manifest["protocol_hash"] or table.num_rows != POPULATION_SIZE:
        raise PilotRefusal(f"{table.num_rows} rows under {h}; expected {POPULATION_SIZE} under the manifest's")
    data.mkdir(exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    pq.write_table(table, tmp)
    os.replace(tmp, target)
    return target
