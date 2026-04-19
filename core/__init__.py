"""Core modules for the browser FFMPEG application."""

from .command_builder import build_ffmpeg_command
from .history_manager import HistoryManager
from .ffmpeg_runner import run_ffmpeg
from .ffprobe_reader import extract_duration_seconds, read_media_info
from .file_scanner import scan_input_files
from .job_manager import JobManager
from .models import FileTask, HistoryEntry, Job, Preset, ScanResult
from .output_manager import build_output_path, ensure_output_directory
from .preset_manager import PresetManager
from .validators import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    SUPPORTED_TYPES,
    VIDEO_EXTENSIONS,
    is_supported_file,
    validate_input_mode,
    normalize_path,
    validate_input_path,
    validate_output_path,
    validate_preset,
    validate_type,
)
