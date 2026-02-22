import pytest
from pydantic import ValidationError

from baseball_sim.domain.contracts import DeterministicContext


def test_deterministic_context_rejects_invalid_model_version() -> None:
    with pytest.raises(ValidationError):
        DeterministicContext(
            seed=1,
            model_version="baseline v1",
            data_snapshot_id="snapshot-2026-02-22",
        )


def test_deterministic_context_accepts_valid_values() -> None:
    context = DeterministicContext(
        seed=1,
        model_version="baseline-v1",
        data_snapshot_id="snapshot-2026-02-22",
    )

    assert context.seed == 1
    assert context.model_version == "baseline-v1"
