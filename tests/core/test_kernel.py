import json
from dataclasses import replace

import pytest

from coalition_formation.config import ResolvedConfig
from coalition_formation.core.actions import (
    Action,
    FormCoalitionAction,
    NoOpAction,
)
from coalition_formation.core.kernel import InvalidActionError, SimulationKernel
from coalition_formation.core.models import (
    RobotSpec,
    ScenarioSpec,
    TaskSpec,
    TaskStatus,
    TerminalStatus,
    TimeWindow,
)
from coalition_formation.core.trace import (
    EventType,
    read_trace,
    state_hash,
    write_trace,
)
from coalition_formation.registry import construct_scenario


class QueuePolicy:
    def __init__(self, actions: list[Action]) -> None:
        self.actions = list(actions)

    def propose(self, observation: object) -> Action:
        del observation
        if self.actions:
            return self.actions.pop(0)
        return NoOpAction()


def _tiny() -> ScenarioSpec:
    return construct_scenario(
        ResolvedConfig(schema_version="1.0", scenario="static_capability/tiny")
    )


def test_run_trace_is_deterministic_and_replayable(tmp_path: object) -> None:
    actions = [
        FormCoalitionAction("c1", "t1", ("r1", "r2")),
        FormCoalitionAction("c2", "t2", ("r3", "r4")),
        FormCoalitionAction("c3", "t3", ("r5", "r6")),
    ]
    first = SimulationKernel(_tiny(), QueuePolicy(actions))
    second = SimulationKernel(_tiny(), QueuePolicy(actions))

    first_world = first.run()
    second_world = second.run()

    assert first_world.terminal_status is TerminalStatus.SUCCEEDED
    assert state_hash(first_world) == state_hash(second_world)
    assert first.trace.to_jsonl() == second.trace.to_jsonl()
    assert first.trace.replay() == first_world

    destination = tmp_path / "trace.jsonl"  # type: ignore[operator]
    write_trace(first.trace, destination)
    saved = read_trace(destination)
    assert saved.replay() == first_world
    assert SimulationKernel.replay(_tiny(), destination).world == first_world


def test_trace_contains_versioned_lifecycle_events_in_order() -> None:
    kernel = SimulationKernel(
        _tiny(),
        QueuePolicy([FormCoalitionAction("c1", "t1", ("r1", "r2"))]),
    )
    kernel.run(max_steps=1)

    events = kernel.events
    assert events[0].event_type is EventType.RESET
    assert EventType.TASK_RELEASE in {event.event_type for event in events}
    assert EventType.PROPOSAL in {event.event_type for event in events}
    assert EventType.ASSIGNMENT in {event.event_type for event in events}
    assert EventType.COALITION_FORMED in {event.event_type for event in events}
    assert EventType.WORK in {event.event_type for event in events}
    assert EventType.COMPLETION in {event.event_type for event in events}
    assert all(
        earlier.ordering_key() <= later.ordering_key()
        for earlier, later in zip(events, events[1:], strict=False)
    )
    for event in events:
        json.dumps(event.to_dict())


def test_invalid_early_action_is_traced_and_atomic() -> None:
    scenario = ScenarioSpec(
        scenario_id="early",
        robots=(RobotSpec(robot_id="r1", capabilities={"skill": 1}),),
        tasks=(TaskSpec(task_id="t1", requirements={"skill": 1}, release_tick=2),),
    )
    kernel = SimulationKernel(scenario)
    kernel.reset()
    before = kernel.world

    with pytest.raises(InvalidActionError, match="early task execution"):
        kernel.step(FormCoalitionAction("c1", "t1", ("r1",)))

    assert kernel.world == before
    assert kernel.events[-1].event_type is EventType.POLICY_ERROR
    assert kernel.events[-1].post_state_hash == state_hash(before)


def test_double_booking_and_unknown_ids_are_rejected_atomically() -> None:
    scenario = ScenarioSpec(
        scenario_id="booking",
        robots=(RobotSpec(robot_id="r1", capabilities={"skill": 1}),),
        tasks=(
            TaskSpec(task_id="t1", requirements={"skill": 1}, workload=3),
            TaskSpec(task_id="t2", requirements={"skill": 1}),
        ),
    )
    kernel = SimulationKernel(scenario)
    kernel.reset()
    kernel.step(FormCoalitionAction("c1", "t1", ("r1",)))
    before = kernel.world

    with pytest.raises(InvalidActionError, match="double booking"):
        kernel.step(FormCoalitionAction("c2", "t2", ("r1",)))
    assert kernel.world == before

    with pytest.raises(InvalidActionError, match="unknown robot IDs"):
        kernel.step(FormCoalitionAction("c3", "t2", ("missing",)))
    assert kernel.world == before


