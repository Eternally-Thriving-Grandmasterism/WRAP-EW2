"""Walk the frozen P/S/M table and bypass_rate on both sealed arms.

This is the PR #1 merge gate. Fixtures are not a substitute.
Never claim EW2 was solved.
"""

from __future__ import annotations

import json
from pathlib import Path

from wrap_ew2.runner import run_sim
from wrap_ew2.scoring import load_run, markdown_table, pass_rule, score_events
from wrap_ew2.world import N_AGENTS


def test_sealed_two_arm_walk_prints_psm_and_bypass(tmp_path: Path) -> None:
    unwrap_dir = run_sim(
        arm="unwrap",
        ticks=2000,
        seed=42,
        preset="sealed",
        out_dir=tmp_path / "unwrap",
    )
    wrap_dir = run_sim(
        arm="wrap",
        ticks=2000,
        seed=42,
        preset="sealed",
        out_dir=tmp_path / "wrap",
    )
    unwrap = json.loads((unwrap_dir / "summary.json").read_text(encoding="utf-8"))
    wrap = json.loads((wrap_dir / "summary.json").read_text(encoding="utf-8"))

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
    )
    assert "| P4 |" in table
    assert "| S3 |" in table
    assert "| M4 |" in table
    assert "| wrap_admit |" in table
    assert "| wrap_allow |" in table
    assert "bypass_rate" in table
    assert "EW2 solved: False" in table
    # wrap_admit is E1 Admit; wrap_allow is final act. They diverge on wrap.
    assert wrap["system"]["wrap_admit"] > wrap["system"]["wrap_allow"]
    assert wrap["system"]["wrap_allow"] + wrap["system"]["wrap_reject"] == wrap["ticks"] * N_AGENTS
    print(table)
