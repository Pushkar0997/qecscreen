"""M0-EVAL-04: per-batch checkpoints, so a code resumes after its last completed batch.

A code's checkpoint directory holds one Parquet shard per completed batch,
``batch_000000.parquet``, ``batch_000001.parquet``, ..., each written before
the next batch is sampled, and ``result.parquet`` once the code has stopped.
A shard records the batch's shot and failure counts, the running totals, and
a sha256 of the batch's sampled bytes. ``sample_and_decode`` reads the shards
back, re-creates the seeded sampler, draws and discards the completed batches
(checking each one's digest against its shard), and decodes from the next
batch on. A code with ``result.parquet`` is never re-run.

Every file is written under a temporary name, synced, and renamed into place,
so a kill mid-write leaves no shard, only a ``.tmp`` file that is ignored and
overwritten by the next attempt.

Nothing here is a label. The row (INV-3 censoring, Wilson interval,
provenance) is built from the final ``RunResult`` by the caller.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from qecscreen.protocol import MIN_FAILURES

__all__ = [
    "BatchRecord",
    "CheckpointMismatchError",
    "CodeCheckpoint",
    "RESULT_FILE",
]

RESULT_FILE = "result.parquet"
_SHARD_RE = re.compile(r"batch_(\d{6})\.parquet")

# Identity of the run a checkpoint belongs to. A resume with any of these
# different would splice two runs' shots into one count.
_RUN_FIELDS = [
    pa.field("seed", pa.uint64()),
    pa.field("batch_size", pa.int64()),
    pa.field("max_shots", pa.int64()),
]
_SHARD_SCHEMA = pa.schema(
    _RUN_FIELDS
    + [
        pa.field("batch_index", pa.int64()),
        pa.field("batch_shots", pa.int64()),
        pa.field("batch_failures", pa.int64()),
        pa.field("batch_osd_invocations", pa.int64()),
        pa.field("batch_decode_seconds", pa.float64()),
        pa.field("batch_samples_sha256", pa.string()),
        pa.field("shots", pa.int64()),  # running totals through this batch
        pa.field("failures", pa.int64()),
        pa.field("samples_sha256", pa.string()),
    ]
)
_RESULT_SCHEMA = pa.schema(
    _RUN_FIELDS
    + [
        pa.field("shots", pa.int64()),
        pa.field("failures", pa.int64()),
        pa.field("stopped_by", pa.string()),
        pa.field("osd_invocations", pa.int64()),
        pa.field("samples_sha256", pa.string()),
        pa.field("decode_seconds", pa.float64()),
    ]
)


class CheckpointMismatchError(ValueError):
    """A checkpoint cannot be resumed: it belongs to another run, it is
    inconsistent, or the re-drawn shots differ from the ones it recorded."""


@dataclass(frozen=True)
class BatchRecord:
    """One completed batch, as flushed to its shard."""

    batch_index: int
    batch_shots: int
    batch_failures: int
    batch_osd_invocations: int
    batch_decode_seconds: float
    batch_samples_sha256: str
    shots: int
    failures: int
    samples_sha256: str


def _write_atomic(table: pa.Table, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        pq.write_table(table, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _read_one(path: Path, schema: pa.Schema) -> dict:
    table = pq.read_table(path)
    if table.num_rows != 1 or not table.schema.equals(schema):
        raise CheckpointMismatchError(f"{path} is not a single-row checkpoint file of this schema")
    return table.to_pylist()[0]


class CodeCheckpoint:
    """The checkpoint directory of one ``(code, p)`` run.

    ``seed``, ``batch_size`` and ``max_shots`` identify the run; every file
    read back must carry the same three, or ``CheckpointMismatchError``.
    """

    def __init__(self, directory: str | os.PathLike[str], *, seed: int, batch_size: int,
                 max_shots: int) -> None:
        self.directory = Path(directory)
        self.run = {"seed": seed, "batch_size": batch_size, "max_shots": max_shots}

    def _check_run(self, record: dict, path: Path) -> None:
        got = {k: record[k] for k in self.run}
        if got != self.run:
            raise CheckpointMismatchError(
                f"{path} belongs to the run {got}, not {self.run}; refusing to resume it"
            )

    def result(self) -> dict | None:
        """The stored ``RunResult`` fields if this code has finished, else ``None``."""
        path = self.directory / RESULT_FILE
        if not path.exists():
            return None
        rec = _read_one(path, _RESULT_SCHEMA)
        self._check_run(rec, path)
        del rec["max_shots"]
        return rec

    def batches(self) -> list[BatchRecord]:
        """Completed batches, in order, checked to be one consistent run prefix."""
        if not self.directory.exists():
            return []
        found = sorted(
            (int(m.group(1)), p)
            for p in self.directory.iterdir()
            if (m := _SHARD_RE.fullmatch(p.name))
        )
        records: list[BatchRecord] = []
        shots = failures = 0
        for i, (index, path) in enumerate(found):
            if index != i:
                raise CheckpointMismatchError(f"shard {i} is missing; found {path.name}")
            rec = _read_one(path, _SHARD_SCHEMA)
            self._check_run(rec, path)
            if failures >= MIN_FAILURES or shots >= self.run["max_shots"]:
                raise CheckpointMismatchError(f"{path.name} is past the run's stopping point")
            shots += rec["batch_shots"]
            failures += rec["batch_failures"]
            if (rec["batch_index"] != i or rec["batch_shots"] != self.run["batch_size"]
                    or (rec["shots"], rec["failures"]) != (shots, failures)):
                raise CheckpointMismatchError(f"{path.name} is inconsistent with the shards before it")
            records.append(BatchRecord(**{k: rec[k] for k in BatchRecord.__dataclass_fields__}))
        return records

    def write_batch(self, record: BatchRecord) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        row = {**self.run, **record.__dict__}
        _write_atomic(pa.Table.from_pylist([row], schema=_SHARD_SCHEMA),
                      self.directory / f"batch_{record.batch_index:06d}.parquet")

    def write_result(self, result: dict) -> None:
        """``result`` is a ``RunResult``'s fields; its seed and batch size must be this run's."""
        self._check_run({**self.run, **{k: result[k] for k in ("seed", "batch_size")}}, self.directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        row = {**self.run, **{k: result[k] for k in _RESULT_SCHEMA.names if k not in self.run}}
        _write_atomic(pa.Table.from_pylist([row], schema=_RESULT_SCHEMA), self.directory / RESULT_FILE)
