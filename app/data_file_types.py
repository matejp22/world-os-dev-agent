from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DataFileKind = Literal[
    "MASTER_ROADMAP",
    "PROJECT_ROADMAP",
]

DataFileOperation = Literal[
    "CREATE",
    "REPLACE",
]

DataFileStatus = Literal[
    "DRAFT",
    "READY_FOR_HUMAN_REVIEW",
    "APPROVED",
    "APPLYING",
    "CREATED_VERIFIED",
    "REPLACED_VERIFIED",
    "APPLIED",
    "REJECTED",
    "ROLLED_BACK",
    "ROLLBACK_FAILED",
]


@dataclass(frozen=True)
class DataFilePatchRecord:
    patch_id: str
    format_version: str
    operation: DataFileOperation
    data_kind: DataFileKind
    workspace_name: str
    target_file: str
    original_sha256: str | None
    candidate_sha256: str
    candidate_file: str
    diff_file: str
    validation_passed: bool
    semantic_decision: str
    semantic_review: str
    status: DataFileStatus
    created_at: str