import hashlib
import itertools
import json
from dataclasses import replace

import pytest

from coalition_formation.audit import audit_trace
from coalition_formation.config import ResolvedConfig
from coalition_formation.core.actions import FormCoalitionAction, NoOpAction
from coalition_formation.core.kernel import SimulationKernel
from coalition_formation.core.models import RobotSpec, ScenarioSpec, TaskSpec
from coalition_formation.oracle import OracleLimitError, solve_static
from coalition_formation.registry import construct_scenario
from coalition_formation.rng import RandomStreams


def preset(name):
    return construct_scenario(ResolvedConfig("1.0", f"static_capability/{name}"))


def test_exact_tiny_and_ties():
    result = solve_static(preset("tiny"))
    assert result.optimal_reward == 60
    assert result.optimal_partitions == (
        (("t1", ("r1", "r2")), ("t2", ("r3", "r4")), ("t3", ("r5", "r6"))),
    )
    ties = solve_static(preset("tied_optimum"))
    assert ties.optimal_reward == 10
    assert ties.optimal_partitions == ((("t1", ("r1",)),), (("t1", ("r2",)),))
    assert ties == solve_static(preset("tied_optimum"))
    json.dumps(result.to_dict())


def test_oracle_empty_negative_zero_and_limits():
    assert solve_static(ScenarioSpec("empty")).optimal_partitions == ((),)
    scenario = ScenarioSpec(
        "s", robots=(RobotSpec("r"),), tasks=(TaskSpec("t", reward=-1),)
    )
    assert solve_static(scenario).optimal_partitions == ((),)
    assert (
        len(solve_static(replace(scenario, tasks=(TaskSpec("t"),))).optimal_partitions)
        == 2
    )
    with pytest.raises(OracleLimitError):
        solve_static(preset("small"))
    with pytest.raises(OracleLimitError):
        solve_static(preset("tiny"), max_states=1)
    with pytest.raises(ValueError, match="simultaneous"):
        solve_static(replace(scenario, horizon=10))


@pytest.mark.parametrize("seed", range(30))
def test_generated_static_oracle_matches_robot_label_enumeration(seed):
    # Independent exhaustive reference labels each robot unused, task 0, or task 1.
    rng = RandomStreams(seed).generator("scenario")
    scenario = ScenarioSpec(
        "generated",
        robots=tuple(
            RobotSpec(f"r{i}", capabilities={"a": int(rng.integers(0, 3))})
            for i in range(4)
        ),
        tasks=tuple(
            TaskSpec(
                f"t{i}",
                requirements={"a": int(rng.integers(0, 7))},
                reward=int(rng.integers(-1, 4)),
            )
            for i in range(2)
        ),
    )
    best, winners = 0, set()
    for labels in itertools.product((-1, 0, 1), repeat=4):
        partition, reward = [], 0
        for i, task in enumerate(scenario.tasks):
            members = tuple(
                r
                for r, label in zip(scenario.robots, labels, strict=True)
                if label == i
            )
            if not members:
                continue
            if sum(r.capabilities["a"] for r in members) < task.requirements["a"]:
                break
            partition.append((task.task_id, tuple(r.robot_id for r in members)))
            reward += task.reward
        else:
            if reward > best:
                best, winners = reward, {tuple(partition)}
            elif reward == best:
                winners.add(tuple(partition))
    result = solve_static(scenario)
    assert result.optimal_reward == best
    assert result.optimal_partitions == tuple(sorted(winners))


def sample():
    scenario = ScenarioSpec(
        "audit",
        robots=(RobotSpec("r", capabilities={"a": 1}),),
        tasks=(TaskSpec("t", requirements={"a": 1}, workload=2),),
    )
    kernel = SimulationKernel(scenario)
    kernel.step(FormCoalitionAction("c", "t", ("r",)))
    kernel.step(NoOpAction())
    return scenario, kernel


def test_valid_trace_and_jsonl_have_identical_audits(tmp_path):
    scenario, kernel = sample()
    path = tmp_path / "trace.jsonl"
    path.write_text(kernel.trace.to_jsonl())
    report = audit_trace(scenario, kernel.trace)
    assert report.findings == ()
    assert report == audit_trace(scenario, path)
    json.dumps(report.to_dict())


