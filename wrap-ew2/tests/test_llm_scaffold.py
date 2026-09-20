"""--llm is a later hook. Fail closed. No live model calls. No heuristic fallback."""

from __future__ import annotations

import inspect

import pytest

from wrap_ew2.agent import HeuristicPolicy, LLMPolicy, build_policy
from wrap_ew2.runner import main, parse_args

VENDOR_KEY_ENVS = (
    "WRAP_EW2_LLM_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "XAI_API_KEY",
)


def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WRAP_EW2_LLM", raising=False)
    for name in VENDOR_KEY_ENVS:
        monkeypatch.delenv(name, raising=False)


def test_llm_flag_without_env_still_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_llm_env(monkeypatch)
    args = parse_args(["--arm", "unwrap", "--llm"])
    assert args.llm is True
    with pytest.raises(RuntimeError, match="WRAP_EW2_LLM=1"):
        build_policy(llm=args.llm)


def test_llm_env_without_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("WRAP_EW2_LLM", "1")
    with pytest.raises(RuntimeError, match="no API key"):
        policy = build_policy(llm=True)
        assert not isinstance(policy, HeuristicPolicy)


def test_default_policy_is_heuristic_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_llm_env(monkeypatch)
    policy = build_policy()
    assert isinstance(policy, HeuristicPolicy)


def test_llm_scaffold_with_env_and_key_still_does_not_call_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("WRAP_EW2_LLM", "1")
    monkeypatch.setenv("WRAP_EW2_LLM_KEY", "not-a-real-key")
    policy = build_policy(llm=True)
    assert isinstance(policy, LLMPolicy)
    with pytest.raises(RuntimeError, match="not implemented"):
        policy.choose(None)  # type: ignore[arg-type]


def test_runner_llm_without_env_does_not_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _clear_llm_env(monkeypatch)
    with pytest.raises(RuntimeError, match="WRAP_EW2_LLM=1"):
        main(
            [
                "--arm",
                "unwrap",
                "--ticks",
                "1",
                "--llm",
                "--out",
                str(tmp_path / "out"),
            ]
        )
    assert not (tmp_path / "out" / "events.jsonl").exists()


def test_llm_policy_does_not_import_vendor_clients_or_sealed() -> None:
    import wrap_ew2.agent as agent_mod

    source = inspect.getsource(agent_mod)
    assert "import openai" not in source
    assert "import anthropic" not in source
    assert "from openai" not in source
    assert "from anthropic" not in source
    assert "sealed_loader" not in source
    assert "ew2_black_swan" not in source
    assert "sealed.json" not in source
