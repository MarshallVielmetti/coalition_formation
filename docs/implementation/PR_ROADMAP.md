# Agent-Ready Pull Request Roadmap

Status: proposed implementation sequence  
Source: [canonical scenario research](../research/canonical_scenarios.md)

This document converts the research milestones into implementation-sized pull requests. Each PR is intended to be executable by a coding agent without inventing architecture or silently expanding scope. The sequence is deliberately incremental: every merged PR must leave `main` tested, documented, and usable by the next PR.

## Global implementation contract

These rules apply to every PR in the roadmap.

- Target Python 3.11 or newer and use a `src/` package layout.
- The import package is `coalition_formation`; the distribution name is `coalition-formation`.
- Keep the domain kernel independent of visualization, CLI, optimization, RL, and web frameworks.
- Policies receive immutable observations and return typed actions or proposals. Only the kernel mutates simulation state.
- Use integer simulation ticks in the first release. Coordinates, workloads, capabilities, and costs may be floating point.
- All stochastic behavior must come from named, reproducible NumPy generators derived from one root seed.
- Events and resolved configurations must be JSON-serializable without custom object pickling.
- Renderers and metrics consume traces; they must never advance or mutate a simulation.
- Preserve domain metrics separately instead of reducing every experiment to one scalar score.
- Optional dependency families belong in extras: `viz`, `graph`, `opt`, `rl`, and `dev`.
- New public behavior requires tests and documentation in the same PR.
- Avoid committing generated run artifacts, caches, videos, or benchmark outputs except intentionally small test fixtures.
- Do not implement features assigned to a later PR merely because a future interface is visible.

## Required checks for every PR

