"""M0-EVAL-04: resume within a code, at batch granularity.

A run killed mid-code and resumed must end with exactly the shots and failures
of an uninterrupted run: every batch decoded once, in order, on the same
syndromes. The decoder is wrapped to record a digest of every syndrome batch
it finished decoding, and to raise (the "kill") on a chosen batch. A code that
finished is never re-run.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os

import pytest

import qecscreen.evaluate.checkpoint as ckpt_mod
import qecscreen.evaluate.run as run_mod
from qecscreen.circuits.build import build_memory_circuit
from qecscreen.evaluate.checkpoint import RESULT_FILE, CheckpointMismatchError
from qecscreen.evaluate.run import sample_and_decode

SMALL = {"l": 2, "m": 3, "a_exps": [(1, 0), (0, 2)], "b_exps": [(0, 1), (2, 0)]}  # [[12,2,3]], as test_evaluate_run
SMALL_ROUNDS = 3

# (p, batch_size, max_shots, stopped_by): one run that reaches MIN_FAILURES
# after several batches, one that is capped and censored.
CONFIGS = {
    "min_failures": (0.012, 32, 1_024, "min_failures"),
    "max_shots": (0.002, 64, 512, "max_shots"),
}
SEED = 20260928
_REAL_DECODER = run_mod.CompiledBpOsd


class Killed(Exception):
    """Stands in for the process dying mid-batch."""


class Recorder:
    """Patches ``run.CompiledBpOsd``: records each finished batch's syndromes
    and, if ``kill_at`` is set, dies on that decode call (0-based)."""

    def __init__(self, monkeypatch, kill_at: int | None = None) -> None:
        self.decoded: list[bytes] = []
        self.calls = 0
        self.kill_at = kill_at
        recorder = self

        class Recording(_REAL_DECODER):
            def decode_shots_bit_packed(self, *, bit_packed_detection_event_data):
                call = recorder.calls
                recorder.calls += 1
                if call == recorder.kill_at:
                    raise Killed(f"killed during decode call {call}")
                out = super().decode_shots_bit_packed(
                    bit_packed_detection_event_data=bit_packed_detection_event_data)
                recorder.decoded.append(bit_packed_detection_event_data.tobytes())
                return out

        monkeypatch.setattr(run_mod, "CompiledBpOsd", Recording)


def _digest(batches: list[bytes]) -> str:
    h = hashlib.sha256()
    for b in batches:
        h.update(b)
    return h.hexdigest()


def _counts(result) -> dict:
    """Every RunResult field except decode_seconds, which is wall-clock telemetry."""
    d = dataclasses.asdict(result)
    del d["decode_seconds"]
    return d


def _shards(directory) -> list[str]:
    return sorted(p for p in os.listdir(directory) if p.startswith("batch_"))


_REFERENCE: dict[str, tuple] = {}


def _reference(name: str) -> tuple:
    """The uninterrupted run for a config and the syndromes it decoded, computed once."""
    if name not in _REFERENCE:
        p, batch_size, max_shots, stopped_by = CONFIGS[name]
        circuit = build_memory_circuit(SMALL, p, SMALL_ROUNDS)
        kw = dict(seed=SEED, batch_size=batch_size, max_shots=max_shots)
        with pytest.MonkeyPatch.context() as m:
            recorder = Recorder(m)
            result = sample_and_decode(circuit, **kw)
        assert result.stopped_by == stopped_by
        assert result.shots // batch_size >= 4 and len(recorder.decoded) == result.shots // batch_size
        _REFERENCE[name] = (circuit, kw, result, tuple(recorder.decoded))
    return _REFERENCE[name]


@pytest.fixture(params=sorted(CONFIGS))
def config(request):
    return _reference(request.param)


@pytest.mark.parametrize("where", ["first", "second", "middle", "last"])
def test_a_run_killed_mid_code_resumes_to_the_uninterrupted_result(config, where, monkeypatch, tmp_path):
    circuit, kw, uninterrupted, reference = config
    n_batches = len(reference)
    b = {"first": 0, "second": 1, "middle": n_batches // 2, "last": n_batches - 1}[where]

    killed = Recorder(monkeypatch, kill_at=b)
    with pytest.raises(Killed):
        sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)
    # Batches 0..b-1 were flushed before batch b started; batch b was not.
    assert len(killed.decoded) == b
    assert _shards(tmp_path) == [f"batch_{i:06d}.parquet" for i in range(b)]
    assert not (tmp_path / RESULT_FILE).exists()

    resumed = Recorder(monkeypatch)
    result = sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)
    # Identical shots and failures, and the same syndromes decoded exactly
    # once each, in order: none skipped, none decoded twice.
    assert _counts(result) == _counts(uninterrupted)
    assert len(resumed.decoded) == n_batches - b
    assert _digest(killed.decoded + resumed.decoded) == _digest(list(reference))
    assert (tmp_path / RESULT_FILE).exists()
    assert len(_shards(tmp_path)) == n_batches


def test_a_completed_code_is_never_re_run(config, monkeypatch, tmp_path):
    circuit, kw, uninterrupted, _ = config
    first = sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)
    assert _counts(first) == _counts(uninterrupted)
    files = {p: (tmp_path / p).read_bytes() for p in os.listdir(tmp_path)}

    rerun = Recorder(monkeypatch)

    class NoCircuit:  # any use of the circuit (sampler, DEM, decoder) fails
        def __getattr__(self, name):
            raise AssertionError(f"a completed code touched circuit.{name}")

    again = sample_and_decode(NoCircuit(), checkpoint_dir=tmp_path, **kw)  # type: ignore[arg-type]
    assert again == first  # decode_seconds included: read back, not re-measured
    assert rerun.calls == 0
    assert {p: (tmp_path / p).read_bytes() for p in os.listdir(tmp_path)} == files


def test_killed_after_the_last_shard_but_before_the_result_decodes_nothing(config, monkeypatch, tmp_path):
    circuit, kw, uninterrupted, reference = config
    n_batches = len(reference)

    def die(self, result):
        raise Killed("killed before the result was written")

    with monkeypatch.context() as m:
        m.setattr(ckpt_mod.CodeCheckpoint, "write_result", die)
        with pytest.raises(Killed):
            sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)
    assert len(_shards(tmp_path)) == n_batches

    resumed = Recorder(monkeypatch)
    result = sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)
    assert _counts(result) == _counts(uninterrupted)
    assert resumed.calls == 0


def test_a_kill_mid_write_leaves_no_shard_and_resumes(monkeypatch, tmp_path):
    """The shard is written to a .tmp name and renamed; dying before the
    rename leaves the .tmp, which is ignored, and the batch is redone."""
    p, batch_size, max_shots, _ = CONFIGS["min_failures"]
    circuit = build_memory_circuit(SMALL, p, SMALL_ROUNDS)
    kw = dict(seed=SEED, batch_size=batch_size, max_shots=max_shots)
    uninterrupted = sample_and_decode(circuit, **kw)

    real_replace = os.replace
    calls = {"n": 0}

    def replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 3:
            raise Killed("killed between write and rename")
        return real_replace(src, dst)

    with monkeypatch.context() as m:
        m.setattr(ckpt_mod.os, "replace", replace)
        with pytest.raises(Killed):
            sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)
    assert _shards(tmp_path) == ["batch_000000.parquet", "batch_000001.parquet",
                                 "batch_000002.parquet.tmp"]

    result = sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)
    assert _counts(result) == _counts(uninterrupted)


@pytest.mark.parametrize("change", [dict(seed=SEED + 1), dict(batch_size=64), dict(max_shots=2_048)])
def test_a_checkpoint_from_another_run_is_refused(change, monkeypatch, tmp_path):
    p, batch_size, max_shots, _ = CONFIGS["min_failures"]
    circuit = build_memory_circuit(SMALL, p, SMALL_ROUNDS)
    kw = dict(seed=SEED, batch_size=batch_size, max_shots=max_shots)
    Recorder(monkeypatch, kill_at=3)
    with pytest.raises(Killed):
        sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)
    with pytest.raises(CheckpointMismatchError):
        sample_and_decode(circuit, checkpoint_dir=tmp_path, **{**kw, **change})
    # And a finished code under other settings.
    sample_and_decode(circuit, checkpoint_dir=tmp_path / "done", **kw)
    with pytest.raises(CheckpointMismatchError):
        sample_and_decode(circuit, checkpoint_dir=tmp_path / "done", **{**kw, **change})


def test_re_drawn_shots_that_differ_from_the_shards_are_refused(monkeypatch, tmp_path):
    """Stands in for resuming on another stim version or CPU class (D-027):
    the re-drawn stream is not the recorded one, so it must not be continued."""
    import pyarrow.parquet as pq

    p, batch_size, max_shots, _ = CONFIGS["min_failures"]
    circuit = build_memory_circuit(SMALL, p, SMALL_ROUNDS)
    kw = dict(seed=SEED, batch_size=batch_size, max_shots=max_shots)
    Recorder(monkeypatch, kill_at=3)
    with pytest.raises(Killed):
        sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)
    shard = tmp_path / "batch_000001.parquet"
    table = pq.read_table(shard)
    col = table.schema.get_field_index("batch_samples_sha256")
    pq.write_table(table.set_column(col, table.schema.field(col), [["0" * 64]]), shard)
    with pytest.raises(CheckpointMismatchError, match="batch 1"):
        sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)


def test_a_gap_in_the_shards_is_refused(monkeypatch, tmp_path):
    p, batch_size, max_shots, _ = CONFIGS["min_failures"]
    circuit = build_memory_circuit(SMALL, p, SMALL_ROUNDS)
    kw = dict(seed=SEED, batch_size=batch_size, max_shots=max_shots)
    Recorder(monkeypatch, kill_at=3)
    with pytest.raises(Killed):
        sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)
    (tmp_path / "batch_000001.parquet").unlink()
    with pytest.raises(CheckpointMismatchError, match="missing"):
        sample_and_decode(circuit, checkpoint_dir=tmp_path, **kw)
