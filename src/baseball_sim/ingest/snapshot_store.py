from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def payload_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def make_snapshot_id(*, source_system: str, category: str, sha256_hex: str) -> str:
    return f"{source_system}:{category}:{sha256_hex[:16]}"


@dataclass(frozen=True)
class StoredSnapshot:
    snapshot_id: str
    source_system: str
    category: str
    payload_sha256: str
    relative_path: str
    bytes_written: int
    already_exists: bool


class SnapshotStore:
    """Stores immutable raw payload snapshots keyed by deterministic hash."""

    def __init__(self, root_dir: str | Path) -> None:
        self._root_dir = Path(root_dir)

    def write_snapshot(
        self,
        *,
        source_system: str,
        category: str,
        payload: Any,
    ) -> StoredSnapshot:
        canonical_bytes = canonical_json_bytes(payload)
        sha256_hex = hashlib.sha256(canonical_bytes).hexdigest()
        snapshot_id = make_snapshot_id(
            source_system=source_system,
            category=category,
            sha256_hex=sha256_hex,
        )
        subdir = self._root_dir / source_system / category / sha256_hex[:2]
        path = subdir / f"{sha256_hex}.json"
        relative_path = path.relative_to(self._root_dir).as_posix()
        already_exists = path.exists()
        if not already_exists:
            subdir.mkdir(parents=True, exist_ok=True)
            # Use exclusive creation to protect immutable snapshots from overwrite.
            with path.open("xb") as handle:
                handle.write(canonical_bytes)
        return StoredSnapshot(
            snapshot_id=snapshot_id,
            source_system=source_system,
            category=category,
            payload_sha256=sha256_hex,
            relative_path=relative_path,
            bytes_written=len(canonical_bytes),
            already_exists=already_exists,
        )
