from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Preset:
    id: str
    name: str
    type: str
    description: str
    output_extension: str
    settings: dict[str, Any]
    ffmpeg_args_template: list[str]


@dataclass(slots=True)
class FileTask:
    source_path: str
    relative_path: str
    output_path: str
    status: str = "pending"
    error_message: str = ""
    duration: float | None = None
    size_before: int | None = None
    size_after: int | None = None
    media_info: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Job:
    job_id: str
    type: str
    state: str = "idle"
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    input_mode: str = ""
    input_path: str = ""
    include_subfolders: bool = False
    output_path: str = ""
    keep_folder_structure: bool = False
    overwrite: bool = False
    preset_id: str = ""
    target_files: list[FileTask] = field(default_factory=list)
    completed_files: list[FileTask] = field(default_factory=list)
    failed_files: list[FileTask] = field(default_factory=list)
    remaining_files: list[FileTask] = field(default_factory=list)
    current_file: str = ""
    current_media_info: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    process_id: int | None = None


@dataclass(slots=True)
class ScanResult:
    files: list[FileTask]
    excluded_count: int = 0


@dataclass(slots=True)
class HistoryEntry:
    job_id: str
    type: str
    state: str
    preset_id: str
    total_count: int
    completed_count: int
    failed_count: int
    remaining_count: int
    input_mode: str
    input_path: str
    output_path: str
    duration_seconds: float | None = None
    completed_at: str | None = None
