"""Deterministic allocation-only simulation kernel."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from math import isfinite
from pathlib import Path
from typing import cast

from .actions import (
    Action,
    DisbandCoalitionAction,
    FormCoalitionAction,
    NoOpAction,
)
from .models import (
    Coalition,
    CoalitionStatus,
    Observation,
    RobotSpec,
    RobotState,
    RobotStatus,
    ScenarioSpec,
    TaskSpec,
    TaskState,
    TaskStatus,
    TerminalStatus,
    WorldState,
)
from .protocols import AllocationPolicy, TaskDynamics, Termination
from .trace import EventRecord, EventTrace, EventType, state_hash
from .types import JsonObject

EVENT_PRIORITIES: Mapping[EventType, int] = {
    EventType.RESET: 0,
    EventType.TASK_RELEASE: 10,
    EventType.PROPOSAL: 20,
    EventType.NO_OP: 25,
    EventType.ASSIGNMENT: 30,
    EventType.COALITION_FORMED: 40,
    EventType.COALITION_DISBANDED: 45,
    EventType.WORK: 50,
    EventType.COMPLETION: 60,
    EventType.FAILURE: 60,
    EventType.POLICY_ERROR: 70,
    EventType.TICK_ADVANCE: 80,
    EventType.SIMULATION_TERMINATION: 90,
}


class KernelError(RuntimeError):
    """Base error for invalid kernel configuration or transitions."""


class InvalidActionError(KernelError, ValueError):
    """Raised when an action is rejected before any action mutation occurs."""


class UnitWorkDynamics:
    """Default allocation-only dynamics: one unit of work per tick."""

    def advance(
        self,
        task: TaskSpec,
        coalition: Coalition,
        progress: float,
        tick: int,
    ) -> float:
        del coalition, tick
        if task.workload == 0.0:
            return 1.0
        return min(1.0, progress + 1.0 / task.workload)


@dataclass(frozen=True, slots=True)
class _FormValidation:
    """Validated immutable inputs used by the formation transition."""

    task: TaskSpec
    robots: tuple[RobotSpec, ...]


class SimulationKernel:
    """Own and advance one immutable ``WorldState`` at a time.

    The kernel is intentionally allocation-only.  Formation, work, and
    release transitions are deterministic and scenario-independent; richer
    travel or task dynamics enter through the protocols already defined by
    the domain model.
    """

    def __init__(
        self,
        scenario: ScenarioSpec,
        policy: AllocationPolicy | None = None,
        *,
        dynamics: TaskDynamics | None = None,
        termination: Termination | None = None,
        horizon: int | None = None,
    ) -> None:
        if not isinstance(scenario, ScenarioSpec):
            raise TypeError("scenario must be a ScenarioSpec")
        active_horizon = scenario.horizon if horizon is None else horizon
        if active_horizon is not None and (
            isinstance(active_horizon, bool)
            or not isinstance(active_horizon, int)
            or active_horizon < 0
        ):
            raise ValueError("horizon must be a nonnegative integer or None")
        self.scenario = scenario
        self.policy = policy
        self.dynamics = dynamics or UnitWorkDynamics()
        self.termination = termination
        self.horizon = active_horizon
        self._world = self._initial_world()
        self._events: list[EventRecord] = []
        self._insertion_sequence = 0
        self._has_reset = False

    @property
    def world(self) -> WorldState:
        """Return the current immutable world snapshot."""

        return self._world

    @property
    def state(self) -> WorldState:
        """Alias for ``world`` used by replay and experiment code."""

        return self._world

    @property
    def events(self) -> tuple[EventRecord, ...]:
        """Return the current append-only event sequence."""

        return tuple(self._events)

    @property
    def trace(self) -> EventTrace:
        """Return the current event sequence as an immutable trace."""

        return EventTrace(self.events)

    def _initial_world(self) -> WorldState:
        robots = {
            robot.robot_id: RobotState(
                robot_id=robot.robot_id,
                position=robot.position,
                resources=dict(robot.resources),
            )
            for robot in self.scenario.robots
        }
        tasks = {
            task.task_id: TaskState(task_id=task.task_id)
            for task in self.scenario.tasks
        }
        return WorldState(robots=robots, tasks=tasks)

    def _record(
        self,
        event_type: EventType,
        payload: Mapping[str, object],
        before: WorldState,
        *,
        event_tick: int | None = None,
        event_priority: int | None = None,
    ) -> EventRecord:
        event = EventRecord(
            event_type=event_type,
            tick=self._world.tick if event_tick is None else event_tick,
            event_priority=(
                EVENT_PRIORITIES[event_type]
                if event_priority is None
                else event_priority
            ),
            insertion_sequence=self._insertion_sequence,
            payload=cast(JsonObject, dict(payload)),
            pre_state_hash=state_hash(before),
            post_state_hash=state_hash(self._world),
            state=self._world,
        )
        self._events.append(event)
        self._insertion_sequence += 1
        return event

    def _transition(
        self,
        event_type: EventType,
        payload: Mapping[str, object],
        next_world: WorldState,
        *,
        event_tick: int | None = None,
        event_priority: int | None = None,
    ) -> EventRecord:
        before = self._world
        self._world = next_world
        return self._record(
            event_type,
            payload,
            before,
            event_tick=event_tick,
            event_priority=event_priority,
        )

    def reset(self) -> WorldState:
        """Reset state and trace, then release tasks available at tick zero."""

        self._world = self._initial_world()
        self._events = []
        self._insertion_sequence = 0
        self._has_reset = True
        self._record(
            EventType.RESET,
            {
                "scenario_id": self.scenario.scenario_id,
                "scenario_schema_version": self.scenario.schema_version,
            },
            self._world,
        )
        self._release_tasks()
        if self.horizon == 0:
            self._terminate(TerminalStatus.TIMED_OUT, "horizon reached at reset")
        elif not self._world.tasks:
            self._terminate(TerminalStatus.SUCCEEDED, "no tasks")
        return self._world

    def observe(self) -> Observation:
        """Return the immutable policy-facing observation."""

        return Observation.from_world_state(self._world)

    def _release_tasks(self) -> None:
        for task in self.scenario.tasks:
            current = self._world.tasks[task.task_id]
            if (
                current.status is not TaskStatus.PENDING
                or task.release_tick > self._world.tick
            ):
                continue
            next_tasks = dict(self._world.tasks)
            next_tasks[task.task_id] = replace(current, status=TaskStatus.RELEASED)
            self._transition(
                EventType.TASK_RELEASE,
                {"task_id": task.task_id, "release_tick": task.release_tick},
                replace(self._world, tasks=next_tasks),
            )

    def _action_payload(self, action: Action | None) -> dict[str, object]:
        return {"action": action.to_dict() if action is not None else None}

    def _policy_error(self, message: str, *, action: Action | None = None) -> None:
        self._record(
            EventType.POLICY_ERROR,
            {
                "message": message,
                "action": action.to_dict() if action is not None else None,
            },
            self._world,
        )

    def _validate_form(self, action: FormCoalitionAction) -> _FormValidation:
        if self._world.terminal_status is not None:
            raise InvalidActionError("post-terminal actions are rejected")
        if action.coalition_id in self._world.coalitions:
            raise InvalidActionError(
                f"coalition ID {action.coalition_id!r} is already in use"
            )
        try:
            task = next(
                item for item in self.scenario.tasks if item.task_id == action.task_id
            )
        except StopIteration:
            raise InvalidActionError(f"unknown task ID {action.task_id!r}") from None
        task_state = self._world.tasks[action.task_id]
        if task_state.status is TaskStatus.PENDING:
            raise InvalidActionError(
                f"early task execution: task {action.task_id!r} is not released"
            )
        if task_state.status is not TaskStatus.RELEASED:
            raise InvalidActionError(
                f"task {action.task_id!r} is not available for assignment"
            )
        if task.time_window is not None:
            if self._world.tick < task.time_window.start_tick:
                raise InvalidActionError(
                    f"early task execution: task {action.task_id!r} opens at "
                    f"tick {task.time_window.start_tick}"
                )
            if self._world.tick >= task.time_window.end_tick:
                raise InvalidActionError(
                    f"task {action.task_id!r} is outside its time window"
                )
        predecessors = {
            dependency.predecessor_id
            for dependency in self.scenario.dependencies
            if dependency.successor_id == task.task_id
        }
        incomplete = sorted(
            predecessor
            for predecessor in predecessors
            if self._world.tasks[predecessor].status is not TaskStatus.COMPLETED
        )
        if incomplete:
            raise InvalidActionError(
                f"task {task.task_id!r} has incomplete predecessors: "
                + ", ".join(incomplete)
            )
        unknown_robots = sorted(set(action.robot_ids) - set(self._world.robots))
        if unknown_robots:
            raise InvalidActionError("unknown robot IDs: " + ", ".join(unknown_robots))
        if len(action.robot_ids) < task.min_coalition_size:
            raise InvalidActionError(
                f"coalition has {len(action.robot_ids)} robots; "
                f"task requires at least {task.min_coalition_size}"
            )
        if (
            task.max_coalition_size is not None
            and len(action.robot_ids) > task.max_coalition_size
        ):
            raise InvalidActionError(
                f"coalition has {len(action.robot_ids)} robots; "
                f"task allows at most {task.max_coalition_size}"
            )
        robot_specs = {robot.robot_id: robot for robot in self.scenario.robots}
        selected_specs = tuple(robot_specs[robot_id] for robot_id in action.robot_ids)
        selected_states = tuple(
            self._world.robots[robot.robot_id] for robot in selected_specs
        )
        for robot, robot_state in zip(selected_specs, selected_states, strict=True):
            if len(robot_state.assigned_task_ids) >= robot.max_concurrent_tasks:
                raise InvalidActionError(
                    f"double booking: robot {robot.robot_id!r} has no task capacity"
                )
            if robot_state.status in {RobotStatus.FAILED, RobotStatus.UNAVAILABLE}:
                raise InvalidActionError(
                    f"robot {robot.robot_id!r} is {robot_state.status.value}"
                )
        selected_ids = set(action.robot_ids)
        incompatible = sorted(
            (robot.robot_id, incompatible_id)
            for robot in selected_specs
            for incompatible_id in robot.incompatible_robot_ids
            if incompatible_id in selected_ids and robot.robot_id < incompatible_id
        )
        if incompatible:
            first, second = incompatible[0]
            raise InvalidActionError(
                f"coalition contains incompatible robots {first!r} and {second!r}"
            )
        for capability, required in task.requirements.items():
            available = sum(
                robot.capabilities.get(capability, 0.0) for robot in selected_specs
            )
            if available < required:
                raise InvalidActionError(
                    f"insufficient capability {capability!r}: "
                    f"{available:g} available, {required:g} required"
                )
        for resource, required in task.resource_requirements.items():
            available = sum(
                robot_state.resources.get(resource, 0.0)
                for robot_state in selected_states
            )
            if available < required:
                raise InvalidActionError(
                    f"insufficient resource {resource!r}: "
                    f"{available:g} available, {required:g} required"
                )
        return _FormValidation(task=task, robots=selected_specs)

    def _apply_form(self, action: FormCoalitionAction) -> None:
        validated = self._validate_form(action)
        task_state = self._world.tasks[action.task_id]
        coalition = Coalition(
            coalition_id=action.coalition_id,
            task_id=action.task_id,
            robot_ids=action.robot_ids,
            status=CoalitionStatus.FORMING,
            value=validated.task.reward,
        )
        coalitions = dict(self._world.coalitions)
        coalitions[action.coalition_id] = coalition
        tasks = dict(self._world.tasks)
        tasks[action.task_id] = replace(
            task_state,
            status=TaskStatus.ASSIGNED,
            assigned_coalition_id=action.coalition_id,
        )
        robots = dict(self._world.robots)
        for robot in validated.robots:
            current = robots[robot.robot_id]
            robots[robot.robot_id] = replace(
                current,
                coalition_ids=(*current.coalition_ids, action.coalition_id),
                assigned_task_ids=(*current.assigned_task_ids, action.task_id),
            )
        self._transition(
            EventType.ASSIGNMENT,
            {
                "coalition_id": action.coalition_id,
                "task_id": action.task_id,
                "robot_ids": list(action.robot_ids),
            },
            replace(self._world, robots=robots, tasks=tasks, coalitions=coalitions),
        )
        coalitions = dict(self._world.coalitions)
        coalitions[action.coalition_id] = replace(
            coalition,
            status=CoalitionStatus.ACTIVE,
            formed_tick=self._world.tick,
        )
        tasks = dict(self._world.tasks)
        tasks[action.task_id] = replace(tasks[action.task_id], status=TaskStatus.ACTIVE)
        robots = dict(self._world.robots)
        for robot_id in action.robot_ids:
            robots[robot_id] = replace(robots[robot_id], status=RobotStatus.WORKING)
        self._transition(
            EventType.COALITION_FORMED,
            {
                "coalition_id": action.coalition_id,
                "task_id": action.task_id,
                "robot_ids": list(action.robot_ids),
            },
            replace(self._world, robots=robots, tasks=tasks, coalitions=coalitions),
        )

    def _apply_disband(self, action: DisbandCoalitionAction) -> None:
        if self._world.terminal_status is not None:
            raise InvalidActionError("post-terminal actions are rejected")
        coalition = self._world.coalitions.get(action.coalition_id)
        if coalition is None:
            raise InvalidActionError(f"unknown coalition ID {action.coalition_id!r}")
        if coalition.status is CoalitionStatus.DISBANDED:
            raise InvalidActionError(
                f"coalition {action.coalition_id!r} is already disbanded"
            )
        tasks = dict(self._world.tasks)
        task_state = tasks[coalition.task_id]
        if task_state.status in {TaskStatus.ASSIGNED, TaskStatus.ACTIVE}:
            tasks[coalition.task_id] = replace(
                task_state,
                status=TaskStatus.RELEASED,
                assigned_coalition_id=None,
            )
        coalitions = dict(self._world.coalitions)
        coalitions[action.coalition_id] = replace(
            coalition, status=CoalitionStatus.DISBANDED
        )
        robots = dict(self._world.robots)
        for robot_id in coalition.robot_ids:
            current = robots[robot_id]
            remaining_coalitions = tuple(
                item for item in current.coalition_ids if item != action.coalition_id
            )
            robots[robot_id] = replace(
                current,
                status=(
                    current.status
                    if current.status in {RobotStatus.FAILED, RobotStatus.UNAVAILABLE}
                    else (
                        RobotStatus.WORKING
                        if remaining_coalitions
                        else RobotStatus.IDLE
                    )
                ),
                coalition_ids=remaining_coalitions,
                assigned_task_ids=tuple(
                    item
                    for item in current.assigned_task_ids
                    if item != coalition.task_id
                ),
            )
        self._transition(
            EventType.COALITION_DISBANDED,
            {
                "coalition_id": action.coalition_id,
                "task_id": coalition.task_id,
                "reason": "policy",
            },
            replace(self._world, robots=robots, tasks=tasks, coalitions=coalitions),
        )

    def _apply_action(self, action: Action) -> None:
        if isinstance(action, FormCoalitionAction):
            self._apply_form(action)
        elif isinstance(action, DisbandCoalitionAction):
            self._apply_disband(action)
        elif isinstance(action, NoOpAction):
            self._record(EventType.NO_OP, {"reason": action.reason}, self._world)
        else:
            raise InvalidActionError("policy returned an unsupported action type")

    def _cleanup_coalition(self, coalition_id: str, reason: str) -> None:
        coalition = self._world.coalitions[coalition_id]
        coalitions = dict(self._world.coalitions)
        coalitions[coalition_id] = replace(coalition, status=CoalitionStatus.DISBANDED)
        robots = dict(self._world.robots)
        for robot_id in coalition.robot_ids:
            current = robots[robot_id]
            remaining_coalitions = tuple(
                item for item in current.coalition_ids if item != coalition_id
            )
            robots[robot_id] = replace(
                current,
                status=(
                    current.status
                    if current.status in {RobotStatus.FAILED, RobotStatus.UNAVAILABLE}
                    else (
                        RobotStatus.WORKING
                        if remaining_coalitions
                        else RobotStatus.IDLE
                    )
                ),
                coalition_ids=remaining_coalitions,
                assigned_task_ids=tuple(
                    item
                    for item in current.assigned_task_ids
                    if item != coalition.task_id
                ),
            )
        tasks = dict(self._world.tasks)
        tasks[coalition.task_id] = replace(
            tasks[coalition.task_id], assigned_coalition_id=None
        )
        self._transition(
            EventType.COALITION_DISBANDED,
            {
                "coalition_id": coalition_id,
                "task_id": coalition.task_id,
                "reason": reason,
            },
            replace(self._world, robots=robots, tasks=tasks, coalitions=coalitions),
            event_priority=65,
        )

    def _advance_work(self) -> None:
        for coalition_id in sorted(self._world.coalitions):
            coalition = self._world.coalitions[coalition_id]
            if coalition.status is not CoalitionStatus.ACTIVE:
                continue
            task = next(
                item
                for item in self.scenario.tasks
                if item.task_id == coalition.task_id
            )
            task_state = self._world.tasks[task.task_id]
            if task_state.status is not TaskStatus.ACTIVE:
                continue
            try:
                next_progress = float(
                    self.dynamics.advance(
                        task, coalition, task_state.progress, self._world.tick
                    )
                )
            except Exception as error:
                self._fail_task(task.task_id, f"task dynamics error: {error}")
                continue
            if not isfinite(next_progress) or not 0.0 <= next_progress <= 1.0:
                self._fail_task(task.task_id, "task dynamics returned invalid progress")
                continue
            tasks = dict(self._world.tasks)
            tasks[task.task_id] = replace(task_state, progress=next_progress)
            self._transition(
                EventType.WORK,
                {
                    "coalition_id": coalition_id,
                    "task_id": task.task_id,
                    "previous_progress": task_state.progress,
                    "progress": next_progress,
                },
                replace(self._world, tasks=tasks),
            )
            if next_progress >= 1.0:
                tasks = dict(self._world.tasks)
                tasks[task.task_id] = replace(
                    tasks[task.task_id],
                    status=TaskStatus.COMPLETED,
                    completion_tick=self._world.tick,
                )
                self._transition(
                    EventType.COMPLETION,
                    {
                        "coalition_id": coalition_id,
                        "task_id": task.task_id,
                    },
                    replace(self._world, tasks=tasks),
                )
                self._cleanup_coalition(coalition_id, "task completed")

    def _fail_task(self, task_id: str, reason: str) -> None:
        task_state = self._world.tasks[task_id]
        if task_state.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }:
            return
        tasks = dict(self._world.tasks)
        tasks[task_id] = replace(
            task_state,
            status=TaskStatus.FAILED,
            assigned_coalition_id=task_state.assigned_coalition_id,
            failure_reason=reason,
        )
        self._transition(
            EventType.FAILURE,
            {"task_id": task_id, "reason": reason},
            replace(self._world, tasks=tasks),
        )
        coalition_id = task_state.assigned_coalition_id
        if coalition_id is not None and coalition_id in self._world.coalitions:
            self._cleanup_coalition(coalition_id, "task failed")

    def _check_deadlines(self) -> None:
        for task in self.scenario.tasks:
            state = self._world.tasks[task.task_id]
            if state.status not in {
                TaskStatus.RELEASED,
                TaskStatus.ASSIGNED,
                TaskStatus.ACTIVE,
            }:
                continue
            if (
                task.time_window is not None
                and self._world.tick + 1 >= task.time_window.end_tick
            ):
                self._fail_task(task.task_id, "time window expired")

    def _terminate(self, status: TerminalStatus, reason: str) -> None:
        if self._world.terminal_status is not None:
            return
        self._transition(
            EventType.SIMULATION_TERMINATION,
            {"status": status.value, "reason": reason},
            replace(self._world, terminal_status=status),
        )

    def _finish_step(self) -> None:
        statuses = tuple(task.status for task in self._world.tasks.values())
        if statuses and all(
            status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
            for status in statuses
        ):
            if all(
                status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}
                for status in statuses
            ):
                self._terminate(
                    TerminalStatus.SUCCEEDED, "all tasks reached terminal success"
                )
            else:
                self._terminate(TerminalStatus.FAILED, "one or more tasks failed")
            return
        if self.termination is not None:
            try:
                should_terminate = self.termination.should_terminate(self._world)
            except Exception as error:
                self._policy_error(f"termination model error: {error}")
                should_terminate = False
            if should_terminate:
                self._terminate(
                    TerminalStatus.SUCCEEDED, "termination model requested stop"
                )
                return
        if self.horizon is not None and self._world.tick + 1 >= self.horizon:
            event_tick = self._world.tick
            self._transition(
                EventType.TICK_ADVANCE,
                {"from_tick": self._world.tick, "to_tick": self.horizon},
                replace(self._world, tick=self.horizon),
                event_tick=event_tick,
            )
            self._terminate(TerminalStatus.TIMED_OUT, "horizon reached")
            return
        event_tick = self._world.tick
        self._transition(
            EventType.TICK_ADVANCE,
            {"from_tick": self._world.tick, "to_tick": self._world.tick + 1},
            replace(self._world, tick=self._world.tick + 1),
            event_tick=event_tick,
        )
        self._release_tasks()

    def _step_internal(self, action: Action | None, *, explicit: bool) -> WorldState:
        if not self._has_reset:
            self.reset()
        if self._world.terminal_status is not None:
            if explicit:
                self._record(
                    EventType.PROPOSAL, self._action_payload(action), self._world
                )
                message = "post-terminal actions are rejected"
                self._policy_error(message, action=action)
                raise InvalidActionError(message)
            return self._world
        if self._world.tick > 0:
            self._release_tasks()
        selected_action = action
        proposal_error: str | None = None
        if not explicit:
            if self.policy is None:
                selected_action = NoOpAction()
            else:
                try:
                    selected_action = self.policy.propose(self.observe())
                except Exception as error:
                    proposal_error = f"policy proposal error: {error}"
                    selected_action = NoOpAction(reason="policy error")
                if not isinstance(
                    selected_action,
                    (FormCoalitionAction, DisbandCoalitionAction, NoOpAction),
                ):
                    proposal_error = "policy returned an unsupported action type"
                    selected_action = NoOpAction(reason="unsupported policy action")
        if selected_action is None:
            selected_action = NoOpAction()
        self._record(
            EventType.PROPOSAL, self._action_payload(selected_action), self._world
        )
        if proposal_error is not None:
            self._apply_action(NoOpAction(reason="policy error"))
            self._policy_error(proposal_error, action=selected_action)
            self._advance_work()
            self._check_deadlines()
            self._finish_step()
            return self._world
        try:
            self._apply_action(selected_action)
        except InvalidActionError as error:
            self._policy_error(str(error), action=selected_action)
            if explicit:
                raise
        self._advance_work()
        self._check_deadlines()
        self._finish_step()
        return self._world

    def step(self, action: Action | None = None) -> WorldState:
        """Apply one policy action, work active coalitions, and advance time.

        An explicitly supplied invalid action raises ``InvalidActionError``
        after recording a proposal and policy-error event.  The rejected action
        never partially mutates the world.  Policy-generated invalid actions
        are recorded and treated as no-ops so a run remains auditable.
        """

        return self._step_internal(action, explicit=action is not None)

    def run(
        self,
        policy: AllocationPolicy | None = None,
        *,
        max_steps: int | None = None,
    ) -> WorldState:
        """Reset and run until terminal, horizon, or the explicit step limit."""

        if policy is not None:
            self.policy = policy
        if max_steps is not None and (
            isinstance(max_steps, bool)
            or not isinstance(max_steps, int)
            or max_steps < 0
        ):
            raise ValueError("max_steps must be a nonnegative integer or None")
        self.reset()
        limit = max_steps
        if limit is None:
            limit = self.horizon if self.horizon is not None else 1000
        for _ in range(limit):
            if self._world.terminal_status is not None:
                break
            self._step_internal(None, explicit=False)
        if self._world.terminal_status is None:
            self._terminate(TerminalStatus.TIMED_OUT, "run step limit reached")
        return self._world

    @classmethod
    def replay(
        cls, scenario: ScenarioSpec, trace: EventTrace | str | Path
    ) -> SimulationKernel:
        """Build a kernel whose state is reconstructed from a saved trace."""

        active_trace: EventTrace
        if isinstance(trace, EventTrace):
            active_trace = trace
        elif isinstance(trace, (str, Path)):
            from .trace import read_trace

            active_trace = read_trace(trace)
        else:
            raise TypeError("trace must be an EventTrace or JSONL path")
        kernel = cls(scenario)
        kernel._events = list(active_trace.events)
        kernel._insertion_sequence = (
            active_trace.events[-1].insertion_sequence + 1 if active_trace.events else 0
        )
        kernel._world = active_trace.replay()
        kernel._has_reset = bool(active_trace.events)
        return kernel


replay_trace = SimulationKernel.replay