Unless the PR explicitly introduces the check itself, the coding agent must run:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src
```

The PR description must report the exact commands run and their outcomes. If an optional extra is introduced, add at least one CI/test job that installs and exercises it.

## Dependency map

| PR | Milestone | Short title | Depends on |
|---:|---|---|---|
| 01 | Foundation | Package and quality scaffold | — |
| 02 | M1 | Domain model and plugin protocols | 01 |
| 03 | M1 | Configuration, RNG, registry, and static scenario | 02 |
| 04 | M1 | Deterministic kernel and event trace | 03 |
| 05 | M1 | Independent auditor and exact oracle | 04 |
| 06 | M1 | Random, greedy, and exhaustive policies | 05 |
| 07 | M1 | CLI, artifact layout, and batch runner | 06 |
| 08 | M1 | Static figures, timelines, and GIF renderer | 07 |
| 09 | M2 | Graph and continuous 2-D travel backends | 08 |
| 10 | M2 | Rendezvous and cooperative transport | 09 |
| 11 | M2 | CFSTP scenario family and paper preset | 09 |
| 12 | M2 | MILP, EDF, and look-ahead baselines | 11 |
| 13 | M2 | Multi-policy experiment analysis | 10, 12 |
| 14 | M3 | Observation, communication, and failures | 13 |
| 15 | M3 | RoboCup Rescue-lite | 14 |
| 16 | M3 | Dynamic incident streams and scaling | 14 |
| 17 | M3 | Decentralized policy and PettingZoo adapter | 15, 16 |
| 18 | M4 | Overlapping coalitions and surveillance | 17 |
| 19 | M4 | Gymnasium adapter and offline datasets | 18 |
| 20 | Release | Performance, documentation, and v0.1 hardening | 19 |

PRs 10 and 11 may be developed in parallel after PR 09. PRs 15 and 16 may be developed in parallel after PR 14. All other dependencies are sequential.

## PR 01 — Package and quality scaffold

### Objective

Create an installable but behavior-free Python project with repeatable local and CI quality gates.

### Deliverables

- Add `pyproject.toml` using a standards-based build backend and declare Python `>=3.11`.
- Add `src/coalition_formation/__init__.py` with a package version and no side effects.
- Add `tests/` with an import/version smoke test.
- Add `.gitignore`, `LICENSE`, `CONTRIBUTING.md`, and a minimal developer setup section in the README.
- Configure Ruff, mypy, pytest, and coverage in `pyproject.toml`.
- Add a GitHub Actions workflow for Python 3.11 and 3.12 that installs `.[dev]` and runs the required checks.
- Declare future extras as empty or minimally populated groups without importing them from the core package.

### Implementation steps

1. Choose and document one build backend; do not add a second environment manager requirement.
2. Make `pip install -e '.[dev]'` the portable setup path.
3. Keep runtime dependencies minimal: NumPy and Pydantic may be declared now; visualization/RL/solver packages must remain optional.
4. Ensure package metadata, repository URLs, and license classifiers match the repository.

### Tests and acceptance

- A clean virtual environment can install the project and import `coalition_formation`.
- CI runs lint, format check, typing, and tests on both supported Python versions.
- `python -m pytest` collects at least one real test.
- No simulator model or scenario behavior is introduced.

## PR 02 — Domain model and plugin protocols

### Objective

Define stable, typed vocabulary for robots, tasks, coalitions, actions, observations, and extension points without implementing the simulator loop.

### Deliverables

- Add immutable specification models: `RobotSpec`, `TaskSpec`, `TimeWindow`, `Dependency`, and `ScenarioSpec`.
- Add runtime value objects: `RobotState`, `TaskState`, `Coalition`, `WorldState`, `Observation`, and typed action variants.
- Represent capabilities and requirements as validated nonnegative mappings from string keys to floats.
- Add enums for task, robot, coalition, and terminal statuses with explicit serialized values.
- Add `typing.Protocol` contracts for coalition feasibility/value, travel, task dynamics, observation, communication, allocation policy, metrics, and termination.
- Document identity rules, units, default values, and equality/serialization semantics.

### Suggested modules

```text
src/coalition_formation/core/models.py
src/coalition_formation/core/actions.py
src/coalition_formation/core/protocols.py
src/coalition_formation/core/types.py
tests/core/
```

### Tests and acceptance

- Reject duplicate IDs, negative capability/resource values, invalid windows, impossible coalition bounds, and unknown dependency endpoints.
- Round-trip every public model through JSON-compatible data.
- Demonstrate at least one third-party test double implementing each protocol without subclassing a concrete framework class.
- Runtime state cannot be mutated by a policy through an `Observation` reference.
- No global registry, event loop, or scenario-specific conditional appears in core models.

## PR 03 — Configuration, deterministic RNG, registry, and static scenario

### Objective

Load versioned scenario configurations, derive stable named random streams, and instantiate the first canonical static capability-matching scenario.

### Deliverables

- Add YAML/JSON loading with a required schema version and resolved-default export.
- Add a scenario registry whose entries are explicit factories rather than import-time discovery magic.
- Add named random streams such as `scenario`, `dynamics`, `observation`, `communication`, and `policy`.
- Derive each named stream from the root seed and a stable name hash so adding a new stream does not perturb existing streams.
- Implement `static_capability/tiny`, `small`, and seeded random presets.
- Add a hand-authored tiny fixture with a unique known optimal partition.
- Add CLI-independent APIs for listing and constructing registered scenarios.

### Tests and acceptance

- Same resolved config and seed produce byte-identical scenario JSON.
- Changing only the policy seed does not change generated robots or tasks.
- Registry order is stable and duplicate names fail clearly.
- Tiny, scarcity, redundancy, incompatibility, and tied-optimum fixtures cover edge cases.
- Unknown schema versions fail with an actionable error rather than being guessed.

## PR 04 — Deterministic kernel and append-only event trace

### Objective

Implement the authoritative state-transition system for allocation-only simulations.

### Deliverables

- Add `SimulationKernel.reset()`, `observe()`, `step()`, and `run()` APIs.
- Define versioned event records for reset, task release, proposal, assignment, coalition formation/disbanding, work, completion/failure, policy error, and simulation termination.
- Specify deterministic ordering by `(tick, event_priority, insertion_sequence)` and stable robot/task IDs.
- Validate actions before applying transitions; invalid actions must be traceable and must not partially mutate state.
- Record pre/post state hashes or sufficient replay data for independent reconstruction.
- Add JSON Lines trace read/write support.
- Implement horizon, terminal-state, and no-op behavior.

### Tests and acceptance

- Repeated runs produce identical traces and final-state hashes.
- Replaying a saved trace reconstructs the same state without invoking the original policy.
- Invalid double booking, unknown IDs, early task execution, and post-terminal actions are rejected atomically.
- Event ordering is tested when multiple events share one tick.
- The kernel has no Matplotlib, Typer, solver, PettingZoo, or scenario-specific imports.

## PR 05 — Independent feasibility auditor and exact oracle

### Objective

Create verification that does not trust the policy or kernel's reported summary and establish exact answers for tiny static problems.

### Deliverables

- Add a trace auditor that reconstructs assignments and checks robot exclusivity, capability sufficiency, coalition bounds, task status transitions, resource conservation, and terminal consistency.
- Return structured findings with severity, tick, entity IDs, invariant name, and evidence.
- Add exhaustive enumeration for tiny static capability instances.
- Report optimal reward, all optimal partitions, explored state count, and deterministic tie ordering.
- Add deliberately corrupted trace fixtures proving each invariant fires.
- Add property-based tests over small randomly generated feasible/infeasible cases.

### Tests and acceptance

- Auditor results are identical whether run in-process or against serialized JSONL.
- Every intentionally corrupted fixture produces the expected finding and no unrelated critical findings.
- Exhaustive results match hand-calculated tiny fixtures, including tied optima.
- The oracle refuses instances above a documented safety threshold instead of hanging.
- The auditor shares data types but not transition functions with the kernel.

## PR 06 — Random, greedy, and exhaustive baseline policies

### Objective

Provide deterministic reference policies behind the common `AllocationPolicy` contract.

### Deliverables

- Implement seeded random-feasible assignment.
- Implement greedy maximum marginal utility with deterministic tie breaking.
- Wrap the exact enumerator as an offline policy for supported tiny static cases.
- Expose policy metadata, configuration validation, and per-decision timing.
- Add a policy registry parallel to the scenario registry.
- Document whether each policy is online/offline, centralized/distributed, and which scenario features it supports.

### Tests and acceptance

- Policies never mutate observations.
- Random policy is repeatable for a fixed policy stream.
- Greedy choices match hand-worked examples and deterministic ties.
- Exact policy attains the auditor's optimum on every tiny fixture.
- Unsupported features fail before the run starts with a compatibility report.

## PR 07 — CLI, artifact layout, and seeded batch runner

### Objective

Make the M1 simulator reproducibly operable from the command line and Python.

### Deliverables

- Add `coalition-formation list`, `validate`, `run`, `batch`, `audit`, and `show-config` commands.
- Define run directories containing resolved config, seed manifest, environment/policy metadata, trace JSONL, metrics JSON, and a human-readable summary.
- Use a deterministic configuration hash in run identity; keep timestamps separate from deterministic content.
- Add batch expansion over explicit seeds and policy/scenario parameter grids.
- Prevent accidental overwrite unless an explicit flag is given.
- Return meaningful exit codes for validation, policy, simulation, and audit failures.

### Tests and acceptance

- CLI tests run through the installed console entry point.
- Single and batch invocations reproduce equivalent Python API results.
- Interrupted/failed runs are marked incomplete and are not mistaken for successful artifacts.
- Batch output has one manifest indexing all child runs.
- Help text contains runnable examples and no undocumented required environment variables.

## PR 08 — Static figures, timelines, and GIF renderer

### Objective

Produce high-quality, headless visual artifacts from traces without coupling rendering to the kernel.

### Deliverables

- Add a spatial renderer with persistent robot identity, coalition encodings, task state, and capability annotations.
- Add robot-by-time Gantt, coalition-membership timeline, capability supply/demand, and metrics-summary figures.
- Add GIF rendering through Matplotlib/Pillow and optional MP4 through FFmpeg when available.
- Support PNG plus SVG or PDF for static publication artifacts.
- Define a colorblind-safe theme, deterministic legend ordering, fixed animation axes, and non-color coalition markers.
- Add `render` CLI commands operating on existing run directories.

### Tests and acceptance

- Rendering never changes trace/state hashes.
- Headless CI renders deterministic smoke artifacts and checks dimensions, frame count, and nonempty content.
- Missing FFmpeg degrades to a clear optional-capability message; GIF remains functional.
- Visual regression checks use tolerant image metrics or structural artist assertions, not brittle byte equality.
- At least one checked-in tiny reference image demonstrates the intended quality bar.

## PR 09 — Graph and continuous 2-D travel backends

### Objective

Add replaceable spatial travel models while preserving allocation-only behavior.

### Deliverables

- Implement Euclidean, Manhattan, and NetworkX shortest-path travel models.
- Add a simple continuous 2-D point-robot executor with speed limits and deterministic integration.
- Add obstacle/region support behind an optional Shapely extra.
- Define unreachable-route and route-invalidated events.
- Cache deterministic shortest-path queries without leaking cache state into results.
- Add analytical-versus-kinematic consistency tests when obstacles and collisions are disabled.

### Tests and acceptance

- Known graph and grid distances match analytical values.
- Triangle and zero-distance edge cases are explicit.
- Unreachable tasks are reported as infeasible, not assigned with infinite/NaN cost.
- Point robots arrive within a documented tolerance and never exceed configured speed.
- Existing static-scenario traces remain unchanged when no spatial model is selected.

## PR 10 — Rendezvous and cooperative transport scenarios

### Objective

Implement the canonical tightly coupled spatial scenario family derived from cooperative transportation and box pushing.

### Deliverables

- Add `rendezvous`, `single_box`, `blocked_boxes`, and `multi_object` presets.
- Model synchronized coalition readiness using an explicit arrival tolerance.
- Model object requirements by mass/geometry and robot push/grasp/localization capabilities.
- Add transport progress, object pose, coalition disengagement, and task failure events.
- Encode blocked-box precedence as scenario data, not special-case kernel logic.
- Extend spatial and Gantt renderers with object paths, wait-for-team intervals, and dependency status.

### Tests and acceptance

- Work cannot start until the complete required coalition is present.
- Removing a required capability or coalition member makes the affected task infeasible or stalled according to configuration.
- The blocked-box fixture enforces precedence and completes under a known feasible policy.
- Analytical and 2-D execution agree on task order and completion feasibility in the deterministic fixture.
- No contact physics engine is introduced in this PR.

## PR 11 — CFSTP scenario family and paper preset

### Objective

Implement coalition routing/scheduling with spatial tasks, workloads, deadlines, and coalition productivity.

### Deliverables

- Add `cfstp_tiny`, `cfstp_paper`, `cfstp_heterogeneous`, and `cfstp_open` presets.
- Implement additive, subadditive, superadditive, and task-specific coalition productivity functions.
- Implement workload accumulation, deadlines, late failure, repeated coalition formation, and travel/service state transitions.
- Reproduce the documented 50×50 Manhattan-grid generator with 300 tasks, 2–20 agents, `U(5,600)` deadlines, `U(10,50)` workloads, and the paper-style productivity preset.
- Record source citation and any interpretation needed where the paper underspecifies generation details.
- Add small fixtures with independently known optimal schedules.

### Tests and acceptance

- Work accumulation matches closed-form examples for each productivity class.
- Deadline boundary semantics are explicit and tested.
- Agents may disband and reform without double booking or lost travel state.
- The paper preset is seeded and its sampled ranges/statistics are validated.
- `cfstp_open` hides unreleased tasks from observations and from online policies.

## PR 12 — MILP, EDF, and look-ahead scheduling baselines

### Objective

Provide optimization and canonical heuristic baselines for CFSTP.

### Deliverables

- Implement earliest-deadline-first with a pluggable coalition constructor.
- Implement a one-step coalition look-ahead heuristic with an anytime incumbent trace.
- Add an open-source MILP baseline using the optional `opt` extra and no proprietary solver requirement.
- Keep model construction separate from simulation execution and independently audit returned schedules.
- Report solver status, bound, gap, runtime, incumbent history, and termination reason.
- Add compatibility guards and size/time limits.

### Tests and acceptance

- MILP agrees with exhaustive or hand-solved tiny CFSTP cases.
- EDF and look-ahead produce feasible audited traces on all supported presets.
- Timeout returns the best valid incumbent rather than fabricating optimal status.
- Solver unavailability only skips optional tests and gives a clear installation message.
- Benchmark tests avoid asserting the original paper's performance percentages as universal facts.

## PR 13 — Multi-policy experiment analysis

### Objective

Compare policies and seeds using trace-derived statistics and publication-quality summaries.

### Deliverables

- Add a normalized run index and tabular exporter to CSV/Parquet.
- Aggregate task success/reward, deadline misses, makespan, travel, waiting, coalition churn, compute time, and audit status.
- Add paired comparisons by scenario seed and uncertainty intervals across seeds.
- Plot spatial outcomes, distributions, empirical performance profiles, and anytime curves.
- Add a reproducible experiment manifest for the M1/M2 scenarios and baselines.
- Generate one example HTML or Markdown report linking raw run artifacts.

### Tests and acceptance

- Aggregation rejects mixed schema versions or marks them explicitly.
- Paired statistics align runs by scenario identity rather than row order.
- Failed/incomplete runs remain visible and are never silently dropped.
- Metrics are recomputed from traces or auditor output, not trusted from policy logs.
- Example report generation succeeds headlessly from small fixtures.

## PR 14 — Observation, communication, and failure models

### Objective

Introduce controlled partial observability, message transport, stochastic execution, and robot failures as orthogonal plugins.

### Deliverables

- Add global, radius-limited, noisy, delayed, and stale observation models.
- Add communication topology/range, bandwidth, delay, loss, queueing, and message accounting.
- Add robot failure, recovery, task cancellation, and route/service-time noise events.
- Separate ground-truth trace fields from policy-visible observations.
- Derive each stochastic mechanism from its own named RNG stream.
- Add failure injection schedules and seeded stochastic presets.

### Tests and acceptance

- A policy cannot recover hidden ground truth through object references or metadata.
- Message delay/loss and bandwidth accounting match hand-calculated fixtures.
- Adding observation noise does not perturb scenario generation or policy RNG streams.
- Failure during travel, wait, and work has explicit tested semantics.
- Zero-noise/global-observation configurations reproduce deterministic M2 outcomes.

## PR 15 — RoboCup Rescue-lite

### Objective

Implement an explicit abstraction of heterogeneous disaster response focused on coalition-relevant mechanisms.

### Deliverables

- Add fire-brigade, police, and ambulance robot profiles.
- Add fire, blocked-road, buried-victim, excavation, transport, and refuge task types.
- Encode `clear road -> reach victim`, `excavate -> transport`, spreading fire, civilian health, and task priority interactions.
- Add deterministic, parallel-incident, communication-dropout, and robot-failure presets.
- Add domain metrics: civilians rescued/lost, fires contained/burned out, roads cleared, response time, and coalition repair time.
- Add a dependency graph and disaster-state visualization.

### Tests and acceptance

- Blocked paths prevent dependent rescue actions until cleared.
- Multiple ambulances contribute according to configured excavation productivity.
- Health/fire dynamics advance independently of policy computation.
- Partial observability and communication variants expose only allowed information.
- Documentation labels this as `RoboCup Rescue-lite`, not a compliant reproduction of the full simulator.

## PR 16 — Dynamic incident streams and scaling

### Objective

Support open-world arrivals, nonstationary travel/service, external incident records, and large-scale performance measurement.

### Deliverables

- Add seeded Poisson and scheduled arrival generators with spatial intensity controls.
- Add rush-hour/time-varying travel and stochastic service models.
- Add task cancellation, priority escalation, and rolling-horizon execution.
- Add an adapter interface for the London Fire Brigade-derived dataset without vendoring data.
- Validate dataset license/download instructions before enabling automated retrieval; retrieval must be opt-in.
- Add scale presets up to 150 agents and 3,000 active tasks plus profiling scripts.
- Track memory, wall time, decision latency, queue depth, and event throughput.

### Tests and acceptance

- Online policies cannot see future arrivals.
- Arrival processes pass seeded count/time/location fixture checks.
- Dataset absence produces a clear skipped/installation path, not a hidden synthetic substitute.
- Scale smoke tests have bounded CI sizes; large benchmarks are explicitly opt-in.
- Profiling output distinguishes policy time, kernel time, audit time, and rendering time.

## PR 17 — Decentralized policy interface and PettingZoo adapter

### Objective

Support independent per-robot decision makers and expose simultaneous multi-agent interaction through PettingZoo.

### Deliverables

- Add decentralized policy lifecycle, local observation, message send/receive, and coalition negotiation actions.
- Define conflict resolution when simultaneous proposals compete for robots/tasks.
- Implement a deterministic reference auction/negotiation policy with message accounting.
- Add a PettingZoo `ParallelEnv` adapter with heterogeneous observation/action spaces where required.
- Run PettingZoo's official parallel API compliance test.
- Map termination versus truncation, agent failure/removal, rewards, and info fields explicitly.

### Tests and acceptance

- Centralized scenarios continue to run without PettingZoo installed.
- Simultaneous action resolution is order-independent or follows a documented deterministic order.
- Communication budgets constrain the reference decentralized policy.
- The adapter passes official API tests and seed reproducibility tests.
- Reward adapters do not replace trace-derived scientific metrics.

## PR 18 — Overlapping coalitions and scheduled surveillance

### Objective

Extend the model from single-task robots/disjoint coalitions to explicit concurrent capacity and overlapping sensor coalitions.

### Deliverables

- Add per-robot concurrent capacity/resource reservation semantics.
- Allow a robot to participate in multiple coalitions only when its declared capacity permits it.
- Add `multisensor_events`, `stereo_track`, `periodic_patrol`, and `connectivity_aware` surveillance presets.
- Add synchronization windows, complementary sensors, viewpoint separation, repeated tasks, and connectivity constraints.
- Extend auditor, policies, timelines, and metrics for overlapping membership.
- Add utilization and sensing-coverage metrics.

### Tests and acceptance

- Capacity and resource reservations prevent oversubscription.
- Stereo tasks require synchronized distinct viewpoints.
- Periodic checks generate/release deterministically and record missed windows.
- Connectivity constraints react correctly to topology changes.
- Existing ST scenarios retain identical semantics and results.

## PR 19 — Gymnasium adapter and offline dataset export

### Objective

Make centralized/learned policies interoperable with Gymnasium and support reproducible offline learning datasets.

### Deliverables

- Add a Gymnasium environment for a centralized controller with documented observation/action encodings.
- Add action masks or explicit invalid-action handling without silently correcting learned actions.
- Add transition export containing observation, action, reward adapter, next observation, termination, truncation, info, seed, and trace reference.
- Add dataset manifests, schema versioning, shard hashes, and deterministic train/validation/test split logic.
- Provide random-policy examples for Gymnasium and PettingZoo; do not claim learning performance.
- Add optional RL dependency tests and environment checkers.

### Tests and acceptance

- Gymnasium's environment checker passes.
- Exported transitions can be replayed back to their source trace.
- Dataset splits are stable and prevent scenario-seed leakage across partitions.
- Large datasets are generated artifacts and remain gitignored.
- Scientific metrics remain independent from any shaped learning reward.

## PR 20 — Performance, documentation, and v0.1 hardening

### Objective

Turn the completed vertical stack into a documented, benchmarked, reproducible v0.1 release candidate.

### Deliverables

- Profile kernel, policies, audit, serialization, and renderers; optimize only measured bottlenecks.
- Add end-to-end tutorials for static capability, cooperative transport, CFSTP, Rescue-lite, and surveillance.
- Add API documentation for plugin authors and one external example plugin.
- Add a benchmark matrix documenting supported features for every scenario/policy combination.
- Add artifact/schema migration policy, changelog, citation metadata, release checklist, and security/reporting guidance.
- Add deterministic example outputs and a command that regenerates them.
- Audit dependencies, licenses, optional extras, and public API exports.

### Tests and acceptance

- A clean checkout can reproduce every quickstart and checked-in small reference result.
- All earlier acceptance suites pass together under core and all-extras CI jobs.
- Performance claims include hardware/configuration and measured evidence.
- Public APIs intended for v0.1 are explicitly exported and documented; internal modules remain internal.
- Release artifacts contain source and metadata but not generated experiment corpora.

## Coding-agent handoff template

Use this prompt when assigning any roadmap item:

> Implement PR XX from `docs/implementation/PR_ROADMAP.md`. Read the global implementation contract and the canonical scenario research first. Complete only that PR and its direct acceptance criteria; do not implement later roadmap items. Preserve unrelated user changes. Before editing, inspect the current repository and adapt paths only where merged earlier PRs require it. Add or update tests and documentation in the same change. Run the repository's required checks and report exact results, remaining risks, and any deliberate deviations from the roadmap.

## Pull request completion rule

A roadmap ticket is complete only when implementation, tests, user-facing documentation, and acceptance evidence are in the same PR. Passing unit tests alone is not sufficient if the PR promises CLI behavior, artifacts, visual output, compatibility checks, or independent audit behavior.
