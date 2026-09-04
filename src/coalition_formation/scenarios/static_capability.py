"""Static capability-matching scenario factories."""

from __future__ import annotations

from ..config import ResolvedConfig
from ..core.models import RobotSpec, ScenarioSpec, TaskSpec
from ..rng import RandomStreams

_RANDOM_SCENARIO_PARAMETERS = frozenset({"robot_count", "task_count", "skill_count"})


def static_capability_tiny(
    config: ResolvedConfig, streams: RandomStreams
) -> ScenarioSpec:
    """Return six robots and three tasks with one known full partition."""

    del config, streams
    robots = (
        RobotSpec(robot_id="r1", capabilities={"skill_a": 2}),
        RobotSpec(robot_id="r2", capabilities={"skill_a": 1}),
        RobotSpec(robot_id="r3", capabilities={"skill_b": 2}),
        RobotSpec(robot_id="r4", capabilities={"skill_b": 1}),
        RobotSpec(robot_id="r5", capabilities={"skill_c": 2}),
        RobotSpec(robot_id="r6", capabilities={"skill_c": 1}),
    )
    tasks = (
        TaskSpec(
            task_id="t1",
            requirements={"skill_a": 3},
            reward=30,
            min_coalition_size=2,
            max_coalition_size=2,
        ),
        TaskSpec(
            task_id="t2",
            requirements={"skill_b": 3},
            reward=20,
            min_coalition_size=2,
            max_coalition_size=2,
        ),
        TaskSpec(
            task_id="t3",
            requirements={"skill_c": 3},
            reward=10,
            min_coalition_size=2,
            max_coalition_size=2,
        ),
    )
    return ScenarioSpec(
        scenario_id="static_capability/tiny",
        scenario_type="static_capability",
        robots=robots,
        tasks=tasks,
    )


def _integer_parameter(
    config: ResolvedConfig, name: str, default: int, minimum: int
) -> int:
    value = config.parameters.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"parameter {name!r} must be an integer")
    if value < minimum:
        raise ValueError(f"parameter {name!r} must be at least {minimum}")
    return value


def _seeded_random_scenario(
    config: ResolvedConfig,
    streams: RandomStreams,
    *,
    scenario_id: str,
    robot_count: int,
    task_count: int,
    skill_count: int,
) -> ScenarioSpec:
    unsupported = sorted(set(config.parameters) - _RANDOM_SCENARIO_PARAMETERS)
    if unsupported:
        names = ", ".join(unsupported)
        raise ValueError(f"unsupported parameter(s) for random scenario: {names}")

    robot_count = _integer_parameter(config, "robot_count", robot_count, 1)
    task_count = _integer_parameter(config, "task_count", task_count, 1)
    skill_count = _integer_parameter(config, "skill_count", skill_count, 1)
    generator = streams.generator("scenario")
    skills = tuple(f"skill_{index}" for index in range(skill_count))
    robots: list[RobotSpec] = []
    for index in range(robot_count):
        capabilities = {skill: float(generator.integers(0, 4)) for skill in skills}
        primary_skill = skills[index % skill_count]
        if not any(capabilities.values()):
            capabilities[primary_skill] = 1.0
        robots.append(
            RobotSpec(
                robot_id=f"r{index + 1}",
                capabilities=capabilities,
            )
        )

    tasks: list[TaskSpec] = []
    for index in range(task_count):
        requirements = {skill: float(generator.integers(0, 3)) for skill in skills}
        if not any(requirements.values()):
            requirements[skills[int(generator.integers(0, skill_count))]] = 1.0
        tasks.append(
            TaskSpec(
                task_id=f"t{index + 1}",
                requirements=requirements,
                workload=float(generator.integers(1, 6)),
                reward=float(generator.integers(1, 101)),
            )
        )
    return ScenarioSpec(
        scenario_id=scenario_id,
        scenario_type="static_capability",
        robots=tuple(robots),
        tasks=tuple(tasks),
    )


