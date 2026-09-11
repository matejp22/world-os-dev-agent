from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_new_data_file_artifacts(
    *,
    candidate_path: Path,
    candidate_bytes: bytes,
    diff_path: Path,
    diff_bytes: bytes,
) -> None:
    """Atomically create exactly two new DATA_FILE_V1 artifact files."""
    if not isinstance(candidate_path, Path):
        raise ValueError("candidate_path must be a pathlib.Path instance.")

    if not isinstance(diff_path, Path):
        raise ValueError("diff_path must be a pathlib.Path instance.")

    if type(candidate_bytes) is not bytes:
        raise ValueError("candidate_bytes must be exactly bytes.")

    if type(diff_bytes) is not bytes:
        raise ValueError("diff_bytes must be exactly bytes.")

    if candidate_path == diff_path:
        raise ValueError("candidate_path and diff_path must differ.")

    candidate_parent = candidate_path.parent
    diff_parent = diff_path.parent

    if not candidate_parent.exists():
        raise ValueError("candidate_path.parent must exist.")

    if not diff_parent.exists():
        raise ValueError("diff_path.parent must exist.")

    if not candidate_parent.is_dir():
        raise ValueError("candidate_path.parent must be a directory.")

    if not diff_parent.is_dir():
        raise ValueError("diff_path.parent must be a directory.")

    if candidate_path.exists() or candidate_path.is_symlink():
        raise FileExistsError("candidate_path must not already exist.")

    if diff_path.exists() or diff_path.is_symlink():
        raise FileExistsError("diff_path must not already exist.")

    temporary_paths: list[Path] = []

    try:
        candidate_temporary = _write_temporary_bytes(
            parent=candidate_parent,
            prefix=f".{candidate_path.name}.",
            data=candidate_bytes,
        )
        temporary_paths.append(candidate_temporary)

        diff_temporary = _write_temporary_bytes(
            parent=diff_parent,
            prefix=f".{diff_path.name}.",
            data=diff_bytes,
        )
        temporary_paths.append(diff_temporary)

        _publish_new_artifact(
            temporary_path=candidate_temporary,
            final_path=candidate_path,
        )
        temporary_paths.remove(candidate_temporary)

        _publish_new_artifact(
            temporary_path=diff_temporary,
            final_path=diff_path,
        )
        temporary_paths.remove(diff_temporary)

        _verify_artifact(
            path=candidate_path,
            expected_bytes=candidate_bytes,
            label="candidate",
        )
        _verify_artifact(
            path=diff_path,
            expected_bytes=diff_bytes,
            label="diff",
        )
    finally:
        for temporary_path in temporary_paths:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _write_temporary_bytes(
    *,
    parent: Path,
    prefix: str,
    data: bytes,
) -> Path:
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=prefix,
        dir=str(parent),
    )
    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(data)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
    except BaseException:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise

    return temporary_path


def _publish_new_artifact(
    *,
    temporary_path: Path,
    final_path: Path,
) -> None:
    if final_path.exists() or final_path.is_symlink():
        raise FileExistsError("artifact path was created concurrently.")

    try:
        os.link(temporary_path, final_path)
    except FileExistsError:
        raise FileExistsError(
            "artifact path was created concurrently."
        ) from None

    temporary_path.unlink()


def _verify_artifact(
    *,
    path: Path,
    expected_bytes: bytes,
    label: str,
) -> None:
    if not path.exists():
        raise RuntimeError(f"published {label} artifact does not exist.")

    if not path.is_file():
        raise RuntimeError(
            f"published {label} artifact is not a regular file."
        )

    if path.is_symlink():
        raise RuntimeError(f"published {label} artifact is a symlink.")

    if path.read_bytes() != expected_bytes:
        raise RuntimeError(
            f"published {label} artifact failed integrity verification."
        )