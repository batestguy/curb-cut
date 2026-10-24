"""Map state names as printed in a source to the repo's canonical states.

Uses the same two seeds as the warehouse (``packages/transform/seeds``): ``dim_states``
(36 states + FCT, ISO 3166-2 codes, zones) and ``state_name_aliases``. Matching uses the
same key as the dbt macro ``normalise_state_key``: letters only, single-spaced, lower case,
so "1. Abia", "ABIA" and "Abia " all match, and "FCT ABUJA" matches through its alias.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

SEEDS = Path(__file__).resolve().parents[3] / "transform" / "seeds"

_NON_LETTERS = re.compile(r"[^A-Za-z]+")


def state_key(name: str) -> str:
    """Python twin of the dbt macro ``normalise_state_key``."""
    return _NON_LETTERS.sub(" ", name).strip().lower()


@dataclass(frozen=True)
class State:
    state: str
    state_code: str
    zone: str


class UnknownStateError(ValueError):
    """A source label did not match any state or alias."""


class StateLookup:
    def __init__(self, states: Iterable[State], aliases: Mapping[str, str]) -> None:
        by_name = {s.state: s for s in states}
        self.states = by_name
        self._keys: dict[str, State] = {state_key(name): s for name, s in by_name.items()}
        for alias, canonical in aliases.items():
            self._keys[state_key(alias)] = by_name[canonical]

    @classmethod
    def from_seeds(cls, seeds: Path = SEEDS) -> StateLookup:
        with (seeds / "dim_states.csv").open(encoding="utf-8", newline="") as f:
            states = [State(r["state"], r["state_code"], r["zone"]) for r in csv.DictReader(f)]
        with (seeds / "state_name_aliases.csv").open(encoding="utf-8", newline="") as f:
            aliases = {r["alias"]: r["state"] for r in csv.DictReader(f)}
        return cls(states, aliases)

    def resolve(self, label: str) -> State:
        try:
            return self._keys[state_key(label)]
        except KeyError:
            raise UnknownStateError(f"no state or alias matches {label!r}") from None

    def map_codes(self, value_labels: Mapping[int, str]) -> dict[int, State]:
        """Map a Stata value-label set (code -> printed name) to states.

        Raises if any label is unknown or if the set does not cover all 37 states once.
        """
        mapped = {int(code): self.resolve(label) for code, label in value_labels.items()}
        covered = {s.state for s in mapped.values()}
        if len(mapped) != len(self.states) or covered != set(self.states):
            missing = sorted(set(self.states) - covered)
            raise UnknownStateError(f"value labels do not map one-to-one; missing {missing}")
        return mapped
