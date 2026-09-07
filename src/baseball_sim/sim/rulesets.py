from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EventRates:
    """How one plate-appearance outcome responds to the matchup.

    ``base`` is the league-average rate — what happens when two average clubs meet.
    ``sensitivity`` is how far the matchup moves it, and is the knob that decides how
    far apart good and bad clubs finish. ``minimum`` and ``maximum`` bound the result
    so an extreme profile cannot produce a rate baseball never sees.
    """

    base: float
    sensitivity: float
    minimum: float
    maximum: float
    home_boost: float = 0.0


@dataclass(frozen=True)
class EventModel:
    """Everything that turns two team profiles into plate-appearance probabilities.

    Lifted out of the state machine so it is versioned with the ruleset rather than
    compiled into the engine. A stored run keeps the model it was played with, so
    retuning the model cannot silently change what an old replay produces.
    """

    attack_offense: float
    attack_discipline: float
    attack_power: float
    attack_speed: float
    prevention_prevention: float
    prevention_command: float
    prevention_range: float
    out: EventRates
    walk: EventRates
    single: EventRates
    double: EventRates
    triple: EventRates
    home_run: EventRates


#: The model the engine has always used. Its values are documented starting points,
#: not fitted ones (ADR-004, ADR-020) — a fitted model belongs in its own ruleset.
DEFAULT_EVENT_MODEL = EventModel(
    attack_offense=0.45,
    attack_discipline=0.20,
    attack_power=0.25,
    attack_speed=0.10,
    prevention_prevention=0.55,
    prevention_command=0.25,
    prevention_range=0.20,
    out=EventRates(base=0.695, sensitivity=-0.12, minimum=0.54, maximum=0.78, home_boost=-0.6),
    walk=EventRates(base=0.078, sensitivity=0.03, minimum=0.045, maximum=0.14, home_boost=1.0),
    single=EventRates(base=0.142, sensitivity=0.05, minimum=0.09, maximum=0.22, home_boost=0.6),
    double=EventRates(base=0.045, sensitivity=0.018, minimum=0.02, maximum=0.08, home_boost=0.3),
    triple=EventRates(base=0.005, sensitivity=0.007, minimum=0.002, maximum=0.02),
    home_run=EventRates(base=0.035, sensitivity=0.028, minimum=0.015, maximum=0.09, home_boost=0.5),
)


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
    event_model: EventModel = DEFAULT_EVENT_MODEL


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
        event_model=_parse_event_model(payload.get("event_model")),
    )
    _validate_ruleset(ruleset)
    return ruleset


def _parse_event_model(payload: Any) -> EventModel:
    """Read an event model, or keep the built-in one.

    A ruleset file written before the model was versioned has no block, and must keep
    behaving exactly as it did — so an absent block is the default, not an error.
    """

    if payload is None:
        return DEFAULT_EVENT_MODEL
    if not isinstance(payload, dict):
        raise ValueError("event_model must be a JSON object")

    def rates(name: str) -> EventRates:
        block = payload.get(name)
        if not isinstance(block, dict):
            raise ValueError(f"event_model.{name} must be a JSON object")
        return EventRates(
            base=_require_float(block, "base"),
            sensitivity=_require_float(block, "sensitivity"),
            minimum=_require_float(block, "minimum"),
            maximum=_require_float(block, "maximum"),
            home_boost=float(block.get("home_boost", 0.0)),
        )

    return EventModel(
        attack_offense=_require_float(payload, "attack_offense"),
        attack_discipline=_require_float(payload, "attack_discipline"),
        attack_power=_require_float(payload, "attack_power"),
        attack_speed=_require_float(payload, "attack_speed"),
        prevention_prevention=_require_float(payload, "prevention_prevention"),
        prevention_command=_require_float(payload, "prevention_command"),
        prevention_range=_require_float(payload, "prevention_range"),
        out=rates("out"),
        walk=rates("walk"),
        single=rates("single"),
        double=rates("double"),
        triple=rates("triple"),
        home_run=rates("home_run"),
    )


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
    _validate_event_model(ruleset.event_model)


def _validate_event_model(model: EventModel) -> None:
    for name in ("out", "walk", "single", "double", "triple", "home_run"):
        rates: EventRates = getattr(model, name)
        if rates.minimum > rates.maximum:
            raise ValueError(f"event_model.{name}: minimum must be <= maximum")
        if not 0.0 <= rates.minimum <= 1.0 or not 0.0 <= rates.maximum <= 1.0:
            raise ValueError(f"event_model.{name}: bounds must be probabilities")
        if not rates.minimum <= rates.base <= rates.maximum:
            raise ValueError(f"event_model.{name}: base must sit inside its bounds")


def ruleset_to_payload(ruleset: SimulationRuleset) -> dict[str, Any]:
    """Serialize a ruleset so a run can be replayed under the rules it was played by."""

    return asdict(ruleset)


def ruleset_from_payload(payload: dict[str, Any]) -> SimulationRuleset:
    """Rebuild a stored ruleset.

    Kept tolerant of a payload written before a field existed: a run recorded then was
    played under that field's default, so falling back to it is what reproduces the
    game, and refusing to load would lose the replay entirely.
    """

    model = payload.get("event_model")
    return SimulationRuleset(
        ruleset_id=str(payload.get("ruleset_id", DEFAULT_RULESET.ruleset_id)),
        scheduled_innings=int(payload.get("scheduled_innings", DEFAULT_RULESET.scheduled_innings)),
        max_innings=int(payload.get("max_innings", DEFAULT_RULESET.max_innings)),
        max_plate_appearances_per_half=int(
            payload.get(
                "max_plate_appearances_per_half",
                DEFAULT_RULESET.max_plate_appearances_per_half,
            )
        ),
        skip_home_bottom_if_leading_after_top_final=bool(
            payload.get(
                "skip_home_bottom_if_leading_after_top_final",
                DEFAULT_RULESET.skip_home_bottom_if_leading_after_top_final,
            )
        ),
        enable_walkoff=bool(payload.get("enable_walkoff", DEFAULT_RULESET.enable_walkoff)),
        enable_runner_on_second_in_extras=bool(
            payload.get(
                "enable_runner_on_second_in_extras",
                DEFAULT_RULESET.enable_runner_on_second_in_extras,
            )
        ),
        runner_on_second_start_inning=int(
            payload.get(
                "runner_on_second_start_inning", DEFAULT_RULESET.runner_on_second_start_inning
            )
        ),
        home_field_event_boost=float(
            payload.get("home_field_event_boost", DEFAULT_RULESET.home_field_event_boost)
        ),
        event_model=_event_model_from_payload(model) if model else DEFAULT_EVENT_MODEL,
    )


def _event_model_from_payload(payload: dict[str, Any]) -> EventModel:
    def rates(name: str) -> EventRates:
        block = payload[name]
        return EventRates(
            base=float(block["base"]),
            sensitivity=float(block["sensitivity"]),
            minimum=float(block["minimum"]),
            maximum=float(block["maximum"]),
            home_boost=float(block.get("home_boost", 0.0)),
        )

    return EventModel(
        attack_offense=float(payload["attack_offense"]),
        attack_discipline=float(payload["attack_discipline"]),
        attack_power=float(payload["attack_power"]),
        attack_speed=float(payload["attack_speed"]),
        prevention_prevention=float(payload["prevention_prevention"]),
        prevention_command=float(payload["prevention_command"]),
        prevention_range=float(payload["prevention_range"]),
        out=rates("out"),
        walk=rates("walk"),
        single=rates("single"),
        double=rates("double"),
        triple=rates("triple"),
        home_run=rates("home_run"),
    )


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
