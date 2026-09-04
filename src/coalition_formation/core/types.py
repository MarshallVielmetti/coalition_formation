"""Shared type aliases for the domain model."""

from __future__ import annotations

from typing import TypeAlias

EntityId: TypeAlias = str
Tick: TypeAlias = int
Point: TypeAlias = tuple[float, float]

JsonPrimitive: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
