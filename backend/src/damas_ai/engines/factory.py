"""Create adapters from configuration."""

from __future__ import annotations

from damas_ai.config import EngineConfig
from damas_ai.engines.base import EngineAdapter
from damas_ai.engines.hub.adapter import HubEngine
from damas_ai.rules import RULESETS

KNOWN_VARIANTS = frozenset(r.variant for r in RULESETS.values())


def create_engine(config: EngineConfig) -> EngineAdapter:
    if config.native_variant not in KNOWN_VARIANTS:
        raise ValueError(
            f"{config.id}: native_variant {config.native_variant!r} has no Rules Core ruleset "
            f"(known: {sorted(KNOWN_VARIANTS)}); its moves could not be validated (ADR-001)"
        )
    if config.protocol == "hub":
        return HubEngine(config)
    if config.protocol == "cb-dll":
        raise NotImplementedError("CheckerBoard DLL engines are out of scope (ADR-005 option A)")
    raise NotImplementedError(f"protocol {config.protocol!r} is not an analysis protocol (DXP: G12)")
