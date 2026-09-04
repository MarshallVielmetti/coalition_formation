"""Immutable specifications and runtime value objects.

The models in this module deliberately contain validation and serialization
only. They do not advance time, perform allocation, or mutate other objects.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from numbers import Real
from types import MappingProxyType
from typing import TypeVar, cast

from .types import JsonObject, Point

T = TypeVar("T")


class TaskStatus(StrEnum):
    """Lifecycle status for a task."""

    PENDING = "pending"
    RELEASED = "released"
    ASSIGNED = "assigned"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RobotStatus(StrEnum):
    """Availability status for a robot."""

    IDLE = "idle"
    TRAVELING = "traveling"
    WORKING = "working"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class CoalitionStatus(StrEnum):
    """Lifecycle status for a task-oriented coalition."""

    PROPOSED = "proposed"
    FORMING = "forming"
    ACTIVE = "active"
    DISBANDED = "disbanded"
    FAILED = "failed"


class TerminalStatus(StrEnum):
    """Terminal status for a simulation or mission."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


def _require_id(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_label(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _as_float(value: object, field_name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    if minimum is not None and result < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}")
    return result


def _as_tick(value: object, field_name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer tick")
    if value < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}")
    return value


def _as_count(value: object, field_name: str, *, minimum: int = 1) -> int:
    return _as_tick(value, field_name, minimum=minimum)


def _freeze_nonnegative_mapping(
    values: Mapping[str, float], field_name: str
) -> Mapping[str, float]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    normalized: dict[str, float] = {}
    for key, value in values.items():
        _require_label(key, f"{field_name} key")
        normalized[key] = _as_float(value, f"{field_name}[{key!r}]", minimum=0.0)
    return cast(Mapping[str, float], MappingProxyType(dict(sorted(normalized.items()))))


def _freeze_ids(
    values: Iterable[str], field_name: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{field_name} must be an iterable of IDs")
    normalized = tuple(values)
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must not be empty")
    for value in normalized:
        _require_id(value, f"{field_name} member")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicate IDs")
    return tuple(sorted(normalized))


def _freeze_point(value: Point | None, field_name: str) -> Point | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a two-dimensional point")
    coordinates = tuple(value)
    if len(coordinates) != 2:
        raise ValueError(f"{field_name} must have exactly two coordinates")
    return (
        _as_float(coordinates[0], f"{field_name}[0]"),
        _as_float(coordinates[1], f"{field_name}[1]"),
    )


def _freeze_entities(
    values: Mapping[str, T], field_name: str, identifier: Callable[[T], str]
) -> Mapping[str, T]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    normalized: dict[str, T] = {}
    for key, value in values.items():
        _require_id(key, f"{field_name} key")
        if identifier(value) != key:
            raise ValueError(f"{field_name} key {key!r} does not match entity ID")
        normalized[key] = value
    return cast(Mapping[str, T], MappingProxyType(dict(sorted(normalized.items()))))


def _mapping(data: Mapping[str, object], key: str) -> Mapping[str, float]:
    value = data.get(key, {})
    if not isinstance(value, Mapping):
        raise TypeError(f"{key} must be a mapping")
    return cast(Mapping[str, float], value)


def _object_sequence(
    data: Mapping[str, object], key: str
) -> tuple[Mapping[str, object], ...]:
    value = data.get(key, [])
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{key} must be a sequence")
    result: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError(f"{key} members must be mappings")
        result.append(cast(Mapping[str, object], item))
    return tuple(result)


def _optional_point(data: Mapping[str, object], key: str) -> Point | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{key} must be a two-dimensional point or null")
    return cast(Point, tuple(cast(float, coordinate) for coordinate in value))


def _optional_time_window(data: Mapping[str, object]) -> TimeWindow | None:
    value = data.get("time_window")
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("time_window must be a mapping or null")
    return TimeWindow.from_dict(cast(Mapping[str, object], value))


def _optional_terminal_status(data: Mapping[str, object]) -> TerminalStatus | None:
    value = data.get("terminal_status")
    if value is None:
        return None
    return TerminalStatus(cast(str, value))


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """A half-open inclusive/exclusive interval of integer simulation ticks."""

    start_tick: int
    end_tick: int

    def __post_init__(self) -> None:
        start_tick = _as_tick(self.start_tick, "start_tick")
        end_tick = _as_tick(self.end_tick, "end_tick")
        if end_tick <= start_tick:
            raise ValueError("end_tick must be greater than start_tick")
        object.__setattr__(self, "start_tick", start_tick)
        object.__setattr__(self, "end_tick", end_tick)

    def to_dict(self) -> JsonObject:
        return {"start_tick": self.start_tick, "end_tick": self.end_tick}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> TimeWindow:
        return cls(
            start_tick=cast(int, data["start_tick"]),
            end_tick=cast(int, data["end_tick"]),
        )


@dataclass(frozen=True, slots=True)
class Dependency:
    """A directed precedence edge between two task IDs."""

    predecessor_id: str
    successor_id: str

    def __post_init__(self) -> None:
        _require_id(self.predecessor_id, "predecessor_id")
        _require_id(self.successor_id, "successor_id")
        if self.predecessor_id == self.successor_id:
            raise ValueError("a dependency cannot point from a task to itself")

    def to_dict(self) -> JsonObject:
        return {
            "predecessor_id": self.predecessor_id,
            "successor_id": self.successor_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Dependency:
        return cls(
            predecessor_id=cast(str, data["predecessor_id"]),
            successor_id=cast(str, data["successor_id"]),
        )


@dataclass(frozen=True, slots=True)
class RobotSpec:
    """Immutable static specification for one robot.

    Positions use scenario units, speed uses units per tick, and capability
    and resource quantities are nonnegative domain-specific amounts.
    """

    robot_id: str
    robot_type: str = "generic"
    capabilities: Mapping[str, float] = field(default_factory=dict)
    resources: Mapping[str, float] = field(default_factory=dict)
    position: Point | None = None
    speed: float = 1.0
    max_concurrent_tasks: int = 1

    def __post_init__(self) -> None:
        _require_id(self.robot_id, "robot_id")
        _require_label(self.robot_type, "robot_type")
        object.__setattr__(
            self,
            "capabilities",
            _freeze_nonnegative_mapping(self.capabilities, "capabilities"),
        )
        object.__setattr__(
            self, "resources", _freeze_nonnegative_mapping(self.resources, "resources")
        )
        object.__setattr__(self, "position", _freeze_point(self.position, "position"))
        object.__setattr__(self, "speed", _as_float(self.speed, "speed", minimum=0.0))
        object.__setattr__(
            self,
            "max_concurrent_tasks",
            _as_count(self.max_concurrent_tasks, "max_concurrent_tasks"),
        )

    def to_dict(self) -> JsonObject:
        return {
            "robot_id": self.robot_id,
            "robot_type": self.robot_type,
            "capabilities": dict(self.capabilities),
            "resources": dict(self.resources),
            "position": list(self.position) if self.position is not None else None,
            "speed": self.speed,
            "max_concurrent_tasks": self.max_concurrent_tasks,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> RobotSpec:
        return cls(
            robot_id=cast(str, data["robot_id"]),
            robot_type=cast(str, data.get("robot_type", "generic")),
            capabilities=_mapping(data, "capabilities"),
            resources=_mapping(data, "resources"),
            position=_optional_point(data, "position"),
            speed=cast(float, data.get("speed", 1.0)),
            max_concurrent_tasks=cast(int, data.get("max_concurrent_tasks", 1)),
        )


@dataclass(frozen=True, slots=True)
class TaskSpec:
    """Immutable static specification for one task."""

    task_id: str
    task_type: str = "generic"
    requirements: Mapping[str, float] = field(default_factory=dict)
    resource_requirements: Mapping[str, float] = field(default_factory=dict)
    location: Point | None = None
    release_tick: int = 0
    time_window: TimeWindow | None = None
    workload: float = 1.0
    reward: float = 0.0
    min_coalition_size: int = 1
    max_coalition_size: int | None = None

    def __post_init__(self) -> None:
        _require_id(self.task_id, "task_id")
        _require_label(self.task_type, "task_type")
        object.__setattr__(
            self,
            "requirements",
            _freeze_nonnegative_mapping(self.requirements, "requirements"),
        )
        object.__setattr__(
            self,
            "resource_requirements",
            _freeze_nonnegative_mapping(
                self.resource_requirements, "resource_requirements"
            ),
        )
        object.__setattr__(self, "location", _freeze_point(self.location, "location"))
        object.__setattr__(
            self, "release_tick", _as_tick(self.release_tick, "release_tick")
        )
        object.__setattr__(
            self, "workload", _as_float(self.workload, "workload", minimum=0.0)
        )
        object.__setattr__(self, "reward", _as_float(self.reward, "reward"))
        object.__setattr__(
            self,
            "min_coalition_size",
            _as_count(self.min_coalition_size, "min_coalition_size"),
        )
        if self.max_coalition_size is not None:
            max_size = _as_count(self.max_coalition_size, "max_coalition_size")
            if max_size < self.min_coalition_size:
                raise ValueError(
                    "max_coalition_size must be at least min_coalition_size"
                )
            object.__setattr__(self, "max_coalition_size", max_size)
        if (
            self.time_window is not None
            and self.release_tick >= self.time_window.end_tick
        ):
            raise ValueError("release_tick must be before the time-window end")

    def to_dict(self) -> JsonObject:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "requirements": dict(self.requirements),
            "resource_requirements": dict(self.resource_requirements),
            "location": list(self.location) if self.location is not None else None,
            "release_tick": self.release_tick,
            "time_window": self.time_window.to_dict() if self.time_window else None,
            "workload": self.workload,
            "reward": self.reward,
            "min_coalition_size": self.min_coalition_size,
            "max_coalition_size": self.max_coalition_size,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> TaskSpec:
        return cls(
            task_id=cast(str, data["task_id"]),
            task_type=cast(str, data.get("task_type", "generic")),
            requirements=_mapping(data, "requirements"),
            resource_requirements=_mapping(data, "resource_requirements"),
            location=_optional_point(data, "location"),
            release_tick=cast(int, data.get("release_tick", 0)),
            time_window=_optional_time_window(data),
            workload=cast(float, data.get("workload", 1.0)),
            reward=cast(float, data.get("reward", 0.0)),
            min_coalition_size=cast(int, data.get("min_coalition_size", 1)),
            max_coalition_size=cast(int | None, data.get("max_coalition_size")),
        )


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    """Immutable collection of robots, tasks, and validated dependencies."""

    scenario_id: str
    robots: tuple[RobotSpec, ...] = ()
    tasks: tuple[TaskSpec, ...] = ()
    dependencies: tuple[Dependency, ...] = ()
    scenario_type: str = "generic"
    schema_version: str = "1.0"
    horizon: int | None = None

    def __post_init__(self) -> None:
        _require_id(self.scenario_id, "scenario_id")
        _require_label(self.scenario_type, "scenario_type")
        _require_label(self.schema_version, "schema_version")
        robots = tuple(sorted(self.robots, key=lambda robot: robot.robot_id))
        tasks = tuple(sorted(self.tasks, key=lambda task: task.task_id))
        robot_ids = [robot.robot_id for robot in robots]
        task_ids = [task.task_id for task in tasks]
        if len(set(robot_ids)) != len(robot_ids):
            raise ValueError("robots must not contain duplicate IDs")
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("tasks must not contain duplicate IDs")
        task_id_set = set(task_ids)
        dependencies = tuple(
            sorted(
                self.dependencies,
                key=lambda dependency: (
                    dependency.predecessor_id,
                    dependency.successor_id,
                ),
            )
        )
        dependency_pairs = [
            (dependency.predecessor_id, dependency.successor_id)
            for dependency in dependencies
        ]
        if len(set(dependency_pairs)) != len(dependency_pairs):
            raise ValueError("dependencies must not contain duplicate edges")
        for dependency in dependencies:
            if (
                dependency.predecessor_id not in task_id_set
                or dependency.successor_id not in task_id_set
            ):
                raise ValueError("dependency endpoints must reference known task IDs")
        if self.horizon is not None:
            object.__setattr__(self, "horizon", _as_tick(self.horizon, "horizon"))
        object.__setattr__(self, "robots", robots)
        object.__setattr__(self, "tasks", tasks)
        object.__setattr__(self, "dependencies", dependencies)

    def to_dict(self) -> JsonObject:
        return {
            "scenario_id": self.scenario_id,
            "scenario_type": self.scenario_type,
            "schema_version": self.schema_version,
            "horizon": self.horizon,
            "robots": [robot.to_dict() for robot in self.robots],
            "tasks": [task.to_dict() for task in self.tasks],
            "dependencies": [dependency.to_dict() for dependency in self.dependencies],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ScenarioSpec:
        return cls(
            scenario_id=cast(str, data["scenario_id"]),
            scenario_type=cast(str, data.get("scenario_type", "generic")),
            schema_version=cast(str, data.get("schema_version", "1.0")),
            horizon=cast(int | None, data.get("horizon")),
            robots=tuple(
                RobotSpec.from_dict(item) for item in _object_sequence(data, "robots")
            ),
            tasks=tuple(
                TaskSpec.from_dict(item) for item in _object_sequence(data, "tasks")
            ),
            dependencies=tuple(
                Dependency.from_dict(item)
                for item in _object_sequence(data, "dependencies")
            ),
        )


@dataclass(frozen=True, slots=True)
class RobotState:
    """Immutable runtime snapshot for one robot."""

    robot_id: str
    status: RobotStatus = RobotStatus.IDLE
    position: Point | None = None
    resources: Mapping[str, float] = field(default_factory=dict)
    coalition_ids: tuple[str, ...] = ()
    assigned_task_ids: tuple[str, ...] = ()
    health: float = 1.0
    available_tick: int = 0

    def __post_init__(self) -> None:
        _require_id(self.robot_id, "robot_id")
        object.__setattr__(self, "status", RobotStatus(self.status))
        object.__setattr__(self, "position", _freeze_point(self.position, "position"))
        object.__setattr__(
            self, "resources", _freeze_nonnegative_mapping(self.resources, "resources")
        )
        object.__setattr__(
            self, "coalition_ids", _freeze_ids(self.coalition_ids, "coalition_ids")
        )
        object.__setattr__(
            self,
            "assigned_task_ids",
            _freeze_ids(self.assigned_task_ids, "assigned_task_ids"),
        )
        object.__setattr__(
            self, "health", _as_float(self.health, "health", minimum=0.0)
        )
        object.__setattr__(
            self, "available_tick", _as_tick(self.available_tick, "available_tick")
        )

    def to_dict(self) -> JsonObject:
        return {
            "robot_id": self.robot_id,
            "status": self.status.value,
            "position": list(self.position) if self.position is not None else None,
            "resources": dict(self.resources),
            "coalition_ids": list(self.coalition_ids),
            "assigned_task_ids": list(self.assigned_task_ids),
            "health": self.health,
            "available_tick": self.available_tick,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> RobotState:
        coalition_ids = data.get("coalition_ids", [])
        assigned_task_ids = data.get("assigned_task_ids", [])
        if isinstance(coalition_ids, (str, bytes)) or not isinstance(
            coalition_ids, Sequence
        ):
            raise TypeError("coalition_ids must be a sequence")
        if isinstance(assigned_task_ids, (str, bytes)) or not isinstance(
            assigned_task_ids, Sequence
        ):
            raise TypeError("assigned_task_ids must be a sequence")
        return cls(
            robot_id=cast(str, data["robot_id"]),
            status=RobotStatus(cast(str, data.get("status", RobotStatus.IDLE.value))),
            position=_optional_point(data, "position"),
            resources=_mapping(data, "resources"),
            coalition_ids=tuple(cast(str, item) for item in coalition_ids),
            assigned_task_ids=tuple(cast(str, item) for item in assigned_task_ids),
            health=cast(float, data.get("health", 1.0)),
            available_tick=cast(int, data.get("available_tick", 0)),
        )


@dataclass(frozen=True, slots=True)
class TaskState:
    """Immutable runtime snapshot for one task."""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    assigned_coalition_id: str | None = None
    completion_tick: int | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        _require_id(self.task_id, "task_id")
        object.__setattr__(self, "status", TaskStatus(self.status))
        object.__setattr__(
            self, "progress", _as_float(self.progress, "progress", minimum=0.0)
        )
        if self.progress > 1.0:
            raise ValueError("progress must be at most 1.0")
        if self.assigned_coalition_id is not None:
            _require_id(self.assigned_coalition_id, "assigned_coalition_id")
        if self.completion_tick is not None:
            object.__setattr__(
                self,
                "completion_tick",
                _as_tick(self.completion_tick, "completion_tick"),
            )
        if self.failure_reason is not None:
            _require_label(self.failure_reason, "failure_reason")

    def to_dict(self) -> JsonObject:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "assigned_coalition_id": self.assigned_coalition_id,
            "completion_tick": self.completion_tick,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> TaskState:
        return cls(
            task_id=cast(str, data["task_id"]),
            status=TaskStatus(cast(str, data.get("status", TaskStatus.PENDING.value))),
            progress=cast(float, data.get("progress", 0.0)),
            assigned_coalition_id=cast(str | None, data.get("assigned_coalition_id")),
            completion_tick=cast(int | None, data.get("completion_tick")),
            failure_reason=cast(str | None, data.get("failure_reason")),
        )


@dataclass(frozen=True, slots=True)
class Coalition:
    """Immutable task-oriented group of robot IDs."""

    coalition_id: str
    task_id: str
    robot_ids: tuple[str, ...]
    status: CoalitionStatus = CoalitionStatus.PROPOSED
    formed_tick: int | None = None
    value: float = 0.0

    def __post_init__(self) -> None:
        _require_id(self.coalition_id, "coalition_id")
        _require_id(self.task_id, "task_id")
        object.__setattr__(self, "status", CoalitionStatus(self.status))
        object.__setattr__(
            self,
            "robot_ids",
            _freeze_ids(self.robot_ids, "robot_ids", allow_empty=False),
        )
        if self.formed_tick is not None:
            object.__setattr__(
                self, "formed_tick", _as_tick(self.formed_tick, "formed_tick")
            )
        object.__setattr__(self, "value", _as_float(self.value, "value"))

    def to_dict(self) -> JsonObject:
        return {
            "coalition_id": self.coalition_id,
            "task_id": self.task_id,
            "robot_ids": list(self.robot_ids),
            "status": self.status.value,
            "formed_tick": self.formed_tick,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Coalition:
        robot_ids = data["robot_ids"]
        if isinstance(robot_ids, (str, bytes)) or not isinstance(robot_ids, Sequence):
            raise TypeError("robot_ids must be a sequence")
        return cls(
            coalition_id=cast(str, data["coalition_id"]),
            task_id=cast(str, data["task_id"]),
            robot_ids=tuple(cast(str, item) for item in robot_ids),
            status=CoalitionStatus(
                cast(str, data.get("status", CoalitionStatus.PROPOSED.value))
            ),
            formed_tick=cast(int | None, data.get("formed_tick")),
            value=cast(float, data.get("value", 0.0)),
        )


@dataclass(frozen=True, slots=True)
class WorldState:
    """Immutable complete runtime snapshot owned by the simulation kernel."""

    tick: int = 0
    robots: Mapping[str, RobotState] = field(default_factory=dict)
    tasks: Mapping[str, TaskState] = field(default_factory=dict)
    coalitions: Mapping[str, Coalition] = field(default_factory=dict)
    terminal_status: TerminalStatus | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick", _as_tick(self.tick, "tick"))
        if self.terminal_status is not None:
            object.__setattr__(
                self, "terminal_status", TerminalStatus(self.terminal_status)
            )
        object.__setattr__(
            self,
            "robots",
            _freeze_entities(self.robots, "robots", lambda robot: robot.robot_id),
        )
        object.__setattr__(
            self,
            "tasks",
            _freeze_entities(self.tasks, "tasks", lambda task: task.task_id),
        )
        object.__setattr__(
            self,
            "coalitions",
            _freeze_entities(
                self.coalitions, "coalitions", lambda coalition: coalition.coalition_id
            ),
        )

    def to_dict(self) -> JsonObject:
        return {
            "tick": self.tick,
            "robots": {key: value.to_dict() for key, value in self.robots.items()},
            "tasks": {key: value.to_dict() for key, value in self.tasks.items()},
            "coalitions": {
                key: value.to_dict() for key, value in self.coalitions.items()
            },
            "terminal_status": self.terminal_status.value
            if self.terminal_status
            else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> WorldState:
        robot_data = data.get("robots", {})
        task_data = data.get("tasks", {})
        coalition_data = data.get("coalitions", {})
        if not isinstance(robot_data, Mapping):
            raise TypeError("robots must be a mapping")
        if not isinstance(task_data, Mapping):
            raise TypeError("tasks must be a mapping")
        if not isinstance(coalition_data, Mapping):
            raise TypeError("coalitions must be a mapping")
        return cls(
            tick=cast(int, data.get("tick", 0)),
            robots={
                cast(str, key): RobotState.from_dict(cast(Mapping[str, object], value))
                for key, value in robot_data.items()
            },
            tasks={
                cast(str, key): TaskState.from_dict(cast(Mapping[str, object], value))
                for key, value in task_data.items()
            },
            coalitions={
                cast(str, key): Coalition.from_dict(cast(Mapping[str, object], value))
                for key, value in coalition_data.items()
            },
            terminal_status=_optional_terminal_status(data),
        )


@dataclass(frozen=True, slots=True)
class Observation:
    """Immutable policy-facing snapshot, possibly containing partial state."""

    tick: int = 0
    robots: Mapping[str, RobotState] = field(default_factory=dict)
    tasks: Mapping[str, TaskState] = field(default_factory=dict)
    coalitions: Mapping[str, Coalition] = field(default_factory=dict)
    terminal_status: TerminalStatus | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick", _as_tick(self.tick, "tick"))
        if self.terminal_status is not None:
            object.__setattr__(
                self, "terminal_status", TerminalStatus(self.terminal_status)
            )
        object.__setattr__(
            self,
            "robots",
            _freeze_entities(self.robots, "robots", lambda robot: robot.robot_id),
        )
        object.__setattr__(
            self,
            "tasks",
            _freeze_entities(self.tasks, "tasks", lambda task: task.task_id),
        )
        object.__setattr__(
            self,
            "coalitions",
            _freeze_entities(
                self.coalitions, "coalitions", lambda coalition: coalition.coalition_id
            ),
        )

    @classmethod
    def from_world_state(cls, state: WorldState) -> Observation:
        return cls(
            tick=state.tick,
            robots=state.robots,
            tasks=state.tasks,
            coalitions=state.coalitions,
            terminal_status=state.terminal_status,
        )

    def to_dict(self) -> JsonObject:
        return {
            "tick": self.tick,
            "robots": {key: value.to_dict() for key, value in self.robots.items()},
            "tasks": {key: value.to_dict() for key, value in self.tasks.items()},
            "coalitions": {
                key: value.to_dict() for key, value in self.coalitions.items()
            },
            "terminal_status": self.terminal_status.value
            if self.terminal_status
            else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Observation:
        state = WorldState.from_dict(data)
        return cls.from_world_state(state)
