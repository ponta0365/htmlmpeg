"""Input file scanning helpers."""

from __future__ import annotations

from pathlib import Path

from .models import FileTask, ScanResult
from .validators import is_supported_file, normalize_path, validate_input_mode, validate_input_path, validate_type


def scan_input_files(
    input_type: str,
    input_mode: str,
    input_path: str,
    include_subfolders: bool = False,
    output_root: str | None = None,
) -> ScanResult:
    validate_type(input_type)
    validate_input_mode(input_mode)
    validate_input_path(input_path)

    source_path = Path(normalize_path(input_path))
    files: list[FileTask] = []
    excluded_count = 0

    if input_mode == "file":
        if is_supported_file(str(source_path), input_type):
            output_dir = Path(output_root) if output_root else source_path.parent
            files.append(
                FileTask(
                    source_path=str(source_path),
                    relative_path=source_path.name,
                    output_path=str(output_dir / source_path.name),
                )
            )
        else:
            excluded_count = 1
        return ScanResult(files=files, excluded_count=excluded_count)

    search_iter = source_path.rglob("*") if include_subfolders else source_path.glob("*")
    for item in sorted(search_iter):
        if not item.is_file():
            continue
        if not is_supported_file(str(item), input_type):
            excluded_count += 1
            continue
        relative_path = item.relative_to(source_path).as_posix()
        output_dir = Path(output_root) if output_root else source_path
        files.append(
            FileTask(
                source_path=str(item),
                relative_path=relative_path,
                output_path=str(output_dir / relative_path),
            )
        )

    return ScanResult(files=files, excluded_count=excluded_count)
