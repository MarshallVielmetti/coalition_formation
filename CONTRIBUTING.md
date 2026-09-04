# Contributing

## Development setup

The project targets Python 3.11 and newer. Create an isolated environment and
install the package with its development tools:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

The domain models and protocols use only the Python standard library. NumPy
and PyYAML are package runtime dependencies for deterministic random streams
and YAML configuration loading. The `viz`, `graph`, `opt`, and `rl` extras are
reserved for later roadmap items; they must remain optional and must not be
imported by the core package.

This PR introduces no simulator behavior, scenario configuration, random
stream, event, or trace schema. Later implementation PRs must document and
version those reproducibility-facing interfaces when they are introduced.

## Quality checks

Run the complete local gate before opening a pull request:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src
```

The same commands run in GitHub Actions on Python 3.11 and 3.12. Keep tests,
documentation, and reproducibility notes in the same pull request as new
public behavior.

## Scope and generated files

The implementation roadmap in `docs/implementation/PR_ROADMAP.md` is
sequential. A pull request should complete only its assigned item and its
direct acceptance criteria. Do not commit generated run artifacts, caches,
videos, or benchmark outputs unless they are intentionally small test
fixtures.