def test_post_terminal_action_is_rejected_without_mutation() -> None:
    scenario = ScenarioSpec(
        scenario_id="terminal",
        robots=(RobotSpec(robot_id="r1", capabilities={"skill": 1}),),
        tasks=(TaskSpec(task_id="t1", requirements={"skill": 1}),),
    )
    kernel = SimulationKernel(scenario)
    kernel.step(FormCoalitionAction("c1", "t1", ("r1",)))
    before = kernel.world

    with pytest.raises(InvalidActionError, match="post-terminal"):
        kernel.step(NoOpAction())

    assert kernel.world == before
    assert kernel.events[-1].event_type is EventType.POLICY_ERROR


def test_horizon_and_no_op_advance_deterministically() -> None:
    scenario = ScenarioSpec(
        scenario_id="horizon",
        horizon=2,
        robots=(RobotSpec(robot_id="r1"),),
        tasks=(TaskSpec(task_id="t1", release_tick=4),),
    )
    kernel = SimulationKernel(scenario)

    kernel.reset()
    kernel.step(NoOpAction(reason="wait"))
    result = kernel.step(NoOpAction(reason="wait"))

    assert result.tick == 2
    assert result.terminal_status is TerminalStatus.TIMED_OUT
    assert [event.event_type for event in kernel.events].count(EventType.NO_OP) == 2
    assert kernel.events[-1].event_type is EventType.SIMULATION_TERMINATION


def test_time_window_expiry_emits_failure() -> None:
    scenario = ScenarioSpec(
        scenario_id="deadline",
        horizon=3,
        robots=(RobotSpec(robot_id="r1", capabilities={"skill": 1}),),
        tasks=(
            TaskSpec(
                task_id="t1",
                requirements={"skill": 1},
                time_window=TimeWindow(start_tick=0, end_tick=2),
                workload=4,
            ),
        ),
    )
    kernel = SimulationKernel(scenario)
    kernel.step(FormCoalitionAction("c1", "t1", ("r1",)))
    result = kernel.step(NoOpAction())

    assert result.tasks["t1"].status is TaskStatus.FAILED
    assert result.terminal_status is TerminalStatus.FAILED
    assert any(event.event_type is EventType.FAILURE for event in kernel.events)


def test_policy_errors_are_traceable_without_breaking_order_or_replay() -> None:
    class FailingPolicy:
        def propose(self, observation: object) -> Action:
            del observation
            raise RuntimeError("deliberate failure")

    scenario = ScenarioSpec(
        scenario_id="policy-error",
        horizon=1,
        robots=(RobotSpec(robot_id="r1"),),
        tasks=(TaskSpec(task_id="t1"),),
    )
    kernel = SimulationKernel(scenario, FailingPolicy())
    result = kernel.run()

    assert result.terminal_status is TerminalStatus.TIMED_OUT
    assert any(event.event_type is EventType.POLICY_ERROR for event in kernel.events)
    assert kernel.trace.replay() == result


@pytest.mark.parametrize("second_workload", [1, 5])
def test_simultaneous_outcomes_preserve_trace_order(second_workload: int) -> None:
    scenario = ScenarioSpec(
        "simultaneous",
        robots=(RobotSpec("r1"), RobotSpec("r2")),
        tasks=(
            TaskSpec("t1", workload=2),
            TaskSpec("t2", workload=second_workload, time_window=TimeWindow(0, 2)),
        ),
    )
    kernel = SimulationKernel(scenario)
    kernel.step(FormCoalitionAction("c1", "t1", ("r1",)))
    kernel.step(FormCoalitionAction("c2", "t2", ("r2",)))
    keys = [event.ordering_key() for event in kernel.events]
    assert keys == sorted(keys)
    from coalition_formation.core.trace import EventTrace

    assert EventTrace.from_jsonl(kernel.trace.to_jsonl()).replay() == kernel.world


@pytest.mark.parametrize("change", ["id", "requirements", "workload", "horizon"])
def test_replay_rejects_modified_scenario(change: str) -> None:
    scenario = ScenarioSpec(
        "source", robots=(RobotSpec("r1"),), tasks=(TaskSpec("t1", workload=3),)
    )
    kernel = SimulationKernel(scenario)
    kernel.step(FormCoalitionAction("c1", "t1", ("r1",)))
    if change == "id":
        modified = replace(scenario, scenario_id="different")
    elif change == "horizon":
        modified = replace(scenario, horizon=5)
    elif change == "requirements":
        modified = replace(
            scenario, tasks=(replace(scenario.tasks[0], requirements={"skill": 1}),)
        )
    else:
        modified = replace(scenario, tasks=(replace(scenario.tasks[0], workload=4),))
    with pytest.raises(ValueError, match="scenario"):
        SimulationKernel.replay(modified, kernel.trace)
    restored = SimulationKernel.replay(scenario, kernel.trace)
    assert restored.step(NoOpAction()) == kernel.step(NoOpAction())
