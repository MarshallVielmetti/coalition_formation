# Configuration, random streams, and static scenarios

PR 03 adds the first executable layer above the domain models. It remains
independent of the CLI and simulation kernel.

## Versioned configuration

Configuration files are JSON or YAML mappings with a required
`schema_version`. The current version is `1.0`; unknown versions fail rather
than being guessed. The required `scenario` selects a registered factory.
`seed` defaults to `0`, `policy_seed` defaults to `seed`, and `parameters`
defaults to an empty mapping. `ResolvedConfig.to_dict()`, `to_json()`, and
`to_yaml()` include all defaults explicitly, making them suitable for run
manifests and reproducibility checks.

```yaml
schema_version: "1.0"
scenario: static_capability/tiny
seed: 7
policy_seed: 11
parameters: {}
```

Use `load_config(path)` for file loading and
`export_resolved_config(config, destination)` to write a resolved JSON or YAML
copy. Configuration parameters are checked for JSON compatibility before they
are stored.

## Named random streams

`RandomStreams` exposes `scenario`, `dynamics`, `observation`,
`communication`, and `policy`. Each stream is a separately seeded
`numpy.random.Generator`. The seed is derived from a stable SHA-256 hash of
the base seed and stream name, so creating or consuming one stream cannot
advance another. The `policy` stream uses `policy_seed`; all other streams use
`root_seed`. `seed_manifest()` returns every derived seed in declaration
order.

Consequently, changing only `policy_seed` leaves generated robots and tasks
unchanged while changing the policy stream. Scenario factories must consume
scenario randomness only from the `scenario` stream.

## Explicit registry and static capability presets

`default_registry()` registers factories explicitly and in this stable order:

1. `static_capability/tiny`
2. `static_capability/small`
3. `static_capability/random`
4. `static_capability/scarcity`
5. `static_capability/redundancy`
6. `static_capability/incompatibility`
7. `static_capability/tied_optimum`

Use `list_scenarios()` and `construct_scenario(config)` from Python. The
registry does not scan imports or discover plugins implicitly. Duplicate names
are rejected with an actionable error.

The tiny fixture has six robots and three tasks. Its unique full feasible
partition is `(r1, r2) -> t1`, `(r3, r4) -> t2`, and `(r5, r6) -> t3`; each
task requires the corresponding pair's skill total and has coalition size
exactly two. The small fixture has 12 robots, five skills, and eight tasks.
The seeded random fixture accepts integer `robot_count`, `task_count`, and
`skill_count` parameters. The remaining registered fixtures exercise scarce
skills, redundant alternatives, explicit robot incompatibility, and tied
alternatives for later exact-solver tests.

This PR adds scenario specifications only. It does not add a simulation loop,
allocation policy, event trace, or optimizer.
