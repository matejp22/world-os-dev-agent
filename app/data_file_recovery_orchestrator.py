from pathlib import Path

from app.data_file_partial_state_recovery import (
    DataFileRecoveryResult,
    recover_data_file_partial_state,
)

from app.data_file_recovery_queue import (
    discover_data_file_recovery_candidates,
)


def run_data_file_recovery_cycle(
    *,
    queue_dir: Path,
) -> tuple[DataFileRecoveryResult, ...]:
    entries = discover_data_file_recovery_candidates(
        queue_dir=queue_dir,
    )

    results: list[DataFileRecoveryResult] = []

    for entry in entries:
        expected_current_bytes = entry.queue_path.read_bytes()

        result = recover_data_file_partial_state(
            queue_path=entry.queue_path,
            expected_current_bytes=expected_current_bytes,
            record=entry.record,
            candidate_path=entry.candidate_path,
        )

        results.append(result)

    return tuple(results)