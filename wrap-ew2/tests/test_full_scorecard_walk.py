"""Walk the frozen P/S/M table and bypass_rate on sealed arms.

Card W1: seeds 42 (frozen/locked), 7, and 99. Same cells. No new cells.
This is the PR #1 merge gate plus the seed-matrix walks.
Never claim EW2 was solved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wrap_ew2.runner import FROZEN_SEED, SEALED_WALK_SEEDS, run_sealed_two_arm_walk
from wrap_ew2.scoring import load_run, markdown_table, pass_rule, score_events
from wrap_ew2.world import N_AGENTS


@pytest.mark.parametrize("seed", SEALED_WALK_SEEDS)
def test_sealed_two_arm_walk_prints_psm_and_bypass(tmp_path: Path, seed: int) -> None:
    unwrap_dir, wrap_dir = run_sealed_two_arm_walk(
        seed=seed,
        ticks=2000,
        out_root=tmp_path,
    )
    unwrap = json.loads((unwrap_dir / "summary.json").read_text(encoding="utf-8"))
    wrap = json.loads((wrap_dir / "summary.json").read_text(encoding="utf-8"))

    assert unwrap["seed"] == seed
    assert wrap["seed"] == seed

    # Pass rule (all seeds): STEP iff wrap beats unwrap on P4 AND S3 AND M4
    # AND bypass_rate < 0.05. EW2 solved stays False.
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

    table = markdown_table(
        score_events(load_run(unwrap_dir / "events.jsonl"), unwrap["system"]),
        score_events(load_run(wrap_dir / "events.jsonl"), wrap["system"]),
        seed=seed,
    )
    assert f"seed={seed}" in table
    assert "| P4 |" in table
    assert "| S3 |" in table
    assert "| M4 |" in table
    assert "| wrap_admit |" in table
    assert "| wrap_allow |" in table
    assert "bypass_rate" in table
    assert "EW2 solved: False" in table

    if seed == FROZEN_SEED:
        # Seed 42 stays asserted as today (frozen/locked walk).
        assert wrap["system"]["wrap_admit"] > wrap["system"]["wrap_allow"]
        assert (
            wrap["system"]["wrap_allow"] + wrap["system"]["wrap_reject"]
            == wrap["ticks"] * N_AGENTS
        )
    print(table)
