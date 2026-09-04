"""Typed, immutable actions returned by allocation policies."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias, cast

from .types import JsonObject


class ActionType(StrEnum):
    """Serialized discriminator for typed policy actions."""

    FORM_COALITION = "form_coalition"
    DISBAND_COALITION = "disband_coalition"
    NO_OP = "no_op"


def _require_id(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _freeze_ids(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{field_name} must be an iterable of IDs")
    normalized = tuple(values)
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    for value in normalized:
        _require_id(value, f"{field_name} member")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicate IDs")
    return tuple(sorted(normalized))


@dataclass(frozen=True, slots=True)
class FormCoalitionAction:
    """Request formation of a named coalition for a task."""

    coalition_id: str
    task_id: str
    robot_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_id(self.coalition_id, "coalition_id")
        _require_id(self.task_id, "task_id")
        object.__setattr__(self, "robot_ids", _freeze_ids(self.robot_ids, "robot_ids"))

    def to_dict(self) -> JsonObject:
        return {
            "action_type": ActionType.FORM_COALITION.value,
            "coalition_id": self.coalition_id,
            "task_id": self.task_id,
            "robot_ids": list(self.robot_ids),
        }


@dataclass(frozen=True, slots=True)
class DisbandCoalitionAction:
    """Request that a named coalition be disbanded."""

    coalition_id: str

    def __post_init__(self) -> None:
        _require_id(self.coalition_id, "coalition_id")

    def to_dict(self) -> JsonObject:
        return {
            "action_type": ActionType.DISBAND_COALITION.value,
            "coalition_id": self.coalition_id,
        }


@dataclass(frozen=True, slots=True)
class NoOpAction:
    """A deliberate no-op with a human-readable reason."""

    reason: str = "no-op"

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason must be a non-empty string")

    def to_dict(self) -> JsonObject:
        return {"action_type": ActionType.NO_OP.value, "reason": self.reason}


Action: TypeAlias = FormCoalitionAction | DisbandCoalitionAction | NoOpAction


def action_from_dict(data: Mapping[str, object]) -> Action:
    """Deserialize one typed action from a JSON-compatible mapping."""

    action_type = ActionType(cast(str, data["action_type"]))
    if action_type is ActionType.FORM_COALITION:
        robot_ids = data["robot_ids"]
        if isinstance(robot_ids, (str, bytes)) or not isinstance(robot_ids, Sequence):
            raise TypeError("robot_ids must be a sequence")
        return FormCoalitionAction(
            coalition_id=cast(str, data["coalition_id"]),
            task_id=cast(str, data["task_id"]),
            robot_ids=tuple(cast(str, item) for item in robot_ids),
        )
    if action_type is ActionType.DISBAND_COALITION:
        return DisbandCoalitionAction(coalition_id=cast(str, data["coalition_id"]))
    return NoOpAction(reason=cast(str, data.get("reason", "no-op")))
