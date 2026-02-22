import json
from pathlib import Path

from baseball_sim.ingest.snapshot_store import SnapshotStore


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_snapshot_store_is_deterministic_and_immutable(tmp_path: Path) -> None:
    payload = {"b": 2, "a": 1, "nested": {"z": 9, "y": [3, 2, 1]}}
    store = SnapshotStore(tmp_path)

    first = store.write_snapshot(
        source_system="mlb_stats_api",
        category="teams",
        payload=payload,
    )
    second = store.write_snapshot(
        source_system="mlb_stats_api",
        category="teams",
        payload=payload,
    )

    assert first.snapshot_id == second.snapshot_id
    assert first.payload_sha256 == second.payload_sha256
    assert first.already_exists is False
    assert second.already_exists is True

    file_path = tmp_path / first.relative_path
    assert file_path.exists()
    assert _read_json(file_path) == {"a": 1, "b": 2, "nested": {"y": [3, 2, 1], "z": 9}}
