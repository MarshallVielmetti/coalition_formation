"""Independent checks of allocation traces; no kernel transition calls."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .core.models import (
    RobotState,
    ScenarioSpec,
    TaskState,
    TaskStatus,
    WorldState,
)
from .core.trace import EventRecord, EventTrace, EventType
from .core.types import JsonObject


@dataclass(frozen=True)
class Finding:
    severity: str
    tick: int
    entity_ids: tuple[str, ...]
    invariant: str
    evidence: str
    sequence: int

    def to_dict(self) -> JsonObject:
        return {
            "severity": self.severity,
            "tick": self.tick,
            "entity_ids": list(self.entity_ids),
            "invariant": self.invariant,
            "evidence": self.evidence,
            "sequence": self.sequence,
        }


@dataclass(frozen=True)
class AuditResult:
    findings: tuple[Finding, ...]
    events_checked: int

    @property
    def passed(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)

    def to_dict(self) -> JsonObject:
        return {
            "passed": self.passed,
            "events_checked": self.events_checked,
            "findings": [f.to_dict() for f in self.findings],
        }


def _hash(world: WorldState) -> str:
    return hashlib.sha256(
        json.dumps(world.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def audit_trace(
    scenario: ScenarioSpec,
    source: EventTrace | Iterable[EventRecord | Mapping[str, object]] | str | Path,
    *,
    require_terminal: bool = True,
) -> AuditResult:
    """Audit snapshots and reconstruct ownership from assignment/disband events.

    Paths are parsed as raw JSONL so corrupt records produce findings rather
    than being rejected by EventTrace's constructor. Partial traces must opt
    out of the final terminal check. Resource conservation follows PR04's
    non-consuming allocation semantics: balances must remain unchanged.
    """
    if isinstance(source, (str, Path)):
        records: list[object] = []
        for line in Path(source).read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    records.append(json.loads(line))
                except ValueError:
                    records.append(None)
    else:
        items = source.events if isinstance(source, EventTrace) else source
        records = [
            e.to_dict() if isinstance(e, EventRecord) else dict(e) for e in items
        ]
    findings: list[Finding] = []
    robots = {r.robot_id: r for r in scenario.robots}
    tasks = {t.task_id: t for t in scenario.tasks}
    previous = WorldState(
        robots={
            r.robot_id: RobotState(
                r.robot_id, position=r.position, resources=r.resources
            )
            for r in scenario.robots
        },
        tasks={t.task_id: TaskState(t.task_id) for t in scenario.tasks},
    )
    # Reconstructed exclusively from event payloads, never snapshot assignments.
    assignments: dict[str, tuple[str, tuple[str, ...]]] = {}
    seen_coalitions: set[str] = set()
    last_key = (-1, -1, -1)
    terminated = False
    tick = 0
    sequence = -1

    def report(
        invariant: str, evidence: str, *ids: str, severity: str = "error"
    ) -> None:
        findings.append(
            Finding(severity, tick, tuple(sorted(ids)), invariant, evidence, sequence)
        )

    for index, raw in enumerate(records):
        sequence = index
        if not isinstance(raw, Mapping):
            report("trace_schema", "record must be a JSON object")
            continue
        try:
            tick_value, priority, seq = (
                raw[k] for k in ("tick", "event_priority", "insertion_sequence")
            )
            if any(type(v) is not int or v < 0 for v in (tick_value, priority, seq)):
                raise ValueError("invalid event ordering fields")
            tick, priority, sequence = int(tick_value), int(priority), int(seq)
            kind = str(raw["event_type"])
            EventType(kind)
            payload = raw["payload"]
            if not isinstance(payload, Mapping) or raw.get("schema_version") != "1.0":
                raise ValueError("unsupported schema or invalid payload")
            state_data = raw["state"]
            if not isinstance(state_data, Mapping):
                raise ValueError("missing state snapshot")
            world = WorldState.from_dict(state_data)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            report("trace_schema", str(error))
            continue
        key = (tick, priority, sequence)
        if key <= last_key or sequence != index:
            report(
                "event_order", f"key {key} after {last_key}; expected sequence {index}"
            )
        last_key = key
        if raw.get("pre_state_hash") != _hash(previous) or raw.get(
            "post_state_hash"
        ) != _hash(world):
            report("state_hash", "snapshot or preceding state hash mismatch")
        if set(world.robots) != set(robots) or set(world.tasks) != set(tasks):
            report("entity_ids", "snapshot entity set differs from scenario")
            continue
        if index == 0:
            if (
                kind != "reset"
                or world != previous
                or payload.get("scenario") != scenario.to_dict()
            ):
                report("reset", "reset snapshot/specification differs from scenario")
        elif kind == "reset":
            report("reset", "unexpected reset inside a trace")
        if terminated and world != previous:
            report("terminal_consistency", "state changed after termination")
        if kind == "assignment":
            task_id, coalition_id = payload.get("task_id"), payload.get("coalition_id")
            ids = payload.get("robot_ids")
            if (
                not isinstance(task_id, str)
                or task_id not in tasks
                or not isinstance(coalition_id, str)
                or not coalition_id
                or not isinstance(ids, list)
                or any(not isinstance(r, str) or r not in robots for r in ids)
            ):
                report("entity_ids", "assignment references invalid IDs")
            else:
                members = tuple(cast(list[str], ids))
                task = tasks[task_id]
                if coalition_id in seen_coalitions:
                    report(
                        "assignment_consistency", "coalition ID reused", coalition_id
                    )
                if any(t == task_id for t, _ in assignments.values()):
                    report("assignment_consistency", "task assigned twice", task_id)
                for r in members:
                    if any(r in rs for _, rs in assignments.values()):
                        report("robot_exclusivity", "robot already assigned", r)
                if len(set(members)) != len(members) or not (
                    task.min_coalition_size
                    <= len(members)
                    <= (task.max_coalition_size or len(robots))
                ):
                    report("coalition_bounds", "invalid membership count", coalition_id)
                if any(
                    set(robots[r].incompatible_robot_ids).intersection(members)
                    for r in members
                ):
                    report(
                        "robot_compatibility",
                        "incompatible coalition members",
                        coalition_id,
                    )
                for skill, amount in task.requirements.items():
                    if (
                        sum(robots[r].capabilities.get(skill, 0) for r in members)
                        < amount
                    ):
                        report(
                            "capability_sufficiency",
                            f"insufficient {skill}",
                            task_id,
                            coalition_id,
                        )
                for resource, amount in task.resource_requirements.items():
                    if (
                        sum(
                            previous.robots[r].resources.get(resource, 0)
                            for r in members
                        )
                        < amount
                    ):
                        report(
                            "resource_sufficiency",
                            f"insufficient {resource}",
                            task_id,
                            coalition_id,
                        )
                if tick < task.release_tick or (
                    task.time_window
                    and not task.time_window.start_tick
                    <= tick
                    < task.time_window.end_tick
                ):
                    report("task_timing", "assignment outside release/window", task_id)
                if any(
                    previous.tasks[d.predecessor_id].status != TaskStatus.COMPLETED
                    for d in scenario.dependencies
                    if d.successor_id == task_id
                ):
                    report("task_dependencies", "unfinished predecessor", task_id)
                assignments[coalition_id] = (task_id, members)
                seen_coalitions.add(coalition_id)
        elif kind == "coalition_disbanded":
            cid = payload.get("coalition_id")
            if not isinstance(cid, str) or cid not in assignments:
                report("assignment_consistency", "disband of unknown coalition")
            else:
                del assignments[cid]
        # Compare every snapshot to the independently reconstructed ownership.
        for r, robot_state in world.robots.items():
            expected = sorted(c for c, (_, rs) in assignments.items() if r in rs)
            expected_tasks = sorted(t for t, rs in assignments.values() if r in rs)
            if (
                list(robot_state.coalition_ids) != expected
                or list(robot_state.assigned_task_ids) != expected_tasks
            ):
                report(
                    "assignment_consistency", "robot ownership differs from events", r
                )
            if robot_state.resources != robots[r].resources:
                report(
                    "resource_conservation",
                    "resource balance changed without consumption events",
                    r,
                )
        for cid, (tid, members) in assignments.items():
            coalition = world.coalitions.get(cid)
            if (
                coalition is None
                or coalition.task_id != tid
                or coalition.robot_ids != tuple(sorted(members))
                or world.tasks[tid].assigned_coalition_id != cid
            ):
                report(
                    "assignment_consistency",
                    "coalition/task ownership differs from events",
                    cid,
                )
        allowed = {
            "task_release": (TaskStatus.PENDING, TaskStatus.RELEASED),
            "assignment": (TaskStatus.RELEASED, TaskStatus.ASSIGNED),
            "coalition_formed": (TaskStatus.ASSIGNED, TaskStatus.ACTIVE),
            "completion": (TaskStatus.ACTIVE, TaskStatus.COMPLETED),
        }
        target = payload.get("task_id")
        if kind in allowed:
            if not isinstance(target, str) or target not in tasks:
                report("entity_ids", "task event references unknown task")
            elif (previous.tasks[target].status, world.tasks[target].status) != allowed[
                kind
            ]:
                report(
                    "task_transitions",
                    "event does not perform its declared transition",
                    target,
                )
        for cid, coalition in world.coalitions.items():
            if cid not in seen_coalitions:
                report(
                    "assignment_consistency", "coalition has no assignment event", cid
                )
            if cid not in assignments and coalition.status != "disbanded":
                report(
                    "assignment_consistency",
                    "unassigned coalition is not disbanded",
                    cid,
                )
        if kind in {"proposal", "no_op", "policy_error"} and world != previous:
            report("event_effect", "non-mutating event changed state")
        for tid, state in world.tasks.items():
            old = previous.tasks[tid]
            owners = [c for c, (t, _) in assignments.items() if t == tid]
            if state.assigned_coalition_id != (owners[0] if owners else None):
                report(
                    "assignment_consistency", "task ownership differs from events", tid
                )
            if state.status != old.status:
                valid = tid == target and (
                    allowed.get(kind) == (old.status, state.status)
                    or (
                        kind == "failure"
                        and old.status
                        in {
                            TaskStatus.PENDING,
                            TaskStatus.RELEASED,
                            TaskStatus.ASSIGNED,
                            TaskStatus.ACTIVE,
                        }
                        and state.status == TaskStatus.FAILED
                    )
                    or (
                        kind == "coalition_disbanded"
                        and old.status in {TaskStatus.ACTIVE, TaskStatus.ASSIGNED}
                        and state.status == TaskStatus.RELEASED
                    )
                )
                if not valid:
                    report(
                        "task_transitions",
                        f"{old.status} -> {state.status} at {kind}",
                        tid,
                    )
            if state.progress != old.progress and (
                kind != "work" or tid != target or old.status != TaskStatus.ACTIVE
            ):
                report("task_transitions", "progress changed without active work", tid)
            if state.status == TaskStatus.COMPLETED and (
                state.progress != 1 or state.completion_tick is None
            ):
                report(
                    "task_transitions",
                    "completion missing full progress/timestamp",
                    tid,
                )
        if (
            world.terminal_status != previous.terminal_status
            and kind != "simulation_termination"
        ):
            report(
                "terminal_consistency",
                "terminal status changed without termination event",
            )
        if kind == "simulation_termination":
            terminated = True
            if (
                world.terminal_status is None
                or payload.get("status") != world.terminal_status
            ):
                report("terminal_consistency", "terminal event and snapshot disagree")
            if world.terminal_status == "succeeded":
                if payload.get("reason") == "termination model requested stop":
                    report(
                        "custom_termination",
                        "custom predicate cannot be independently certified",
                        severity="warning",
                    )
                elif any(
                    t.status not in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}
                    for t in world.tasks.values()
                ):
                    report("terminal_consistency", "success with unfinished tasks")
            if world.terminal_status == "failed" and not any(
                t.status == TaskStatus.FAILED for t in world.tasks.values()
            ):
                report("terminal_consistency", "failure without failed tasks")
        previous = world
    if not records:
        report("trace_schema", "empty trace")
    elif require_terminal and not terminated:
        report("terminal_consistency", "trace has no termination event")
    return AuditResult(tuple(findings), len(records))
