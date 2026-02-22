from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SimulationRuleset:
    ruleset_id: str
    scheduled_innings: int
    max_innings: int
    max_plate_appearances_per_half: int
    skip_home_bottom_if_leading_after_top_final: bool
    enable_walkoff: bool
    enable_runner_on_second_in_extras: bool
    runner_on_second_start_inning: int
    home_field_event_boost: float


@dataclass(frozen=True)
class LoadedRuleset:
    ruleset: SimulationRuleset
    checksum_sha256: str
    source_path: str


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _require_bool(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Expected boolean for {key}")
    return value


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Expected integer for {key}")
    return value


def _require_float(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, int):
        return float(value)
    if not isinstance(value, float):
        raise ValueError(f"Expected number for {key}")
    return value


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or value == "":
        raise ValueError(f"Expected non-empty string for {key}")
    return value


def parse_ruleset(payload: dict[str, Any]) -> SimulationRuleset:
    ruleset = SimulationRuleset(
        ruleset_id=_require_str(payload, "ruleset_id"),
        scheduled_innings=_require_int(payload, "scheduled_innings"),
        max_innings=_require_int(payload, "max_innings"),
        max_plate_appearances_per_half=_require_int(payload, "max_plate_appearances_per_half"),
        skip_home_bottom_if_leading_after_top_final=_require_bool(
            payload,
            "skip_home_bottom_if_leading_after_top_final",
        ),
        enable_walkoff=_require_bool(payload, "enable_walkoff"),
        enable_runner_on_second_in_extras=_require_bool(
            payload, "enable_runner_on_second_in_extras"
        ),
        runner_on_second_start_inning=_require_int(payload, "runner_on_second_start_inning"),
        home_field_event_boost=_require_float(payload, "home_field_event_boost"),
    )
    _validate_ruleset(ruleset)
    return ruleset


def _validate_ruleset(ruleset: SimulationRuleset) -> None:
    if ruleset.scheduled_innings < 1:
        raise ValueError("scheduled_innings must be >= 1")
    if ruleset.max_innings < ruleset.scheduled_innings:
        raise ValueError("max_innings must be >= scheduled_innings")
    if ruleset.max_innings > 21:
        raise ValueError("max_innings must be <= 21 for current API contract")
    if ruleset.max_plate_appearances_per_half < 3:
        raise ValueError("max_plate_appearances_per_half must be >= 3")
    if ruleset.runner_on_second_start_inning < 1:
        raise ValueError("runner_on_second_start_inning must be >= 1")
    if not 0.0 <= ruleset.home_field_event_boost <= 0.1:
        raise ValueError("home_field_event_boost must be between 0.0 and 0.1")


@lru_cache(maxsize=8)
def load_ruleset_from_path(path: str) -> LoadedRuleset:
    ruleset_path = Path(path)
    if not ruleset_path.exists():
        raise FileNotFoundError(f"Ruleset not found: {ruleset_path}")
    payload = json.loads(ruleset_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Ruleset file must contain JSON object")

    ruleset = parse_ruleset(payload)
    checksum = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    return LoadedRuleset(
        ruleset=ruleset,
        checksum_sha256=checksum,
        source_path=ruleset_path.as_posix(),
    )


DEFAULT_RULESET = SimulationRuleset(
    ruleset_id="built_in_default",
    scheduled_innings=9,
    max_innings=21,
    max_plate_appearances_per_half=80,
    skip_home_bottom_if_leading_after_top_final=True,
    enable_walkoff=True,
    enable_runner_on_second_in_extras=False,
    runner_on_second_start_inning=10,
    home_field_event_boost=0.015,
)
