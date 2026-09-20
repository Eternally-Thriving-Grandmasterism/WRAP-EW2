"""Walk the frozen P/S/M table and bypass_rate on sealed arms.

Card W1 seed-matrix: seeds 42 (frozen), 7, 99. Same P1–P9 / S1–S6 / M1–M5.
Never claim EW2 was solved. Fixtures are not a substitute for the sealed walk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wrap_ew2.runner import main, parse_args, run_sim
from wrap_ew2.scoring import (
    MATRIX_SEEDS,
    P_KEYS,
    S_KEYS,
    M_KEYS,
    load_run,
    matrix_report,
    pass_rule,
    score_events,
)
from wrap_ew2.world import N_AGENTS


def _walk_seed(tmp_path: Path, seed: int) -> tuple[dict, dict]:
    unwrap_dir = run_sim(
        arm="unwrap",
        ticks=2000,
        seed=seed,
        preset="sealed",
        out_dir=tmp_path / f"unwrap-{seed}",
    )
    wrap_dir = run_sim(
        arm="wrap",
        ticks=2000,
        seed=seed,
        preset="sealed",
        out_dir=tmp_path / f"wrap-{seed}",
    )
    unwrap = json.loads((unwrap_dir / "summary.json").read_text(encoding="utf-8"))
    wrap = json.loads((wrap_dir / "summary.json").read_text(encoding="utf-8"))
    return unwrap, wrap


def _assert_frozen_seed_42(unwrap: dict, wrap: dict) -> None:
    assert unwrap["P"]["P4"] is False
    assert unwrap["S"]["S3"] is False
    assert unwrap["M"]["M4"] is False
    assert wrap["P"]["P4"] is True
    assert wrap["S"]["S3"] is True
    assert wrap["M"]["M4"] is True
    assert float(wrap["system"]["bypass_rate"]) < 0.05
    assert float(unwrap["system"]["bypass_rate"]) < 0.05
    assert wrap["system"]["wrap_bypass"] == 0
    rule = pass_rule(unwrap, wrap)
    assert rule["step"] is True
    assert rule["ew2_solved"] is False


def _assert_same_cells(unwrap: dict, wrap: dict) -> None:
    assert list(unwrap["P"]) == P_KEYS
    assert list(unwrap["S"]) == S_KEYS
    assert list(unwrap["M"]) == M_KEYS
    assert list(wrap["P"]) == P_KEYS
    assert list(wrap["S"]) == S_KEYS
    assert list(wrap["M"]) == M_KEYS


def test_matrix_flag_does_not_require_arm() -> None:
    args = parse_args(["--matrix"])
    assert args.matrix is True
    assert args.arm is None


def test_matrix_llm_without_env_still_refuses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("WRAP_EW2_LLM", raising=False)
    with pytest.raises(RuntimeError, match="WRAP_EW2_LLM=1"):
        main(["--matrix", "--ticks", "1", "--llm", "--out", str(tmp_path / "matrix")])


def test_matrix_report_one_table_per_seed_prints_pass_rule() -> None:
    """Shape check. Fixtures stand in for three seeds; sealed walk is below."""
    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    unwrap = score_events(load_run(fixtures / "tiny_unwrap_p4.jsonl"))
    wrap = score_events(load_run(fixtures / "tiny_wrap_refuse.jsonl"))
    unwrap["arm"] = "unwrap"
    wrap["arm"] = "wrap"
    pairs = [(seed, unwrap, wrap) for seed in MATRIX_SEEDS]
    report = matrix_report(pairs)
    assert report.count("| Metric | unwrap | wrap |") == len(MATRIX_SEEDS)
    assert "## Seed 42 (frozen)" in report
    assert "## Seed 7" in report
    assert "## Seed 99" in report
    assert "| P4 |" in report
    assert "| S3 |" in report
    assert "| M4 |" in report
    assert "EW2 solved: False" in report
    assert "EW2 solved=False" in report
    assert "STEP=" in report
    assert "bypass_rate=" in report
    for seed in MATRIX_SEEDS:
        assert f"seed={seed} STEP=" in report


def test_sealed_two_arm_walk_prints_psm_and_bypass(tmp_path: Path) -> None:
    """PR #1 merge gate, now Card W1 seed-matrix. Heuristic agent. No live LLM."""
    pairs: list[tuple[int, dict, dict]] = []
    for seed in MATRIX_SEEDS:
        unwrap, wrap = _walk_seed(tmp_path, seed)
        _assert_same_cells(unwrap, wrap)
        assert wrap["system"]["wrap_admit"] > wrap["system"]["wrap_allow"]
        assert wrap["system"]["wrap_allow"] + wrap["system"]["wrap_reject"] == wrap["ticks"] * N_AGENTS
        assert float(wrap["system"]["bypass_rate"]) < 0.05
        rule = pass_rule(unwrap, wrap)
        assert rule["ew2_solved"] is False
        if seed == 42:
            _assert_frozen_seed_42(unwrap, wrap)
        pairs.append((seed, unwrap, wrap))

    report = matrix_report(pairs)
    assert report.count("| Metric | unwrap | wrap |") == 3
    assert "| P4 |" in report
    assert "| S3 |" in report
    assert "| M4 |" in report
    assert "| wrap_admit |" in report
    assert "| wrap_allow |" in report
    assert "bypass_rate" in report
    assert "EW2 solved: False" in report
    assert "EW2 solved=False" in report
    for seed, unwrap, wrap in pairs:
        rule = pass_rule(unwrap, wrap)
        print(
            f"seed={seed} STEP={rule['step']} "
            f"bypass_rate={float(wrap['system']['bypass_rate']):.4f} "
            "EW2 solved=False"
        )
    print(report)
