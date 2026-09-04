"""Stable named random streams derived from reproducible root seeds."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

STREAM_NAMES: tuple[str, ...] = (
    "scenario",
    "dynamics",
    "observation",
    "communication",
    "policy",
)
_MAX_SEED = 2**128 - 1


def _validate_seed(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be a nonnegative integer")
    if not 0 <= value <= _MAX_SEED:
        raise ValueError(f"{field_name} must be between 0 and {_MAX_SEED}")
    return value


@dataclass(frozen=True, slots=True)
class RandomStreams:
    """Lazily-created, stateful NumPy generators with independent names.

    Each stream seed is a SHA-256-derived value from its base seed and name.
    The policy stream can use a separate seed; all other streams use the root
    seed. Adding a new stream therefore cannot consume values from an existing
    stream.
    """

    root_seed: int
    policy_seed: int | None = None
    _generators: dict[str, np.random.Generator] = field(
        init=False, default_factory=dict, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "root_seed", _validate_seed(self.root_seed, "root_seed")
        )
        if self.policy_seed is None:
            object.__setattr__(self, "policy_seed", self.root_seed)
        else:
            object.__setattr__(
                self, "policy_seed", _validate_seed(self.policy_seed, "policy_seed")
            )

    def seed_for(self, name: str) -> int:
        """Return the stable seed assigned to one known stream name."""

        if name not in STREAM_NAMES:
            available = ", ".join(STREAM_NAMES)
            raise KeyError(f"unknown random stream {name!r}; available: {available}")
        base_seed = self.policy_seed if name == "policy" else self.root_seed
        material = f"coalition-formation|{base_seed}|{name}".encode()
        return int.from_bytes(hashlib.sha256(material).digest()[:16], "little")

    def generator(self, name: str) -> np.random.Generator:
        """Return the persistent generator for a known named stream."""

        if name not in self._generators:
            self._generators[name] = np.random.default_rng(self.seed_for(name))
        return self._generators[name]

    def seed_manifest(self) -> dict[str, int]:
        """Return all derived stream seeds in stable declaration order."""

        return {name: self.seed_for(name) for name in STREAM_NAMES}
