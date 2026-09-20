"""JSONL SHA compare. IDENTICAL stops the seed-diversity claim.

Not a scorecard. Do not invent P/S/M cells. EW2 solved stays False.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from wrap_ew2.scoring import load_run


def events_jsonl_path(path: Path) -> Path:
    return path / "events.jsonl" if path.is_dir() else path


def events_sha256(path: Path) -> str:
    """SHA-256 of the raw events.jsonl bytes."""
    return hashlib.sha256(events_jsonl_path(path).read_bytes()).hexdigest()


def event_kind(event: dict[str, Any]) -> str:
    """JSONL rows have no top-level kind. Use intent.op, else stress_id."""
    intent = event.get("intent") or {}
    op = intent.get("op")
    if op:
        return str(op)
    stress = event.get("stress_id")
    if stress:
        return str(stress)
    return "unknown"


def _mismatch_row(
    index: int,
    event_a: dict[str, Any] | None,
    event_b: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "index": index,
        "tick_a": int(event_a["tick"]) if event_a is not None else None,
        "tick_b": int(event_b["tick"]) if event_b is not None else None,
        "kind_a": event_kind(event_a) if event_a is not None else None,
        "kind_b": event_kind(event_b) if event_b is not None else None,
    }


def first_differing_event(
    events_a: list[dict[str, Any]], events_b: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """First event object that is not equal. Reports that row's tick + kind."""
    n = min(len(events_a), len(events_b))
    for i in range(n):
        if events_a[i] != events_b[i]:
            return _mismatch_row(i, events_a[i], events_b[i])
    if len(events_a) != len(events_b):
        return _mismatch_row(
            n,
            events_a[n] if n < len(events_a) else None,
            events_b[n] if n < len(events_b) else None,
        )
    return None


def first_tick_kind_mismatch(
    events_a: list[dict[str, Any]], events_b: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """First index where tick or kind differs. None if those sequences match."""
    n = min(len(events_a), len(events_b))
    for i in range(n):
        ea = events_a[i]
        eb = events_b[i]
        ta = int(ea.get("tick", -1))
        tb = int(eb.get("tick", -1))
        ka = event_kind(ea)
        kb = event_kind(eb)
        if ta != tb or ka != kb:
            return {
                "index": i,
                "tick_a": ta,
                "tick_b": tb,
                "kind_a": ka,
                "kind_b": kb,
            }
    if len(events_a) != len(events_b):
        return _mismatch_row(
            n,
            events_a[n] if n < len(events_a) else None,
            events_b[n] if n < len(events_b) else None,
        )
    return None


def compare_jsonl_traces(path_a: Path, path_b: Path) -> dict[str, Any]:
    """Compare two JSONL traces. IDENTICAL means stop; do not claim diversity."""
    sha_a = events_sha256(path_a)
    sha_b = events_sha256(path_b)
    if sha_a == sha_b:
        return {
            "status": "IDENTICAL",
            "sha_a": sha_a,
            "sha_b": sha_b,
            "mismatch": None,
            "first_event": None,
        }
    events_a = load_run(path_a)
    events_b = load_run(path_b)
    return {
        "status": "DIFF",
        "sha_a": sha_a,
        "sha_b": sha_b,
        "mismatch": first_tick_kind_mismatch(events_a, events_b),
        "first_event": first_differing_event(events_a, events_b),
    }


def format_trace_diff(pair: str, result: dict[str, Any]) -> str:
    if result["status"] == "IDENTICAL":
        return f"{pair}: IDENTICAL sha={result['sha_a']}"
    lines = [
        f"{pair}: DIFF",
        f"sha_a={result['sha_a']}",
        f"sha_b={result['sha_b']}",
    ]
    first = result.get("first_event")
    if first is None:
        lines.append("first differing event kind+tick: none")
    else:
        lines.append(
            "first differing event kind+tick: "
            f"tick_a={first['tick_a']} kind_a={first['kind_a']} "
            f"tick_b={first['tick_b']} kind_b={first['kind_b']}"
        )
    mismatch = result.get("mismatch")
    if mismatch is None:
        lines.append("first tick/kind mismatch: none")
    else:
        lines.append(
            "first tick/kind mismatch: "
            f"tick_a={mismatch['tick_a']} kind_a={mismatch['kind_a']} "
            f"tick_b={mismatch['tick_b']} kind_b={mismatch['kind_b']}"
        )
    return "\n".join(lines)


def print_pair_or_stop(pair: str, result: dict[str, Any]) -> str:
    """Print the compare line. IDENTICAL is the stop signal; caller must fail."""
    line = format_trace_diff(pair, result)
    print(line)
    return line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare WRAP-EW2 JSONL hashes. IDENTICAL stops diversity claims."
    )
    parser.add_argument("--a", required=True, type=Path, help="run dir A or events.jsonl")
    parser.add_argument("--b", required=True, type=Path, help="run dir B or events.jsonl")
    parser.add_argument("--pair", default="", help="label such as 42vs7")
    args = parser.parse_args(argv)
    pair = args.pair or f"{args.a.name}vs{args.b.name}"
    result = compare_jsonl_traces(args.a, args.b)
    print_pair_or_stop(pair, result)
    if result["status"] == "IDENTICAL":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
