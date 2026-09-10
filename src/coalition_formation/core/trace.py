"""Versioned event traces and deterministic state fingerprints.

The trace module deliberately knows only about the immutable core models.  It
does not import a scenario factory, a policy implementation, or a renderer.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import cast

from .models import WorldState
from .types import JsonObject, JsonValue

TRACE_SCHEMA_VERSION = "1.0"


class EventType(StrEnum):
    """Stable event discriminators used by the allocation kernel."""

    RESET = "reset"
    TASK_RELEASE = "task_release"
    TASK_RELEASED = "task_release"
    PROPOSAL = "proposal"
    ASSIGNMENT = "assignment"
    COALITION_FORMED = "coalition_formed"
    COALITION_DISBANDED = "coalition_disbanded"
    COALITION_DISBAND = "coalition_disbanded"
    WORK = "work"
    COMPLETION = "completion"
    TASK_COMPLETED = "completion"
    FAILURE = "failure"
    TASK_FAILED = "failure"
    POLICY_ERROR = "policy_error"
    NO_OP = "no_op"
    TICK_ADVANCE = "tick_advance"
    SIMULATION_TERMINATION = "simulation_termination"
    TERMINATION = "simulation_termination"


def state_hash(state: WorldState) -> str:
    """Return a stable SHA-256 fingerprint of a world snapshot."""

    encoded = json.dumps(state.to_dict(), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _copy_json_object(value: Mapping[str, object]) -> JsonObject:
    """Validate and detach an event payload through the JSON codec."""

    try:
        decoded: object = json.loads(
            json.dumps(dict(value), allow_nan=False, sort_keys=True)
        )
    except (TypeError, ValueError) as error:
        raise TypeError("event payload must be JSON-compatible") from error
    if not isinstance(decoded, dict):
        raise TypeError("event payload must be a JSON object")
    return cast(JsonObject, decoded)


@dataclass(frozen=True, slots=True)
class EventRecord:
    """One append-only, replayable event.

    ``state`` is a complete post-event snapshot.  Keeping the snapshot in the
    trace makes replay independent of the policy and also gives auditors a
    sufficient replay record even when a future event type is unknown to an
    older reader.
    """

    event_type: EventType
    tick: int
    event_priority: int
    insertion_sequence: int
    payload: Mapping[str, JsonValue] = field(default_factory=dict)
    pre_state_hash: str = ""
    post_state_hash: str = ""
    state: WorldState | None = None
    schema_version: str = TRACE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, EventType):
            object.__setattr__(self, "event_type", EventType(self.event_type))
        if (
            isinstance(self.tick, bool)
            or not isinstance(self.tick, int)
            or self.tick < 0
        ):
            raise ValueError("tick must be a nonnegative integer")
        if (
            isinstance(self.event_priority, bool)
            or not isinstance(self.event_priority, int)
            or self.event_priority < 0
        ):
            raise ValueError("event_priority must be a nonnegative integer")
        if (
            isinstance(self.insertion_sequence, bool)
            or not isinstance(self.insertion_sequence, int)
            or self.insertion_sequence < 0
        ):
            raise ValueError("insertion_sequence must be a nonnegative integer")
        if self.schema_version != TRACE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported trace schema_version {self.schema_version!r}; "
                f"expected {TRACE_SCHEMA_VERSION!r}"
            )
        object.__setattr__(
            self, "payload", MappingProxyType(_copy_json_object(self.payload))
        )
        if self.state is not None:
            calculated_hash = state_hash(self.state)
            if self.post_state_hash and self.post_state_hash != calculated_hash:
                raise ValueError("post_state_hash does not match event state")
            object.__setattr__(self, "post_state_hash", calculated_hash)

    @property
    def priority(self) -> int:
        """Alias for the event-priority field."""

        return self.event_priority

    @property
    def sequence(self) -> int:
        """Alias for the insertion-sequence field."""

        return self.insertion_sequence

    @property
    def post_state(self) -> WorldState | None:
        """Alias for the complete post-event replay snapshot."""

        return self.state

    def ordering_key(self) -> tuple[int, int, int]:
        """Return the deterministic ordering key required by the kernel."""

        return (self.tick, self.event_priority, self.insertion_sequence)

    def to_dict(self) -> JsonObject:
        """Serialize the event, including its replay snapshot."""

        result: JsonObject = {
            "schema_version": self.schema_version,
            "event_type": self.event_type.value,
            "tick": self.tick,
            "event_priority": self.event_priority,
            "insertion_sequence": self.insertion_sequence,
            "payload": cast(JsonValue, dict(self.payload)),
            "pre_state_hash": self.pre_state_hash,
            "post_state_hash": self.post_state_hash,
        }
        if self.state is not None:
            result["state"] = self.state.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> EventRecord:
        payload = data.get("payload", {})
        if not isinstance(payload, Mapping):
            raise TypeError("event payload must be a mapping")
        raw_state = data.get("state")
        state: WorldState | None = None
        if raw_state is not None:
            if not isinstance(raw_state, Mapping):
                raise TypeError("event state must be a mapping")
            state = WorldState.from_dict(cast(Mapping[str, object], raw_state))
        return cls(
            schema_version=cast(str, data.get("schema_version", TRACE_SCHEMA_VERSION)),
            event_type=EventType(cast(str, data["event_type"])),
            tick=cast(int, data["tick"]),
            event_priority=cast(
                int, data.get("event_priority", data.get("priority", 0))
            ),
            insertion_sequence=cast(
                int, data.get("insertion_sequence", data.get("sequence", 0))
            ),
            payload=cast(JsonObject, payload),
            pre_state_hash=cast(str, data.get("pre_state_hash", "")),
            post_state_hash=cast(str, data.get("post_state_hash", "")),
            state=state,
        )


@dataclass(frozen=True, slots=True)
class EventTrace:
    """An ordered immutable collection of replayable events."""

    events: tuple[EventRecord, ...] = ()

    def __post_init__(self) -> None:
        events = tuple(self.events)
        keys = tuple(event.ordering_key() for event in events)
        if keys != tuple(sorted(keys)):
            raise ValueError("events must be ordered by tick, priority, and sequence")
        sequences = tuple(event.insertion_sequence for event in events)
        if len(set(sequences)) != len(sequences):
            raise ValueError("events must have unique insertion sequences")
        object.__setattr__(self, "events", events)

    @property
    def final_state(self) -> WorldState | None:
        """Return the last recorded state, if the trace contains one."""

        for event in reversed(self.events):
            if event.state is not None:
                return event.state
        return None

    def replay(self, initial_state: WorldState | None = None) -> WorldState:
        """Reconstruct and hash-check the final state without a policy."""

        current = initial_state
        for event in self.events:
            if current is not None and event.pre_state_hash:
                actual_pre_hash = state_hash(current)
                if actual_pre_hash != event.pre_state_hash:
                    raise ValueError(
                        "trace pre_state_hash mismatch at "
                        f"sequence {event.insertion_sequence}"
                    )
            if event.state is not None:
                current = event.state
            if current is not None and event.post_state_hash:
                actual_post_hash = state_hash(current)
                if actual_post_hash != event.post_state_hash:
                    raise ValueError(
                        "trace post_state_hash mismatch at "
                        f"sequence {event.insertion_sequence}"
                    )
        if current is None:
            raise ValueError("trace contains no replayable state")
        return current

    def to_jsonl(self) -> str:
        """Serialize one event per line with deterministic JSON formatting."""

        return "".join(
            json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
            for event in self.events
        )

    @classmethod
    def from_jsonl(cls, content: str) -> EventTrace:
        """Deserialize a JSON Lines trace from text."""

        events: list[EventRecord] = []
        for line_number, line in enumerate(content.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                decoded: object = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid trace JSON on line {line_number}") from error
            if not isinstance(decoded, Mapping):
                raise ValueError(f"trace line {line_number} must be an object")
            events.append(EventRecord.from_dict(cast(Mapping[str, object], decoded)))
        return cls(tuple(events))


def write_trace(
    trace: EventTrace | Iterable[EventRecord], destination: str | Path
) -> None:
    """Write an event trace as UTF-8 JSON Lines."""

    active_trace = trace if isinstance(trace, EventTrace) else EventTrace(tuple(trace))
    Path(destination).write_text(active_trace.to_jsonl(), encoding="utf-8")


def read_trace(source: str | Path) -> EventTrace:
    """Read an event trace from a UTF-8 JSON Lines file."""

    return EventTrace.from_jsonl(Path(source).read_text(encoding="utf-8"))


write_jsonl = write_trace
read_jsonl = read_trace
