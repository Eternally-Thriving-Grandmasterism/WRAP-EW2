"""same seed + arm => identical JSONL hashes; different seeds must not share a SHA"""

from __future__ import annotations

from pathlib import Path

import pytest

from wrap_ew2.runner import SEALED_WALK_SEEDS, run_sim
from wrap_ew2.scoring import (
    compare_jsonl_traces,
    event_kind,
    events_sha256,
    first_tick_kind_mismatch,
    format_trace_diff,
)


def test_same_seed_arm_identical_jsonl(tmp_path: Path) -> None:
    a = run_sim(arm="unwrap", ticks=120, seed=42, preset="none", out_dir=tmp_path / "a")
    b = run_sim(arm="unwrap", ticks=120, seed=42, preset="none", out_dir=tmp_path / "b")
    assert events_sha256(a) == events_sha256(b)


def test_same_seed_wrap_identical_jsonl(tmp_path: Path) -> None:
    a = run_sim(arm="wrap", ticks=80, seed=42, preset="none", out_dir=tmp_path / "wa")
    b = run_sim(arm="wrap", ticks=80, seed=42, preset="none", out_dir=tmp_path / "wb")
    assert events_sha256(a) == events_sha256(b)
    self_cmp = compare_jsonl_traces(a, a)
    assert self_cmp["status"] == "IDENTICAL"


def test_sealed_runs_are_deterministic(tmp_path: Path) -> None:
    a = run_sim(arm="unwrap", ticks=650, seed=42, preset="sealed", out_dir=tmp_path / "sa")
    b = run_sim(arm="unwrap", ticks=650, seed=42, preset="sealed", out_dir=tmp_path / "sb")
    assert events_sha256(a) == events_sha256(b)


def test_trace_diff_helper_identifies_tick_kind_mismatch(tmp_path: Path) -> None:
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text(
        '{"tick":0,"intent":{"op":"harvest"},"seed":42}\n'
        '{"tick":1,"intent":{"op":"transfer"},"seed":42}\n',
        encoding="utf-8",
    )
    b.write_text(
        '{"tick":0,"intent":{"op":"harvest"},"seed":7}\n'
        '{"tick":1,"intent":{"op":"warn"},"seed":7}\n',
        encoding="utf-8",
    )
    result = compare_jsonl_traces(a, b)
    assert result["status"] == "DIFF"
    assert result["mismatch"] == {
        "index": 1,
        "tick_a": 1,
        "tick_b": 1,
        "kind_a": "transfer",
        "kind_b": "warn",
    }
    assert result["payload_status"] == "DIFF"
    labels_only = tmp_path / "labels.jsonl"
    labels_only.write_text(
        '{"tick":0,"intent":{"op":"harvest"},"seed":99,"run_id":"x"}\n'
        '{"tick":1,"intent":{"op":"transfer"},"seed":99,"run_id":"x"}\n',
        encoding="utf-8",
    )
    same_payload = compare_jsonl_traces(a, labels_only)
    assert same_payload["status"] == "DIFF"
    assert same_payload["payload_status"] == "IDENTICAL"
    assert same_payload["mismatch"] is None
    assert event_kind({"intent": {"op": "harvest"}}) == "harvest"
    events_a = [{"tick": 0, "intent": {"op": "harvest"}}, {"tick": 1, "intent": {"op": "transfer"}}]
    events_b = [{"tick": 0, "intent": {"op": "harvest"}}, {"tick": 1, "intent": {"op": "warn"}}]
    assert first_tick_kind_mismatch(events_a, events_b)["kind_b"] == "warn"
    print(format_trace_diff("fixture", result))


def test_different_seed_same_arm_different_sha(tmp_path: Path) -> None:
    a = run_sim(arm="wrap", ticks=80, seed=42, preset="none", out_dir=tmp_path / "s42")
    b = run_sim(arm="wrap", ticks=80, seed=7, preset="none", out_dir=tmp_path / "s7")
    result = compare_jsonl_traces(a, b)
    print(format_trace_diff("42vs7", result))
    if result["status"] == "IDENTICAL":
        pytest.fail("42vs7: IDENTICAL — stop; do not claim seed-matrix diversity")
    assert events_sha256(a) != events_sha256(b)


def test_wrap_seeds_42_7_99_first_tick_kind_mismatch(tmp_path: Path) -> None:
    """Card W2: wrap arm 42 vs 7 and 42 vs 99. Print first tick/kind mismatch."""
    paths: dict[int, Path] = {}
    for seed in SEALED_WALK_SEEDS:
        paths[seed] = run_sim(
            arm="wrap",
            ticks=2000,
            seed=seed,
            preset="sealed",
            out_dir=tmp_path / f"wrap-{seed}",
        )

    shas = {seed: events_sha256(paths[seed]) for seed in SEALED_WALK_SEEDS}
    assert len(set(shas.values())) == 3

    for left, right in ((42, 7), (42, 99)):
        result = compare_jsonl_traces(paths[left], paths[right])
        line = format_trace_diff(f"{left}vs{right}", result)
        print(line)
        if result["status"] == "IDENTICAL":
            pytest.fail(
                f"{left}vs{right}: IDENTICAL — stop; do not claim seed-matrix diversity"
            )
        assert result["status"] == "DIFF"
        assert result["first_event"] is not None
        print(
            f"{left}vs{right} first differing event kind+tick: "
            f"kind_a={result['first_event']['kind_a']} "
            f"tick_a={result['first_event']['tick_a']} "
            f"kind_b={result['first_event']['kind_b']} "
            f"tick_b={result['first_event']['tick_b']}"
        )
        if result.get("payload_status") == "IDENTICAL":
            print(
                f"{left}vs{right}: label-stripped payload IDENTICAL; "
                "do not claim seed-matrix diversity of the act stream"
            )