def rehash(records):
    for i, record in enumerate(records):
        record["post_state_hash"] = hashlib.sha256(
            json.dumps(record["state"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if i:
            record["pre_state_hash"] = records[i - 1]["post_state_hash"]


@pytest.mark.parametrize(
    "invariant",
    [
        "capability_sufficiency",
        "coalition_bounds",
        "resource_conservation",
        "task_transitions",
        "terminal_consistency",
    ],
)
def test_corrupted_fixtures_report_only_expected_invariant(invariant, tmp_path):
    scenario, kernel = sample()
    records = [e.to_dict() for e in kernel.events]
    if invariant in {"capability_sufficiency", "coalition_bounds"}:
        task = replace(
            scenario.tasks[0],
            **(
                {"requirements": {"a": 2}}
                if invariant == "capability_sufficiency"
                else {"min_coalition_size": 2}
            ),
        )
        scenario = replace(scenario, tasks=(task,))
        records[0]["payload"]["scenario"] = scenario.to_dict()
    elif invariant == "resource_conservation":
        records[-1]["state"]["robots"]["r"]["resources"] = {"created": 1.0}
    elif invariant == "task_transitions":
        records[-1]["state"]["tasks"]["t"]["status"] = "cancelled"
    else:
        records[-1]["payload"]["status"] = "failed"
    rehash(records)
    report = audit_trace(scenario, records)
    assert {f.invariant for f in report.findings} == {invariant}
    path = tmp_path / "corrupt.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    assert audit_trace(scenario, path) == report


def test_exclusivity_reconstructed_from_events():
    scenario = ScenarioSpec(
        "overlap",
        robots=(RobotSpec("r", max_concurrent_tasks=2),),
        tasks=(TaskSpec("a", workload=5), TaskSpec("b", workload=5)),
    )
    kernel = SimulationKernel(scenario)
    kernel.step(FormCoalitionAction("a", "a", ("r",)))
    kernel.step(FormCoalitionAction("b", "b", ("r",)))
    scenario = replace(scenario, robots=(RobotSpec("r"),))
    records = [e.to_dict() for e in kernel.events]
    records[0]["payload"]["scenario"] = scenario.to_dict()
    assert {
        f.invariant
        for f in audit_trace(scenario, records, require_terminal=False).findings
    } == {"robot_exclusivity"}


def test_malformed_and_partial_traces(tmp_path):
    scenario, kernel = sample()
    path = tmp_path / "invalid.jsonl"
    path.write_text("{broken\n")
    assert not audit_trace(scenario, path).passed
    assert not audit_trace(scenario, []).passed
    records = [e.to_dict() for e in kernel.events[:-1]]
    assert audit_trace(scenario, records, require_terminal=False).passed
    assert not audit_trace(scenario, records).passed


@pytest.mark.parametrize("seed", range(20))
def test_generated_audit_capability_property(seed):
    rng = RandomStreams(seed).generator("scenario")
    capacity = int(rng.integers(1, 5))
    demand = int(rng.integers(0, 7))
    scenario = ScenarioSpec(
        "generated",
        robots=(RobotSpec("r", capabilities={"a": capacity}),),
        tasks=(TaskSpec("t"),),
    )
    kernel = SimulationKernel(scenario)
    kernel.step(FormCoalitionAction("c", "t", ("r",)))
    records = [e.to_dict() for e in kernel.events]
    scenario = replace(scenario, tasks=(TaskSpec("t", requirements={"a": demand}),))
    records[0]["payload"]["scenario"] = scenario.to_dict()
    findings = audit_trace(scenario, records).findings
    assert {f.invariant for f in findings} == (
        {"capability_sufficiency"} if demand > capacity else set()
    )


def test_oracle_incompatibility_and_resource_feasibility():
    scenario = preset("incompatibility")
    result = solve_static(
        replace(scenario, tasks=(replace(scenario.tasks[0], reward=1),))
    )
    assert all("r3" in p[0][1] for p in result.optimal_partitions)
    scenario = ScenarioSpec(
        "resources",
        robots=(RobotSpec("r", resources={"energy": 1}),),
        tasks=(TaskSpec("t", resource_requirements={"energy": 2}, reward=3),),
    )
    assert solve_static(scenario).optimal_reward == 0
