"""Operator-only sealed preset loader. Imported by runner, never by agent policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "wrap-ew2.sealed.v1"

PRESET_NAME = "ew2_black_swan.sealed.json"


def default_preset_path() -> Path:
    # wrap-ew2/src/wrap_ew2/sealed_loader.py -> wrap-ew2/presets/
    return Path(__file__).resolve().parents[2] / "presets" / PRESET_NAME


def load_sealed(path: Path | None = None) -> dict[str, Any]:
    target = path or default_preset_path()
    data = json.loads(target.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"unexpected sealed schema: {data.get('schema')}")
    if "events" not in data:
        raise ValueError("sealed preset missing events")
    return data
