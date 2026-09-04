# Domain model and plugin protocols

PR 02 establishes the typed vocabulary used by later simulation layers. It is
intentionally a data and interface layer: it does not load configurations,
advance a clock, allocate robots, or execute tasks. PR 03 adds NumPy and PyYAML
outside this core module for deterministic streams and configuration loading;
the domain models and protocols themselves remain standard-library only.

## Identity, units, and defaults

- `robot_id`, `task_id`, `coalition_id`, and `scenario_id` are stable,
  non-empty strings. Entity mappings must use the same ID as the mapped value.
- `TimeWindow` is a half-open interval `[start_tick, end_tick)` of
  nonnegative integer ticks. A window must have a strictly later end tick.
- Positions are two-element `(x, y)` tuples in scenario units. Robot speed is
  scenario units per tick. Coordinates and speed must be finite; speed may be
  zero for a stationary robot.
- Capabilities, requirements, and resource quantities are finite,
  nonnegative floats. Empty mappings mean that no quantity is specified.
- `RobotSpec.incompatible_robot_ids` contains symmetric robot-level exclusions;
  every referenced ID must exist in the enclosing `ScenarioSpec`.
- Robot specifications default to type `generic`, speed `1.0`, and one
  concurrent task. Tasks default to type `generic`, release tick `0`, workload
  `1.0`, reward `0.0`, and coalition size bounds `[1, unbounded]`.
- A coalition is task-oriented and must contain at least one unique robot ID.
  Runtime progress is normalized to `[0.0, 1.0]`, and health is a
  nonnegative quantity whose interpretation remains domain-specific.

## Immutability and equality

All models and actions are frozen dataclasses. Mappings are copied and exposed
through read-only mapping proxies; ID collections are copied into sorted
tuples. `ScenarioSpec`, `WorldState`, and `Observation` also canonicalize
entity mappings by ID. Equality is structural dataclass equality after these
normalizations, so declaration order does not change the identity of a
collection. Policies receive `Observation`, never mutable kernel state.

## Serialization

Every public model and action provides `to_dict()` and the corresponding model
provides `from_dict()` (actions use `action_from_dict`). The returned objects
contain only JSON-compatible dictionaries, lists, strings, numbers, booleans,
and nulls. Enum fields serialize to their explicit string values. For example:

```python
import json

from coalition_formation.core.models import RobotSpec

robot = RobotSpec(robot_id="r1", capabilities={"lifting": 2})
encoded = robot.to_dict()
json.dumps(encoded)
assert RobotSpec.from_dict(encoded) == robot
```

The model layer introduces no event or trace schema. Later configuration and
kernel PRs must version those schemas when they are added.

## Protocols

`core.protocols` uses `typing.Protocol`, so plugins implement the contracts by
matching method signatures and do not subclass a framework class. The
contracts cover coalition feasibility and value, travel, task dynamics,
observations, communication, allocation policies, metrics, and termination.
Optional visualization, graph, optimization, RL, and web dependencies are not
imported by this core layer.
