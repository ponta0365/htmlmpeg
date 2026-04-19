"""Output path helpers."""

from __future__ import annotations

from pathlib import Path


def ensure_output_directory(path: str) -> Path:
    output_dir = Path(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def build_output_path(
    source_path: str,
    output_root: str,
    output_extension: str,
    keep_folder_structure: bool = False,
    source_root: str | None = None,
    overwrite: bool = False,
    suffix: str = "_compressed",
) -> str:
    source = Path(source_path)
    output_dir = ensure_output_directory(output_root)

    if keep_folder_structure and source_root:
        relative = source.relative_to(Path(source_root))
        target = output_dir / relative
    else:
        target = output_dir / source.name

    target = target.with_suffix(output_extension)
    target = target.with_name(f"{target.stem}{suffix}{target.suffix}")
    target.parent.mkdir(parents=True, exist_ok=True)

    if overwrite:
        return str(target)

    candidate = target
    index = 1
    while candidate.exists():
        candidate = candidate.with_name(f"{target.stem}_{index:03d}{target.suffix}")
        index += 1
    return str(candidate)
