from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from baseball_sim.sim.state_machine import PlayTrace


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class MatchContext:
    match_id: str
    seed: int
    model_version: str
    data_snapshot_id: str
    home_team_id: int
    away_team_id: int
    ruleset_id: str
    ruleset_checksum: str
    scheduled_innings: int


class GameLogWriter:
    def __init__(self, *, log_dir: str | Path, context: MatchContext) -> None:
        self._context = context
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._jsonl_path = self._log_dir / f"{self._context.match_id}.jsonl"
        self._summary_path = self._log_dir / f"{self._context.match_id}_summary.json"
        self._registry_path = self._log_dir / "match_registry.jsonl"

    @property
    def jsonl_path(self) -> Path:
        return self._jsonl_path

    @property
    def summary_path(self) -> Path:
        return self._summary_path

    def write_header(self, *, extra: dict[str, Any] | None = None) -> None:
        payload = {
            "type": "meta",
            "timestamp_utc": utc_now_iso(),
            "context": asdict(self._context),
            "extra": extra or {},
        }
        self._append_jsonl(payload)
        self._append_registry(
            {
                "timestamp_utc": utc_now_iso(),
                "match_id": self._context.match_id,
                "seed": self._context.seed,
                "model_version": self._context.model_version,
                "data_snapshot_id": self._context.data_snapshot_id,
                "home_team_id": self._context.home_team_id,
                "away_team_id": self._context.away_team_id,
                "ruleset_id": self._context.ruleset_id,
                "ruleset_checksum": self._context.ruleset_checksum,
            }
        )

    def write_play(self, *, play: PlayTrace) -> None:
        payload = {
            "type": "play",
            "timestamp_utc": utc_now_iso(),
            "match_id": self._context.match_id,
            "play": asdict(play),
        }
        self._append_jsonl(payload)

    def write_summary(self, *, payload: dict[str, Any]) -> None:
        summary_payload = {
            "timestamp_utc": utc_now_iso(),
            "context": asdict(self._context),
            "summary": payload,
        }
        self._summary_path.write_text(
            json.dumps(summary_payload, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        self._append_jsonl(
            {
                "type": "summary",
                "timestamp_utc": utc_now_iso(),
                "match_id": self._context.match_id,
                "summary": payload,
            }
        )

    def _append_jsonl(self, payload: dict[str, Any]) -> None:
        with self._jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")

    def _append_registry(self, payload: dict[str, Any]) -> None:
        with self._registry_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")
