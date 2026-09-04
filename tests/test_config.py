import json

import pytest

from coalition_formation.config import (
    CONFIG_SCHEMA_VERSION,
    ConfigurationError,
    ResolvedConfig,
    export_resolved_config,
    load_config,
)
from coalition_formation.core.types import MAX_SEED
from coalition_formation.rng import RandomStreams


def test_config_requires_version_and_materializes_defaults() -> None:
    config = ResolvedConfig.from_mapping(
        {"schema_version": CONFIG_SCHEMA_VERSION, "scenario": "example"}
    )

    assert config.to_dict() == {
        "schema_version": "1.0",
        "scenario": "example",
        "seed": 0,
        "policy_seed": 0,
        "parameters": {},
    }
    assert json.loads(config.to_json()) == config.to_dict()


def test_unknown_or_missing_schema_versions_fail_actionably() -> None:
    with pytest.raises(ConfigurationError, match="missing required schema_version"):
        ResolvedConfig.from_mapping({"scenario": "example"})
    with pytest.raises(ConfigurationError, match="unsupported schema_version"):
        ResolvedConfig.from_mapping({"schema_version": "2.0", "scenario": "example"})


def test_json_and_yaml_files_load_to_the_same_resolved_config(tmp_path) -> None:
    config_data = {
        "schema_version": "1.0",
        "scenario": "static_capability/random",
        "seed": 17,
        "parameters": {"robot_count": 4, "task_count": 2, "skill_count": 3},
    }
    json_path = tmp_path / "config.json"
    yaml_path = tmp_path / "config.yaml"
    json_path.write_text(json.dumps(config_data), encoding="utf-8")
    yaml_path.write_text(
        "schema_version: '1.0'\n"
        "scenario: static_capability/random\n"
        "seed: 17\n"
        "parameters:\n"
        "  robot_count: 4\n"
        "  task_count: 2\n"
        "  skill_count: 3\n",
        encoding="utf-8",
    )

    json_config = load_config(json_path)
    yaml_config = load_config(yaml_path)
    assert json_config == yaml_config

    resolved_path = tmp_path / "resolved.json"
    export_resolved_config(yaml_config, resolved_path)
    assert load_config(resolved_path) == yaml_config


def test_configuration_rejects_unknown_fields_and_non_json_parameters() -> None:
    with pytest.raises(ConfigurationError, match="unknown configuration field"):
        ResolvedConfig.from_mapping(
            {"schema_version": "1.0", "scenario": "example", "extra": True}
        )
    with pytest.raises(ConfigurationError, match="JSON-compatible"):
        ResolvedConfig(
            schema_version="1.0",
            scenario="example",
            parameters={"not_json": object()},
        )


def test_configuration_and_rng_share_the_same_seed_limit() -> None:
    config = ResolvedConfig(
        schema_version="1.0",
        scenario="example",
        seed=MAX_SEED,
        policy_seed=MAX_SEED,
    )
    streams = RandomStreams(config.seed, config.policy_seed)
    streams.generator("scenario").integers(0, 10)

    with pytest.raises(ConfigurationError, match="between 0 and"):
        ResolvedConfig(schema_version="1.0", scenario="example", seed=MAX_SEED + 1)
    with pytest.raises(ValueError, match="between 0 and"):
        RandomStreams(MAX_SEED + 1)
