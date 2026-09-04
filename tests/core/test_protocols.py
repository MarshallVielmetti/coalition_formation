from collections.abc import Mapping

from coalition_formation.core.actions import Action, NoOpAction
from coalition_formation.core.models import (
    Coalition,
    Observation,
    RobotSpec,
    TaskSpec,
    WorldState,
)
from coalition_formation.core.protocols import (
    AllocationPolicy,
    CoalitionFeasibility,
    CoalitionValue,
    CommunicationModel,
    Metrics,
    ObservationModel,
    TaskDynamics,
    Termination,
    TravelModel,
)
from coalition_formation.core.types import JsonObject, Point


class FeasibilityDouble:
    def is_feasible(
        self,
        task: TaskSpec,
        coalition: Coalition,
        robots: Mapping[str, RobotSpec],
    ) -> bool:
        return task.task_id == coalition.task_id and all(
            robot_id in robots for robot_id in coalition.robot_ids
        )


class ValueDouble:
    def evaluate(
        self,
        task: TaskSpec,
        coalition: Coalition,
        robots: Mapping[str, RobotSpec],
    ) -> float:
        return task.reward + len(robots)


class TravelDouble:
    def travel_time(self, origin: Point, destination: Point) -> float:
        return float(origin != destination)


class DynamicsDouble:
    def advance(
        self,
        task: TaskSpec,
        coalition: Coalition,
        progress: float,
        tick: int,
    ) -> float:
        return min(
            1.0,
            progress + tick * 0.0 + len(coalition.robot_ids) / max(1, task.workload),
        )


class ObservationDouble:
    def observe(self, world: WorldState, robot_id: str) -> Observation:
        return Observation(
            tick=world.tick,
            robots={robot_id: world.robots[robot_id]},
            tasks=world.tasks,
            coalitions=world.coalitions,
        )


class CommunicationDouble:
    def send(
        self,
        sender_id: str,
        recipient_id: str,
        payload: JsonObject,
        tick: int,
    ) -> bool:
        return bool(sender_id and recipient_id and payload is not None and tick >= 0)


class PolicyDouble:
    def propose(self, observation: Observation) -> Action:
        return NoOpAction(reason=f"tick {observation.tick}")


class MetricsDouble:
    def compute(self, world: WorldState) -> Mapping[str, float]:
        return {"tick": float(world.tick)}


class TerminationDouble:
    def should_terminate(self, world: WorldState) -> bool:
        return world.terminal_status is not None


def test_plugins_match_protocols_without_framework_subclassing() -> None:
    doubles_and_protocols = (
        (FeasibilityDouble(), CoalitionFeasibility),
        (ValueDouble(), CoalitionValue),
        (TravelDouble(), TravelModel),
        (DynamicsDouble(), TaskDynamics),
        (ObservationDouble(), ObservationModel),
        (CommunicationDouble(), CommunicationModel),
        (PolicyDouble(), AllocationPolicy),
        (MetricsDouble(), Metrics),
        (TerminationDouble(), Termination),
    )

    for double, protocol in doubles_and_protocols:
        assert isinstance(double, protocol)
