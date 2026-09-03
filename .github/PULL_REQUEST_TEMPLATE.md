## Roadmap item

- PR roadmap item: `PR XX`
- Closes: #
- Depends on:

## Outcome

Describe the user-visible and API-visible result. Lead with what now works.

## Scope

- [ ] All deliverables for this roadmap item are included.
- [ ] Later roadmap items were not implemented opportunistically.
- [ ] Unrelated worktree changes were preserved.

## Validation

List exact commands and results.

```text
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src
```

For scenario or rendering changes, also link or attach the smallest representative artifact and report its seed/configuration.

## Acceptance evidence

Map each acceptance criterion from `docs/implementation/PR_ROADMAP.md` to a test, artifact, or documented manual check.

| Criterion | Evidence |
|---|---|
| | |

## Reproducibility and compatibility

- [ ] New randomness uses a named stream derived from the root seed.
- [ ] Events/configuration remain JSON-serializable.
- [ ] Trace schema changes are versioned or explicitly ruled out.
- [ ] Optional dependencies do not leak into core imports.
- [ ] Existing scenario/policy outputs are unchanged, or intentional changes are documented.

## Risks and follow-ups

Record remaining risks, known limitations, performance impact, and deliberately deferred work.
