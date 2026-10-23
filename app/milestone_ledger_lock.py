"""Shared cross-process lock for canonical milestone ledger updates."""
import msvcrt
import time
from contextlib import contextmanager
from pathlib import Path

@contextmanager
def milestone_ledger_lock(context_dir: Path, timeout: float = 5.0):
    if not context_dir.is_dir():
        raise RuntimeError("Canonical context directory missing.")
    lock_path = context_dir / ".milestone_execution_ledger.lock"
    with open(lock_path, "a+b") as handle:
        handle.seek(0)
        if handle.seek(0, 2) == 0:
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Milestone ledger lock timeout.")
                time.sleep(0.1)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
