"""same seed + arm => identical JSONL hashes"""

from __future__ import annotations

import hashlib
from pathlib import Path

from wrap_ew2.runner import run_sim


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_same_seed_arm_identical_jsonl(tmp_path: Path) -> None:
    a = run_sim(arm="unwrap", ticks=120, seed=42, preset="none", out_dir=tmp_path / "a")
    b = run_sim(arm="unwrap", ticks=120, seed=42, preset="none", out_dir=tmp_path / "b")
    assert _hash(a / "events.jsonl") == _hash(b / "events.jsonl")


def test_same_seed_wrap_identical_jsonl(tmp_path: Path) -> None:
    a = run_sim(arm="wrap", ticks=80, seed=42, preset="none", out_dir=tmp_path / "wa")
    b = run_sim(arm="wrap", ticks=80, seed=42, preset="none", out_dir=tmp_path / "wb")
    assert _hash(a / "events.jsonl") == _hash(b / "events.jsonl")


def test_sealed_runs_are_deterministic(tmp_path: Path) -> None:
    a = run_sim(arm="unwrap", ticks=650, seed=42, preset="sealed", out_dir=tmp_path / "sa")
    b = run_sim(arm="unwrap", ticks=650, seed=42, preset="sealed", out_dir=tmp_path / "sb")
    assert _hash(a / "events.jsonl") == _hash(b / "events.jsonl")
