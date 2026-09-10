# Deterministic kernel and event trace

PR 04 adds the allocation-only transition layer above the immutable domain
models. `SimulationKernel` owns a `WorldState`; policies see only an immutable
`Observation` and return one typed action per tick. The kernel validates the
whole action before changing the world, so an invalid proposal cannot partially
book a robot, create a coalition, or change a task.

## Running a simulation

```python
from coalition_formation.core.actions import FormCoalitionAction
from coalition_formation.core.kernel import SimulationKernel
from coalition_formation.registry import construct_scenario

scenario = construct_scenario(config)
kernel = SimulationKernel(scenario, policy)
final_state = kernel.run()
```

`reset()` clears the state and trace and releases tasks whose release tick is
zero. `observe()` returns the current policy boundary. `step(action)` applies
one explicit action; when no action is supplied, the configured policy is
called. `run()` resets the kernel and continues until all tasks are terminal,
the scenario horizon is reached, or its explicit `max_steps` limit is
exhausted.

The built-in `UnitWorkDynamics` advances an active task by one unit of work per
tick, normalized by its workload. Custom task dynamics can implement the
existing `TaskDynamics` protocol without changing the kernel.

## Event schema and ordering

Every event is a JSON-compatible, versioned `EventRecord` with:

- `schema_version`, currently `1.0`;
- `event_type`, `tick`, `event_priority`, and `insertion_sequence`;
- the action or transition `payload`;
- `pre_state_hash` and `post_state_hash`; and
- a complete post-event `state` snapshot for policy-independent replay.

Events are appended in the deterministic order
`(tick, event_priority, insertion_sequence)`. Release, proposal, assignment,
formation, work, completion/failure, policy-error, clock-advance, and
termination events use stable priorities. The trace includes reset and
coalition-disbanding events as well. State snapshots make the trace useful to
independent auditors and allow old readers to preserve replay even when they
do not understand a newer payload.

`EventTrace.to_jsonl()` and `EventTrace.from_jsonl()` serialize one event per
line. The `write_trace()` and `read_trace()` helpers operate on UTF-8 files:

```python
from coalition_formation.core.trace import read_trace, write_trace

write_trace(kernel.trace, "run.jsonl")
saved_trace = read_trace("run.jsonl")
assert saved_trace.replay() == kernel.world
```

`SimulationKernel.replay(scenario, "run.jsonl")` restores a kernel from the
saved trace without constructing or invoking the original policy.
Kernel replay requires a reset record containing the matching full scenario
specification and checks its initial state hash. Older traces without that
metadata can still be read through `EventTrace`, but kernel replay rejects
them because their specifications cannot be verified. Reset records also
preserve the effective horizon for continuation.

Each tick processes all work events before completion and failure events,
then performs coalition cleanup. This keeps simultaneous completions and
deadline failures in priority order while preserving the state hash chain.

## Failure and terminal behavior

Unknown IDs, early tasks, unmet capability/resource requirements, incompatible
robots, exhausted robot capacity, duplicate coalition IDs, and post-terminal
actions are rejected as `InvalidActionError`. The proposal and a `policy_error`
event are recorded while the rejected action leaves the world unchanged.
Policy-generated invalid actions are recorded and treated as no-ops so a batch
run remains auditable. A completed task releases its coalition automatically;
an explicit disband returns an unfinished task to the released state. A
deadline failure or horizon timeout produces a terminal event.

The kernel imports only the core models, actions, protocols, and trace module.
It does not import Matplotlib, Typer, an optimizer, PettingZoo, or a scenario
factory.