def static_capability_small(
    config: ResolvedConfig, streams: RandomStreams
) -> ScenarioSpec:
    """Return a twelve-robot, eight-task instance with tied alternatives."""

    del config, streams
    skill_names = ("skill_a", "skill_b", "skill_c", "skill_d", "skill_e")
    robots = tuple(
        RobotSpec(robot_id=f"r{index + 1}", capabilities={skill: 1})
        for skill, indices in (
            (skill_names[0], (0, 1)),
            (skill_names[1], (2, 3)),
            (skill_names[2], (4, 5)),
            (skill_names[3], (6, 7)),
            (skill_names[4], (8, 9)),
        )
        for index in indices
    ) + (
        RobotSpec(
            robot_id="r11",
            capabilities={skill_names[0]: 1, skill_names[1]: 1},
        ),
        RobotSpec(
            robot_id="r12",
            capabilities={skill_names[2]: 1, skill_names[3]: 1},
        ),
    )
    task_skills = (
        skill_names[0],
        skill_names[0],
        skill_names[1],
        skill_names[1],
        skill_names[2],
        skill_names[2],
        skill_names[3],
        skill_names[4],
    )
    tasks = tuple(
        TaskSpec(
            task_id=f"t{index + 1}",
            requirements={skill: 1},
            reward=float(8 - index),
            max_coalition_size=1,
        )
        for index, skill in enumerate(task_skills)
    )
    return ScenarioSpec(
        scenario_id="static_capability/small",
        scenario_type="static_capability",
        robots=robots,
        tasks=tasks,
    )


def static_capability_seeded_random(
    config: ResolvedConfig, streams: RandomStreams
) -> ScenarioSpec:
    """Return a configurable seeded random static capability instance."""

    return _seeded_random_scenario(
        config,
        streams,
        scenario_id="static_capability/random",
        robot_count=10,
        task_count=6,
        skill_count=4,
    )


def static_capability_scarcity(
    config: ResolvedConfig, streams: RandomStreams
) -> ScenarioSpec:
    """Return a task depending on one scarce capability."""

    del config, streams
    return ScenarioSpec(
        scenario_id="static_capability/scarcity",
        scenario_type="static_capability",
        robots=(
            RobotSpec(robot_id="r1", capabilities={"rare": 1}),
            RobotSpec(robot_id="r2", capabilities={"common": 1}),
            RobotSpec(robot_id="r3", capabilities={"common": 1}),
        ),
        tasks=(TaskSpec(task_id="t1", requirements={"rare": 1}, max_coalition_size=1),),
    )


def static_capability_redundancy(
    config: ResolvedConfig, streams: RandomStreams
) -> ScenarioSpec:
    """Return a task with two interchangeable capable robots."""

    del config, streams
    return ScenarioSpec(
        scenario_id="static_capability/redundancy",
        scenario_type="static_capability",
        robots=(
            RobotSpec(robot_id="r1", capabilities={"lift": 1}),
            RobotSpec(robot_id="r2", capabilities={"lift": 1}),
            RobotSpec(robot_id="r3", capabilities={"other": 1}),
        ),
        tasks=(TaskSpec(task_id="t1", requirements={"lift": 1}, max_coalition_size=1),),
    )


def static_capability_incompatibility(
    config: ResolvedConfig, streams: RandomStreams
) -> ScenarioSpec:
    """Return a task where a capable robot pair is explicitly incompatible."""

    del config, streams
    return ScenarioSpec(
        scenario_id="static_capability/incompatibility",
        scenario_type="static_capability",
        robots=(
            RobotSpec(
                robot_id="r1",
                capabilities={"lift": 1},
                incompatible_robot_ids=("r2",),
            ),
            RobotSpec(
                robot_id="r2",
                capabilities={"lift": 1},
                incompatible_robot_ids=("r1",),
            ),
            RobotSpec(robot_id="r3", capabilities={"lift": 2}),
        ),
        tasks=(TaskSpec(task_id="t1", requirements={"lift": 2}, max_coalition_size=2),),
    )


def static_capability_tied_optimum(
    config: ResolvedConfig, streams: RandomStreams
) -> ScenarioSpec:
    """Return two equivalent robots competing for one equally valued task."""

    del config, streams
    return ScenarioSpec(
        scenario_id="static_capability/tied_optimum",
        scenario_type="static_capability",
        robots=(
            RobotSpec(robot_id="r1", capabilities={"sensor": 1}),
            RobotSpec(robot_id="r2", capabilities={"sensor": 1}),
        ),
        tasks=(
            TaskSpec(
                task_id="t1",
                requirements={"sensor": 1},
                reward=10,
                max_coalition_size=1,
            ),
        ),
    )
