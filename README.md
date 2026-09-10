# Multi-Robot Coalition Formation Toolkit

This repository is the beginning of a Python simulation and benchmarking toolkit for multi-robot coalition formation.

The first artifact is a literature-grounded study of the problem taxonomy, canonical scenarios, benchmark instances, simulator boundaries, and visualization requirements:

- [Canonical scenarios and simulator implications](docs/research/canonical_scenarios.md)
- [Agent-ready pull request roadmap](docs/implementation/PR_ROADMAP.md)
- [Domain model and plugin protocols](docs/implementation/domain_model.md)
- [Configuration, random streams, and static scenarios](docs/implementation/configuration_and_scenarios.md)
- [Deterministic kernel and event trace](docs/implementation/kernel_and_trace.md)

The allocation-only deterministic kernel and replayable event trace are now
implemented as the first simulation layer. Spatial travel, optimization,
rendering, and learning adapters remain later roadmap items.

- 2026-09-03: Did XYZ

## Developer setup

The project targets Python 3.11 and newer. Create an isolated environment and
install the package with its development tools:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

The domain models and protocols remain behavior-free and standard-library
only. NumPy and PyYAML are runtime dependencies for the named random-stream
and configuration APIs. Future visualization, graph, optimization, and
reinforcement learning dependencies are kept in the optional `viz`, `graph`,
`opt`, and `rl` extras; they are not imported by the core package.

Run the repository quality gate with:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src
```
