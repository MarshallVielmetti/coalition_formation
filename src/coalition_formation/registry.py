"""Explicit scenario registry and construction APIs."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from .config import ResolvedConfig
from .core.models import ScenarioSpec
from .rng import RandomStreams

ScenarioFactory: TypeAlias = Callable[[ResolvedConfig, RandomStreams], ScenarioSpec]


class ScenarioRegistry:
    """Ordered registry backed by explicitly registered scenario factories."""

    def __init__(self) -> None:
        self._factories: dict[str, ScenarioFactory] = {}

    def register(self, name: str, factory: ScenarioFactory) -> None:
        """Register one factory, rejecting duplicate or invalid names."""

        if not isinstance(name, str) or not name:
            raise ValueError("scenario name must be a non-empty string")
        if name in self._factories:
            raise ValueError(f"scenario {name!r} is already registered")
        self._factories[name] = factory

    def names(self) -> tuple[str, ...]:
        """Return names in explicit registration order."""

        return tuple(self._factories)

    def create(
        self, name: str, config: ResolvedConfig, streams: RandomStreams
    ) -> ScenarioSpec:
        """Construct a registered scenario without discovery side effects."""

        try:
            factory = self._factories[name]
        except KeyError:
            available = ", ".join(self.names()) or "none"
            raise KeyError(
                f"unknown scenario {name!r}; available scenarios: {available}"
            ) from None
        return factory(config, streams)


def default_registry() -> ScenarioRegistry:
    """Build the default registry through explicit factory registrations."""

    from .scenarios.static_capability import (
        static_capability_incompatibility,
        static_capability_redundancy,
        static_capability_scarcity,
        static_capability_seeded_random,
        static_capability_small,
        static_capability_tied_optimum,
        static_capability_tiny,
    )

    registry = ScenarioRegistry()
    for name, factory in (
        ("static_capability/tiny", static_capability_tiny),
        ("static_capability/small", static_capability_small),
        ("static_capability/random", static_capability_seeded_random),
        ("static_capability/scarcity", static_capability_scarcity),
        ("static_capability/redundancy", static_capability_redundancy),
        ("static_capability/incompatibility", static_capability_incompatibility),
        ("static_capability/tied_optimum", static_capability_tied_optimum),
    ):
        registry.register(name, factory)
    return registry


def list_scenarios(registry: ScenarioRegistry | None = None) -> tuple[str, ...]:
    """List scenario names through a CLI-independent API."""

    return (registry or default_registry()).names()


def construct_scenario(
    config: ResolvedConfig, registry: ScenarioRegistry | None = None
) -> ScenarioSpec:
    """Construct a scenario from resolved configuration and named streams."""

    active_registry = registry or default_registry()
    streams = RandomStreams(config.seed, config.policy_seed)
    return active_registry.create(config.scenario, config, streams)
