from __future__ import annotations

import hashlib
import json
from typing import Any


def create_match_id(
    *,
    seed: int,
    model_version: str,
    data_snapshot_id: str,
    home_team_id: int,
    away_team_id: int,
    scheduled_innings: int,
    ruleset_id: str,
    ruleset_checksum: str,
) -> str:
    payload: dict[str, Any] = {
        "seed": seed,
        "model_version": model_version,
        "data_snapshot_id": data_snapshot_id,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "scheduled_innings": scheduled_innings,
        "ruleset_id": ruleset_id,
        "ruleset_checksum": ruleset_checksum,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()[:16]
    return f"match_{digest}"
