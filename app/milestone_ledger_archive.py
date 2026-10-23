"""Immutable milestone ledger archival."""
import hashlib
import os
from pathlib import Path

def archive_execution_ledger(source: Path, archive_dir: Path, milestone_id: str) -> Path:
    if not milestone_id or not milestone_id.startswith("milestone-") or not all(c.isalnum() or c == "-" for c in milestone_id):
        raise ValueError("Invalid milestone ID.")
    data = source.read_bytes()
    import json
    payload = json.loads(data)
    if not isinstance(payload, dict) or payload.get("milestone_id") != milestone_id:
        raise RuntimeError("Ledger milestone ID does not match archive ID.")
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination = archive_dir / f"{milestone_id}.json"
    digest = hashlib.sha256(data).hexdigest()
    try:
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Existing ledger archive differs.")
        return destination
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Ledger archive verification failed.")
    return destination
