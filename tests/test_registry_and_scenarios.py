import itertools
import json

import pytest

from coalition_formation.config import CONFIG_SCHEMA_VERSION, ResolvedConfig
from coalition_formation.core.models import RobotSpec, ScenarioSpec
from coalition_formation.registry import (
    ScenarioRegistry,
    construct_scenario,
    default_registry,
    list_scenarios,
)
from coalition_formation.rng import RandomStreams


def _config(
    scenario: str, seed: int = 7, policy_seed: int | None = None
) -> ResolvedConfig:
    return ResolvedConfig(
        schema_version=CONFIG_SCHEMA_VERSION,
        scenario=scenario,
        seed=seed,
        policy_seed=policy_seed,
    )


def test_registry_order_and_duplicate_names_are_deterministic() -> None:
    expected = (
        "static_capability/tiny",
        "static_capability/small",
        "static_capability/random",
        "static_capability/scarcity",
        "static_capability/redundancy",
        "static_capability/incompatibility",
        "static_capability/tied_optimum",
    )
    assert list_scenarios() == expected
    assert list_scenarios() == list_scenarios()

    registry = ScenarioRegistry()

    def factory(config: ResolvedConfig, streams: RandomStreams) -> ScenarioSpec:
        del config, streams
        return ScenarioSpec(scenario_id="example")

    registry.register("example", factory)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("example", factory)
    with pytest.raises(KeyError, match="unknown scenario"):
        registry.create("missing", _config("example"), RandomStreams(1))


def test_same_config_and_seed_produce_byte_identical_scenario_json() -> None:
    config = _config("static_capability/random", seed=19, policy_seed=23)
    first = json.dumps(
        construct_scenario(config).to_dict(), sort_keys=True, separators=(",", ":")
    ).encode()
    second = json.dumps(
        construct_scenario(config).to_dict(), sort_keys=True, separators=(",", ":")
    ).encode()
    assert first == second


def test_policy_seed_does_not_change_generated_robots_or_tasks() -> None:
    first = construct_scenario(_config("static_capability/random", 19, 1))
    second = construct_scenario(_config("static_capability/random", 19, 999))

    assert first.robots == second.robots
    assert first.tasks == second.tasks
    assert RandomStreams(19, 1).seed_for("policy") != RandomStreams(19, 999).seed_for(
        "policy"
    )


def test_tiny_fixture_has_the_known_unique_full_partition() -> None:
    scenario = construct_scenario(_config("static_capability/tiny"))
    assert len(scenario.robots) == 6
    assert len(scenario.tasks) == 3
    expected = {"t1": ("r1", "r2"), "t2": ("r3", "r4"), "t3": ("r5", "r6")}
    robot_by_id = {robot.robot_id: robot for robot in scenario.robots}

    for task in scenario.tasks:
        feasible_pairs = []
        for pair in itertools.combinations(robot_by_id, 2):
            if all(
                sum(
                    robot_by_id[robot_id].capabilities.get(skill, 0.0)
                    for robot_id in pair
                )
                >= required
                for skill, required in task.requirements.items()
            ):
                feasible_pairs.append(pair)
        assert feasible_pairs == [expected[task.task_id]]


def test_small_and_random_presets_have_documented_shapes() -> None:
    small = construct_scenario(_config("static_capability/small"))
    assert len(small.robots) == 12
    assert len(small.tasks) == 8
    assert {skill for robot in small.robots for skill in robot.capabilities} == {
        f"skill_{letter}" for letter in "abcde"
    }

    random_config = ResolvedConfig(
        schema_version="1.0",
        scenario="static_capability/random",
        seed=4,
        parameters={"robot_count": 4, "task_count": 2, "skill_count": 3},
    )
    random_scenario = construct_scenario(random_config)
    assert len(random_scenario.robots) == 4
    assert len(random_scenario.tasks) == 2
    assert {len(robot.capabilities) for robot in random_scenario.robots} <= {3}


def test_random_scenario_rejects_unsupported_parameters() -> None:
    config = ResolvedConfig(
        schema_version=CONFIG_SCHEMA_VERSION,
        scenario="static_capability/random",
        parameters={"robot_counts": 4},
    )

    with pytest.raises(ValueError, match="unsupported parameter"):
        construct_scenario(config)


def test_static_edge_case_fixtures() -> None:
    scarcity = construct_scenario(_config("static_capability/scarcity"))
    rare_providers = [
        robot.robot_id
        for robot in scarcity.robots
        if robot.capabilities.get("rare", 0) > 0
    ]
    assert rare_providers == ["r1"]

    redundancy = construct_scenario(_config("static_capability/redundancy"))
    lift_providers = [
        robot.robot_id
        for robot in redundancy.robots
        if robot.capabilities.get("lift", 0) > 0
    ]
    assert lift_providers == ["r1", "r2"]

    incompatibility = construct_scenario(_config("static_capability/incompatibility"))
    robots = {robot.robot_id: robot for robot in incompatibility.robots}
    assert robots["r2"].robot_id in robots["r1"].incompatible_robot_ids
    assert robots["r1"].robot_id in robots["r2"].incompatible_robot_ids

    tied = construct_scenario(_config("static_capability/tied_optimum"))
    assert [
        robot.robot_id
        for robot in tied.robots
        if robot.capabilities.get("sensor", 0) >= 1
    ] == ["r1", "r2"]


def test_scenario_registry_accepts_explicit_custom_factories() -> None:
    registry = default_registry()
    config = _config("custom")

    def custom_factory(config: ResolvedConfig, streams: RandomStreams) -> ScenarioSpec:
        del config, streams
        return ScenarioSpec(
            scenario_id="custom",
            robots=(RobotSpec(robot_id="r1"),),
        )

    registry.register("custom", custom_factory)
    assert registry.create("custom", config, RandomStreams(1)).scenario_id == "custom"
