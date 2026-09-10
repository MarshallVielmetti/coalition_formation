"""Bounded exact set packing for simultaneous static allocations."""

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from typing import TypeAlias

from .core.models import ScenarioSpec
from .core.types import JsonObject

Partition: TypeAlias = tuple[tuple[str, tuple[str, ...]], ...]


class OracleLimitError(ValueError):
    """The instance exceeds the documented exhaustive-search budget."""


@dataclass(frozen=True)
class OracleResult:
    optimal_reward: float
    optimal_partitions: tuple[Partition, ...]
    explored_states: int

    def to_dict(self) -> JsonObject:
        return {
            "optimal_reward": self.optimal_reward,
            "optimal_partitions": [
                [
                    {"task_id": task, "robot_ids": list(robots)}
                    for task, robots in partition
                ]
                for partition in self.optimal_partitions
            ],
            "explored_states": self.explored_states,
        }


def solve_static(scenario: ScenarioSpec, *, max_states: int = 100_000) -> OracleResult:
    """Enumerate all optimal disjoint allocations, allowing unassigned tasks.

    At most 10 robots and 8 tasks; at most max_states recursive visits.
    Rewards are summed exactly as binary-float Fractions for tie comparison.
    This is not a scheduling oracle: robots cannot be reused between tasks.
    """
    if (
        isinstance(max_states, bool)
        or not isinstance(max_states, int)
        or max_states < 1
    ):
        raise ValueError("max_states must be a positive integer")
    if len(scenario.robots) > 10 or len(scenario.tasks) > 8:
        raise OracleLimitError("static oracle supports at most 10 robots and 8 tasks")
    if (
        scenario.dependencies
        or scenario.horizon is not None
        or any(t.release_tick or t.time_window or t.location for t in scenario.tasks)
        or any(r.max_concurrent_tasks != 1 for r in scenario.robots)
    ):
        raise ValueError("oracle requires simultaneous static, single-task robots")
    robots = {r.robot_id: r for r in scenario.robots}
    candidates: list[list[tuple[str, ...]]] = []
    for task in scenario.tasks:
        feasible = []
        for size in range(
            task.min_coalition_size,
            min(task.max_coalition_size or len(robots), len(robots)) + 1,
        ):
            for ids in combinations(robots, size):
                if any(
                    set(robots[r].incompatible_robot_ids).intersection(ids) for r in ids
                ):
                    continue
                if all(
                    sum(robots[r].capabilities.get(k, 0) for r in ids) >= v
                    for k, v in task.requirements.items()
                ) and all(
                    sum(robots[r].resources.get(k, 0) for r in ids) >= v
                    for k, v in task.resource_requirements.items()
                ):
                    feasible.append(ids)
        candidates.append(sorted(feasible))
    best = Fraction(0)
    winners: list[Partition] = []
    explored = 0

    def visit(
        index: int, used: frozenset[str], reward: Fraction, partition: Partition
    ) -> None:
        nonlocal best, winners, explored
        explored += 1
        if explored > max_states:
            raise OracleLimitError(f"static oracle exceeded {max_states} search states")
        if index == len(scenario.tasks):
            if reward > best:
                best, winners = reward, [partition]
            elif reward == best:
                winners.append(partition)
            return
        visit(index + 1, used, reward, partition)
        task = scenario.tasks[index]
        for ids in candidates[index]:
            if used.isdisjoint(ids):
                visit(
                    index + 1,
                    used.union(ids),
                    reward + Fraction(task.reward),
                    (*partition, (task.task_id, ids)),
                )

    visit(0, frozenset(), Fraction(0), ())
    return OracleResult(float(best), tuple(sorted(winners)), explored)
