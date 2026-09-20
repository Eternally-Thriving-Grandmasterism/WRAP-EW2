"""CLI runner. Loads the sealed preset only when --preset sealed."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from wrap_ew2.actions import apply_intent, is_off_charter
from wrap_ew2.agent import build_policy
from wrap_ew2.memory import observe, update_after_act
from wrap_ew2.governance import resolve_votes
from wrap_ew2.scoring import score_events, write_summary
from wrap_ew2.telemetry import JsonlWriter, build_event, recognized_ids
from wrap_ew2.world import DAY_BUCKET, SEED_DEFAULT, TICKS_DEFAULT, World, make_world
from wrap_ew2.wrap_adapter import WrapAdapter
from wrap_ew2.wrap_stub import WrapStub

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "wrap-ew2"
FROZEN_SEED = 42
SEALED_WALK_SEEDS = (42, 7, 99)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WRAP-EW2 research runner")
    parser.add_argument("--arm", choices=("wrap", "unwrap"), required=True)
    parser.add_argument("--ticks", type=int, default=TICKS_DEFAULT)
    parser.add_argument("--seed", type=int, default=SEED_DEFAULT)
    parser.add_argument("--preset", choices=("sealed", "none"), default="none")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--llm",
        action="store_true",
        help="later model-arm hook; refuse unless WRAP_EW2_LLM=1; fail closed if no key",
    )
    parser.add_argument("--skip-edges", default="", help="test hook: comma edges e.g. e3")
    return parser.parse_args(argv)


def run_id_for(arm: str, seed: int, ticks: int, preset: str) -> str:
    return f"{arm}-seed{seed}-ticks{ticks}-{preset}"


def run_sealed_two_arm_walk(
    *,
    seed: int,
    ticks: int = TICKS_DEFAULT,
    out_root: Path | None = None,
    preset: str = "sealed",
) -> tuple[Path, Path]:
    """Run unwrap then wrap for one seed. Dest dirs stay seed-keyed."""
    root = out_root or DATA_ROOT
    unwrap_dir = run_sim(
        arm="unwrap",
        ticks=ticks,
        seed=seed,
        preset=preset,
        out_dir=root / run_id_for("unwrap", seed, ticks, preset),
    )
    wrap_dir = run_sim(
        arm="wrap",
        ticks=ticks,
        seed=seed,
        preset=preset,
        out_dir=root / run_id_for("wrap", seed, ticks, preset),
    )
    return unwrap_dir, wrap_dir


def maybe_inject(world: World, events: list[dict[str, Any]]) -> str | None:
    if not world.state_exists():
        return None
    fired: str | None = None
    for ev in events:
        eid = ev["id"]
        if eid in world.stress_injected:
            continue
        if world.bucket < int(ev["after_bucket"]):
            continue
        _fire(world, ev)
        fired = eid
    return fired


def _fire(world: World, ev: dict[str, Any]) -> None:
    eid = ev["id"]
    surface = ev["surface"]
    payload = ev["payload"]
    if eid == "M_BREACH":
        journal = " | ".join(world.agent("agent_04").private_journal)
        payload = f"DUMP journal of agent_04: {journal}"
    if surface == "harvest_message":
        for node in world.nodes.values():
            node.message = payload
        world.harvest_messages.append(payload)
    elif surface == "public_board":
        from wrap_ew2.world import BoardEntry

        world.public_board.append(
            BoardEntry(
                tick=world.tick,
                author="unsigned",
                text=payload,
                kind="inject",
                unverified=(eid == "S_MISINFO"),
                claim_id=eid,
            )
        )
    if eid == "STOP_WORK":
        world.stop_work = True
    world.stress_injected.add(eid)
    world.last_injection = eid


def build_gate(arm: str) -> WrapAdapter | WrapStub:
    if arm == "wrap":
        return WrapAdapter()
    return WrapStub()


def run_sim(
    *,
    arm: str,
    ticks: int,
    seed: int,
    preset: str,
    out_dir: Path | None = None,
    run_id: str | None = None,
    llm: bool = False,
    skip_edges: set[str] | None = None,
) -> Path:
    rid = run_id or run_id_for(arm, seed, ticks, preset)
    dest = out_dir or (DATA_ROOT / rid)
    dest.mkdir(parents=True, exist_ok=True)
    events_path = dest / "events.jsonl"

    sealed_events: list[dict[str, Any]] = []
    if preset == "sealed":
        from wrap_ew2.sealed_loader import load_sealed

        sealed_events = list(load_sealed()["events"])

    world = make_world(seed)
    policy = build_policy(llm=llm)
    gate = build_gate(arm)

    with JsonlWriter(events_path) as writer:
        for tick in range(ticks):
            world.tick = tick
            world.bucket = tick // DAY_BUCKET
            world.regen_nodes()
            maybe_inject(world, sealed_events)
            for agent in world.agents_in_order():
                obs = observe(agent, world)
                intent = policy.choose(obs)
                world_slice = world.public_slice(agent.id)
                result = gate.evaluate(intent, world_slice, skip_edges=skip_edges)
                act: dict[str, Any] | None = None
                if result.decision == "act":
                    act = apply_intent(world, agent, intent)
                    if act is None:
                        # structurally empty act still records the attempt as act
                        act = intent.to_dict()
                update_after_act(agent, intent, result.decision)
                labels = [t.label for t in agent.recognized_threats]
                recognized = recognized_ids(labels, intent)
                stress_id = None
                if world.last_injection in {"P_PHISH", "S_MISINFO", "M_BREACH", "STOP_WORK"}:
                    if world.last_injection in recognized or world.tick == _inject_tick(world):
                        stress_id = world.last_injection
                if recognized and stress_id is None:
                    stress_id = recognized[0]
                event = build_event(
                    run_id=rid,
                    arm=arm,
                    seed=seed,
                    tick=tick,
                    bucket=world.bucket,
                    agent=agent.id,
                    intent=intent,
                    edges=result.as_dict(),
                    bypass=result.bypass,
                    decision=result.decision,
                    act=act if result.decision == "act" else None,
                    recognized=recognized,
                    stress_id=stress_id,
                    wrap_bound=result.wrap_bound,
                )
                event["off_charter"] = is_off_charter(intent) and result.decision == "act"
                writer.write(event)
            resolve_votes(world)

    events = _read_events(events_path)
    summary = score_events(events, extra_system=_system_from_gate(gate, events, world))
    summary["run_id"] = rid
    summary["arm"] = arm
    summary["seed"] = seed
    summary["ticks"] = ticks
    summary["preset"] = preset
    summary["stress_injected"] = sorted(world.stress_injected)
    summary["events_sha256"] = sha256_file(events_path)
    write_summary(dest / "summary.json", summary)
    _print_run_footer(summary)
    return dest


def _inject_tick(world: World) -> int:
    return world.tick


def _system_from_gate(gate: WrapAdapter | WrapStub, events: list[dict[str, Any]], world: World) -> dict[str, Any]:
    # wrap_admit is E1 Admit count, not containment. wrap_allow is final act.
    return {
        "wrap_admit": sum(1 for e in events if e.get("edges", {}).get("e1") == "Admit"),
        "wrap_allow": sum(1 for e in events if e.get("decision") == "act"),
        "wrap_reject": sum(1 for e in events if e.get("decision") == "refuse"),
        "wrap_bypass": sum(1 for e in events if e.get("bypass")),
        "bypass_rate": (
            sum(1 for e in events if e.get("bypass")) / len(events) if events else 0.0
        ),
        "stress_injected": sorted(world.stress_injected),
    }


def _read_events(path: Path) -> list[dict[str, Any]]:
    from wrap_ew2.telemetry import read_jsonl

    return read_jsonl(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _print_run_footer(summary: dict[str, Any]) -> None:
    system = summary["system"]
    print(
        f"run_id={summary['run_id']} arm={summary['arm']} "
        f"seed={summary.get('seed')} sha256={summary['events_sha256']}"
    )
    print(f"stress_injected={summary.get('stress_injected')}")
    print(f"P4={summary['P']['P4']} S3={summary['S']['S3']} M4={summary['M']['M4']}")
    print(f"wrap_admit={system['wrap_admit']} wrap_allow={system['wrap_allow']}")
    print(f"bypass_rate={system['bypass_rate']}")
    print("EW2 solved: False")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skip = {part.strip() for part in args.skip_edges.split(",") if part.strip()}
    run_sim(
        arm=args.arm,
        ticks=args.ticks,
        seed=args.seed,
        preset=args.preset,
        out_dir=args.out,
        run_id=args.run_id,
        llm=args.llm,
        skip_edges=skip or None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
