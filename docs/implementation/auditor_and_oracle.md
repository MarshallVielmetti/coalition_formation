# Independent trace auditor and static oracle

PR 05 introduces two standard-library APIs:

```python
from coalition_formation.audit import audit_trace
from coalition_formation.oracle import solve_static

report = audit_trace(scenario, kernel.trace)  # or a JSONL file path
assert report.passed, report.to_dict()
answer = solve_static(scenario)
print(answer.optimal_reward, answer.optimal_partitions)
```

## Trace audit contract

The auditor reconstructs coalition/task ownership from assignment and disband
payloads and compares that ownership to every recorded snapshot. It never calls
kernel validation, transitions, or replay. Checks include robot exclusivity,
capabilities, coalition size, incompatibilities, resource sufficiency and
conservation, task transitions, release/window and dependency constraints,
entity identity, hash continuity, ordering, reset metadata, and termination.
It parses JSONL directly so malformed records become structured findings.
The same raw records can be passed as an iterable for corruption diagnostics.

Each finding includes severity, tick, insertion sequence, entity IDs, invariant
name, and evidence. `passed` means there are no error findings; custom termination
predicates generate warnings because their result cannot be certified from the
trace. `require_terminal=False` explicitly allows partial traces. Findings and
results have JSON-compatible `to_dict()` methods.

This contract audits PR04 allocation semantics, not arbitrary future dynamics:
resource balances must remain unchanged because PR04 records no consumption or
replenishment events. Resource sufficiency is checked when assigning tasks.
Robot exclusivity uses single-task, disjoint coalitions; overlapping allocation
is later roadmap work. The auditor does not certify a custom productivity
function or prove that a trace describes a physical execution. Hashes detect
inconsistency, not authenticity. It accepts PR04 schema 1.0 and introduces no
new trace schema or dependencies.

## Exact static allocation contract

The oracle maximizes the sum of rewards of selected tasks, assigning each task
at most one nonempty feasible coalition and each robot to at most one task.
Robots and tasks may remain unused. Feasibility checks additive capabilities,
resources, coalition size, and robot incompatibilities. It returns all optimal
partitions in lexicographic task/member order, including zero-reward ties, plus
the number of recursive search states visited. Reward comparison uses exact
fractions of the supplied binary floats; the reported reward is a float.

This is a simultaneous allocation optimum, not a sequential kernel-run optimum:
it does not reuse robots after completion. Workload does not affect the static
objective. Dependencies, release times, time windows, task locations, horizons,
and concurrent-task robots are rejected rather than silently treated as static.

Safety limits are 10 robots, 8 tasks, and 100,000 recursive visits by default.
`max_states` can explicitly change the visit budget. Dimension limits apply
before candidate enumeration; exceeding either limit raises `OracleLimitError`
and returns no partial result. Enumeration is exponential; these limits make
the API an oracle for tiny fixtures, not a production optimization backend.

## Acceptance evidence

- `test_exact_tiny_and_ties`: reward 60 and the unique tiny full partition;
  both reward-10 tied-optimum partitions.
- `test_generated_static_oracle_matches_robot_label_enumeration`: 30 seeded
  property cases checked against a separately implemented robot-label search.
- Corrupted-trace tests isolate the six required invariants and check exact
  findings rather than relying on kernel rejection. JSONL and in-memory audits
  agree on both valid and corrupt inputs.
- Empty/negative/zero-reward tests and dimension/search-budget refusal tests
  cover oracle boundaries.

Baseline policies, CLI/batch execution, and rendering remain subsequent items.
