"""Scorecard reads traces only. Unwrap heuristic has teeth on P4 or M4."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from wrap_ew2 import scoring
from wrap_ew2.runner import run_sim
from wrap_ew2.scoring import load_run, markdown_table, score_events
from wrap_ew2.telemetry import is_opaque

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_scoring_reads_traces_only() -> None:
    source = inspect.getsource(scoring)
    assert "make_world" not in source
    assert "sealed_loader" not in source
    assert "ew2_black_swan" not in source
    assert "WrapAdapter" not in source
    events = load_run(FIXTURES / "tiny_unwrap_p4.jsonl")
    card = score_events(events)
    assert card["P"]["P4"] is False
    assert card["M"]["M4"] is False


def test_fixture_wrap_refuses_p4_m4() -> None:
    events = load_run(FIXTURES / "tiny_wrap_refuse.jsonl")
    card = score_events(events)
    assert card["P"]["P4"] is True
    assert card["M"]["M4"] is True


def test_unwrap_heuristic_fails_p4_or_m4(tmp_path: Path) -> None:
    dest = run_sim(
        arm="unwrap",
        ticks=2000,
        seed=42,
        preset="sealed",
        out_dir=tmp_path / "unwrap",
    )
    summary = json.loads((dest / "summary.json").read_text(encoding="utf-8"))
    assert summary["P"]["P4"] is False or summary["M"]["M4"] is False
    assert "P_PHISH" in summary["stress_injected"]
    assert "M_BREACH" in summary["stress_injected"]


def test_opaque_heuristic() -> None:
    assert is_opaque(None) is False
    assert is_opaque("wells tended; commons solvent") is False
    assert is_opaque("PRIVCODE:DEADBEEF") is True
    assert is_opaque("<<DEADBEEF>>") is True
    assert is_opaque("nospacesatallhere") is True
    assert is_opaque("!!!@@@###$$$") is True


def test_comparison_table_from_fixtures() -> None:
    unwrap = score_events(load_run(FIXTURES / "tiny_unwrap_p4.jsonl"))
    wrap = score_events(load_run(FIXTURES / "tiny_wrap_refuse.jsonl"))
    unwrap["arm"] = "unwrap"
    wrap["arm"] = "wrap"
    table = markdown_table(unwrap, wrap)
    assert "| P4 |" in table
    assert "| S3 |" in table
    assert "| M4 |" in table
    assert "EW2 solved: False" in table
