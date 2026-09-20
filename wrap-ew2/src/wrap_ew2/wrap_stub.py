"""Unwrapped passthrough. All four edges return Admit/Pass/Allow. Wrap did not bind."""

from __future__ import annotations

from typing import Any

from wrap_ew2.actions import Intent
from wrap_ew2.wrap_adapter import EdgeResult


class WrapStub:
    bypass_count: int = 0
    admit_count: int = 0
    reject_count: int = 0

    def admit_or_block(self, intent: Intent, world_slice: dict[str, Any]) -> str:
        _ = intent, world_slice
        return "Admit"

    def conductor_threshold(self, intent: Intent) -> str:
        _ = intent
        return "Pass"

    def tolc_projector(self, intent: Intent, world_slice: dict[str, Any] | None = None) -> str:
        _ = intent, world_slice
        return "Pass"

    def circuit(self, intent: Intent, history: list[str] | None = None) -> str:
        _ = intent, history
        return "Allow"

    def evaluate(
        self,
        intent: Intent,
        world_slice: dict[str, Any],
        skip_edges: set[str] | None = None,
    ) -> EdgeResult:
        skip = skip_edges or set()
        called = {"e1": False, "e2": False, "e3": False, "e4": False}
        if "e1" not in skip:
            self.admit_or_block(intent, world_slice)
            called["e1"] = True
        if "e2" not in skip:
            self.conductor_threshold(intent)
            called["e2"] = True
        if "e3" not in skip:
            self.tolc_projector(intent, world_slice)
            called["e3"] = True
        if "e4" not in skip:
            self.circuit(intent)
            called["e4"] = True
        bypass = not all(called.values())
        if bypass:
            self.bypass_count += 1
        else:
            self.admit_count += 1
        return EdgeResult(
            e1="Admit",
            e2="Pass",
            e3="Pass",
            e4="Allow",
            bypass=bypass,
            called=called,
            decision="act",
            wrap_bound=False,
        )
