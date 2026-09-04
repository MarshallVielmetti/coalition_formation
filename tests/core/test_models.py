import json
from dataclasses import FrozenInstanceError

import pytest

from coalition_formation.core.models import (
    Coalition,
    CoalitionStatus,
    Dependency,
    Observation,
    RobotSpec,
    RobotState,
    RobotStatus,
    ScenarioSpec,
    TaskSpec,
    TaskState,
    TaskStatus,
    TerminalStatus,
    TimeWindow,
    WorldState,
)


def test_spec_models_round_trip_through_json_compatible_data() -> None:
    window = TimeWindow(start_tick=2, end_tick=10)
    dependency = Dependency(predecessor_id="t1", successor_id="t2")
    robot = RobotSpec(
        robot_id="r1",
        robot_type="carrier",
        capabilities={"lift": 2},
        resources={"battery": 10},
        position=(1, 2),
        speed=1.5,
        max_concurrent_tasks=2,
    )
    task = TaskSpec(
        task_id="t1",
        task_type="transport",
        requirements={"lift": 1},
        resource_requirements={"battery": 3},
        location=(4, 5),
        release_tick=1,
        time_window=window,
        workload=3,
        reward=8,
        min_coalition_size=1,
        max_coalition_size=2,
    )
    task_two = TaskSpec(task_id="t2")
    scenario = ScenarioSpec(
        scenario_id="s1",
        robots=(robot,),
        tasks=(task_two, task),
        dependencies=(dependency,),
        scenario_type="static_capability",
        schema_version="1.0",
        horizon=20,
    )
    robot_state = RobotState(
        robot_id="r1",
        status=RobotStatus.WORKING,
        position=(2, 3),
        resources={"battery": 9},
        coalition_ids=("c1",),
        assigned_task_ids=("t1",),
        health=0.9,
        available_tick=4,
    )
    task_state = TaskState(
        task_id="t1",
        status=TaskStatus.ACTIVE,
        progress=0.5,
        assigned_coalition_id="c1",
    )
    coalition = Coalition(
        coalition_id="c1",
        task_id="t1",
        robot_ids=("r1",),
        status=CoalitionStatus.ACTIVE,
        formed_tick=3,
        value=4,
    )
    world = WorldState(
        tick=4,
        robots={"r1": robot_state},
        tasks={"t1": task_state},
        coalitions={"c1": coalition},
        terminal_status=TerminalStatus.SUCCEEDED,
    )
    observation = Observation.from_world_state(world)

    values = (
        (window, TimeWindow),
        (dependency, Dependency),
        (robot, RobotSpec),
        (task, TaskSpec),
        (scenario, ScenarioSpec),
        (robot_state, RobotState),
        (task_state, TaskState),
        (coalition, Coalition),
        (world, WorldState),
        (observation, Observation),
    )
    for value, model_type in values:
        encoded = value.to_dict()
        json.dumps(encoded)
        assert model_type.from_dict(encoded) == value


def test_models_copy_and_freeze_nested_collections() -> None:
    capabilities = {"lift": 1}
    robot = RobotSpec(robot_id="r1", capabilities=capabilities)
    capabilities["lift"] = 99

    assert robot.capabilities == {"lift": 1.0}
    with pytest.raises(TypeError):
        robot.capabilities["lift"] = 2  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        robot.robot_id = "r2"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("factory", "message"),
    (
        (lambda: TimeWindow(start_tick=3, end_tick=3), "end_tick"),
        (lambda: TimeWindow(start_tick=-1, end_tick=3), "start_tick"),
        (lambda: RobotSpec(robot_id="r1", capabilities={"lift": -1}), "capabilities"),
        (
            lambda: TaskSpec(task_id="t1", min_coalition_size=3, max_coalition_size=2),
            "max_coalition_size",
        ),
        (lambda: Coalition(coalition_id="c1", task_id="t1", robot_ids=()), "robot_ids"),
    ),
)
def test_invalid_values_are_rejected(factory: object, message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        factory()  # type: ignore[operator]


def test_duplicate_ids_and_unknown_dependency_endpoints_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate IDs"):
        ScenarioSpec(
            scenario_id="s1",
            robots=(RobotSpec(robot_id="r1"), RobotSpec(robot_id="r1")),
        )

    with pytest.raises(ValueError, match="duplicate IDs"):
        ScenarioSpec(
            scenario_id="s1",
            tasks=(TaskSpec(task_id="t1"), TaskSpec(task_id="t1")),
        )

    with pytest.raises(ValueError, match="known task IDs"):
        ScenarioSpec(
            scenario_id="s1",
            tasks=(TaskSpec(task_id="t1"),),
            dependencies=(Dependency(predecessor_id="t0", successor_id="t1"),),
        )


def test_observation_is_a_read_only_policy_boundary() -> None:
    world = WorldState(robots={"r1": RobotState(robot_id="r1")})
    observation = Observation.from_world_state(world)

    with pytest.raises(TypeError):
        observation.robots["r2"] = RobotState(robot_id="r2")  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        observation.robots["r1"].status = RobotStatus.FAILED  # type: ignore[misc]

    assert world.robots["r1"].status is RobotStatus.IDLE
