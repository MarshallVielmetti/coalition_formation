"""Structural extension points for domain and policy plugins."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from .actions import Action
from .models import Coalition, Observation, RobotSpec, TaskSpec, WorldState
from .types import JsonObject, Point


@runtime_checkable
class CoalitionFeasibility(Protocol):
    """Check whether a coalition can perform a task."""

    def is_feasible(
        self,
        task: TaskSpec,
        coalition: Coalition,
        robots: Mapping[str, RobotSpec],
    ) -> bool:
        """Return whether capability, size, and domain constraints hold."""


@runtime_checkable
class CoalitionValue(Protocol):
    """Evaluate a coalition-task pairing."""

    def evaluate(
        self,
        task: TaskSpec,
        coalition: Coalition,
        robots: Mapping[str, RobotSpec],
    ) -> float:
        """Return the domain value or productivity for the pairing."""


@runtime_checkable
class TravelModel(Protocol):
    """Estimate travel cost between two points."""

    def travel_time(self, origin: Point, destination: Point) -> float:
        """Return travel time in simulation ticks or fractional ticks."""


@runtime_checkable
class TaskDynamics(Protocol):
    """Advance task progress for a coalition at one tick."""

    def advance(
        self,
        task: TaskSpec,
        coalition: Coalition,
        progress: float,
        tick: int,
    ) -> float:
        """Return the next normalized progress value."""


@runtime_checkable
class ObservationModel(Protocol):
    """Convert complete state into a policy-facing observation."""

    def observe(self, world: WorldState, robot_id: str) -> Observation:
        """Return a full or partial immutable observation."""


@runtime_checkable
class CommunicationModel(Protocol):
    """Model one logical message delivery attempt."""

    def send(
        self,
        sender_id: str,
        recipient_id: str,
        payload: JsonObject,
        tick: int,
    ) -> bool:
        """Return whether the message was delivered."""


@runtime_checkable
class AllocationPolicy(Protocol):
    """Choose a typed allocation action from an immutable observation."""

    def propose(self, observation: Observation) -> Action:
        """Return one typed action or deliberate no-op."""


@runtime_checkable
class Metrics(Protocol):
    """Compute named domain metrics from runtime state."""

    def compute(self, world: WorldState) -> Mapping[str, float]:
        """Return separate named metrics rather than one combined score."""


@runtime_checkable
class Termination(Protocol):
    """Decide whether a run should terminate."""

    def should_terminate(self, world: WorldState) -> bool:
        """Return whether the current world is terminal."""
