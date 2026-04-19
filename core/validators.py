"""Validation helpers for user input and presets."""

from __future__ import annotations

from pathlib import Path

from .models import Preset

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".opus", ".ogg"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

SUPPORTED_TYPES = {
    "video": VIDEO_EXTENSIONS,
    "audio": AUDIO_EXTENSIONS,
    "image": IMAGE_EXTENSIONS,
}

SUPPORTED_INPUT_MODES = {"file", "folder"}


def normalize_path(value: str) -> str:
    return str(Path(value).expanduser().resolve())


def validate_type(value: str) -> None:
    if value not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported type: {value}")


def validate_input_mode(value: str) -> None:
    if value not in SUPPORTED_INPUT_MODES:
        raise ValueError(f"Unsupported input_mode: {value}")


def validate_preset(preset: Preset) -> None:
    validate_type(preset.type)
    if not isinstance(preset.id, str) or not preset.id.strip():
        raise ValueError("Preset id is required")
    if not isinstance(preset.name, str) or not preset.name.strip():
        raise ValueError("Preset name is required")
    if not isinstance(preset.description, str):
        raise ValueError("Preset description must be a string")
    if not isinstance(preset.output_extension, str) or not preset.output_extension.strip():
        raise ValueError("Preset output_extension is required")
    if not preset.output_extension.startswith("."):
        raise ValueError("Preset output_extension must start with '.'")
    if not isinstance(preset.settings, dict):
        raise ValueError("Preset settings must be an object")
    if not isinstance(preset.ffmpeg_args_template, list) or not all(
        isinstance(item, str) for item in preset.ffmpeg_args_template
    ):
        raise ValueError("Preset ffmpeg_args_template must be a list of strings")


def is_supported_file(path: str, file_type: str) -> bool:
    validate_type(file_type)
    return Path(path).suffix.lower() in SUPPORTED_TYPES[file_type]


def validate_input_path(path: str) -> None:
    if not path:
        raise ValueError("Input path is required")
    if not Path(path).exists():
        raise FileNotFoundError(path)


def validate_output_path(path: str) -> None:
    if not path:
        raise ValueError("Output path is required")
