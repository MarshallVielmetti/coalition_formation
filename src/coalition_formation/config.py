"""Versioned configuration loading and resolved-default export."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import cast

import yaml  # type: ignore[import-untyped]

from .core.types import JsonObject, JsonValue

CONFIG_SCHEMA_VERSION = "1.0"


class ConfigurationError(ValueError):
    """Raised when a configuration is missing or contains invalid fields."""


def _require_nonempty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{field_name} must be a non-empty string")
    return value


def _require_seed(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{field_name} must be a nonnegative integer")
    if value < 0:
        raise ConfigurationError(f"{field_name} must be a nonnegative integer")
    return value


def _freeze_parameters(
    parameters: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    if not isinstance(parameters, Mapping):
        raise ConfigurationError("parameters must be a mapping")
    if any(not isinstance(key, str) or not key for key in parameters):
        raise ConfigurationError("parameter keys must be non-empty strings")
    try:
        normalized = json.loads(
            json.dumps(
                dict(parameters),
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError) as error:
        raise ConfigurationError(
            "parameters must contain JSON-compatible values"
        ) from error
    if not isinstance(normalized, dict):
        raise ConfigurationError("parameters must be a mapping")
    return cast(Mapping[str, JsonValue], MappingProxyType(normalized))


@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    """Configuration with all defaults materialized explicitly."""

    schema_version: str
    scenario: str
    seed: int = 0
    policy_seed: int | None = None
    parameters: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != CONFIG_SCHEMA_VERSION:
            raise ConfigurationError(
                f"unsupported schema_version {self.schema_version!r}; "
                f"expected {CONFIG_SCHEMA_VERSION!r}"
            )
        _require_nonempty_string(self.scenario, "scenario")
        object.__setattr__(self, "seed", _require_seed(self.seed, "seed"))
        policy_seed = self.seed if self.policy_seed is None else self.policy_seed
        object.__setattr__(
            self, "policy_seed", _require_seed(policy_seed, "policy_seed")
        )
        object.__setattr__(self, "parameters", _freeze_parameters(self.parameters))

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> ResolvedConfig:
        """Validate a raw mapping and resolve its defaults."""

        if not isinstance(data, Mapping):
            raise ConfigurationError("configuration root must be a mapping")
        if "schema_version" not in data:
            raise ConfigurationError(
                f"missing required schema_version; expected {CONFIG_SCHEMA_VERSION!r}"
            )
        allowed = {"schema_version", "scenario", "seed", "policy_seed", "parameters"}
        unknown = set(data) - allowed
        if unknown:
            names = ", ".join(sorted(str(name) for name in unknown))
            raise ConfigurationError(f"unknown configuration field(s): {names}")
        raw_parameters = data.get("parameters", {})
        if not isinstance(raw_parameters, Mapping):
            raise ConfigurationError("parameters must be a mapping")
        return cls(
            schema_version=_require_nonempty_string(
                data["schema_version"], "schema_version"
            ),
            scenario=_require_nonempty_string(data.get("scenario"), "scenario"),
            seed=_require_seed(data.get("seed", 0), "seed"),
            policy_seed=(
                None
                if data.get("policy_seed") is None
                else _require_seed(data["policy_seed"], "policy_seed")
            ),
            parameters=cast(dict[str, JsonValue], dict(raw_parameters)),
        )

    def to_dict(self) -> JsonObject:
        """Return a JSON-compatible mapping with defaults explicitly present."""

        return {
            "schema_version": self.schema_version,
            "scenario": self.scenario,
            "seed": self.seed,
            "policy_seed": self.policy_seed,
            "parameters": dict(self.parameters),
        }

    def to_json(self) -> str:
        """Export deterministic JSON for manifests and reproducibility checks."""

        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"

    def to_yaml(self) -> str:
        """Export resolved configuration as YAML."""

        return cast(str, yaml.safe_dump(self.to_dict(), sort_keys=True))


def load_config(source: str | Path) -> ResolvedConfig:
    """Load and resolve a `.json`, `.yaml`, or `.yml` configuration file."""

    path = Path(source)
    raw_text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        decoded: object = json.loads(raw_text)
    elif suffix in {".yaml", ".yml"}:
        decoded = yaml.safe_load(raw_text)
    else:
        raise ConfigurationError(
            f"unsupported configuration extension {path.suffix!r}; "
            "use .json, .yaml, or .yml"
        )
    if not isinstance(decoded, Mapping):
        raise ConfigurationError("configuration root must be a mapping")
    return ResolvedConfig.from_mapping(cast(Mapping[str, object], decoded))


def export_resolved_config(config: ResolvedConfig, destination: str | Path) -> None:
    """Write a resolved configuration using the destination file extension."""

    path = Path(destination)
    suffix = path.suffix.lower()
    if suffix == ".json":
        content = config.to_json()
    elif suffix in {".yaml", ".yml"}:
        content = config.to_yaml()
    else:
        raise ConfigurationError(
            f"unsupported configuration extension {path.suffix!r}; "
            "use .json, .yaml, or .yml"
        )
    path.write_text(content, encoding="utf-8")
