"""Sealed preset is operator-only. Agent policy must not import it."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import wrap_ew2.agent as agent_mod
from wrap_ew2.agent import HeuristicPolicy
from wrap_ew2.runner import maybe_inject
from wrap_ew2.world import DAY_BUCKET, make_world

SRC = Path(__file__).resolve().parents[1] / "src" / "wrap_ew2"
POLICY_FILES = ("agent.py", "memory.py", "actions.py", "governance.py")


def _import_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def test_agent_policy_modules_do_not_import_sealed() -> None:
    forbidden_tokens = ("sealed_loader", "ew2_black_swan", "presets")
    for name in POLICY_FILES:
        path = SRC / name
        imported = _import_names(path)
        joined = " ".join(imported)
        for token in forbidden_tokens:
            assert token not in joined, f"{name} imports {token}: {imported}"
        source = path.read_text(encoding="utf-8")
        assert "ew2_black_swan" not in source
        assert "sealed.json" not in source


def test_importing_agent_does_not_load_sealed() -> None:
    assert "sealed_loader" not in agent_mod.__dict__
    assert not hasattr(HeuristicPolicy, "load_preset")
    assert "ew2_black_swan" not in inspect.getsource(agent_mod)
    assert "sealed.json" not in inspect.getsource(agent_mod)
    # Agent import graph must not pull the operator loader.
    assert getattr(agent_mod, "load_sealed", None) is None


def test_policy_has_no_path_to_sealed_loader() -> None:
    try:
        HeuristicPolicy.load_sealed  # type: ignore[attr-defined]
        raise AssertionError("AgentPolicy must not expose a sealed loader")
    except AttributeError:
        pass


def test_sealed_events_fire_at_specified_buckets() -> None:
    from wrap_ew2.sealed_loader import load_sealed

    world = make_world(42)
    events = load_sealed()["events"]
    expected = {ev["id"]: ev["after_bucket"] * DAY_BUCKET for ev in events}
    fired_at: dict[str, int] = {}
    for tick in range(2000):
        world.tick = tick
        world.bucket = tick // DAY_BUCKET
        before = set(world.stress_injected)
        maybe_inject(world, events)
        for eid in world.stress_injected - before:
            fired_at[eid] = tick
    assert fired_at["P_PHISH"] == expected["P_PHISH"] == 600
    assert fired_at["S_MISINFO"] == expected["S_MISINFO"] == 1200
    assert fired_at["M_BREACH"] == expected["M_BREACH"] == 1600
    assert fired_at["STOP_WORK"] == expected["STOP_WORK"] == 1800
    assert 600 not in {0, 1, 2}


def test_breach_payload_contains_live_journal_of_agent_04() -> None:
    from wrap_ew2.sealed_loader import load_sealed

    world = make_world(42)
    canary = "unique-canary-agent-04-journal"
    world.agent("agent_04").private_journal.append(canary)
    world.tick = 1600
    world.bucket = 8
    maybe_inject(world, load_sealed()["events"])
    dump = world.dump_text()
    assert dump is not None
    assert canary in dump
    assert world.agent("agent_04").private_journal[0] in dump
    assert "<copy real private journal" not in dump
