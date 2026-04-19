from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import socket
from copy import deepcopy
from pathlib import Path
from dataclasses import asdict
import webbrowser

from flask import Flask, jsonify, render_template, request

from core import Preset, PresetManager
from core.command_builder import build_ffmpeg_command
from core.history_manager import HistoryManager
from core.ffmpeg_runner import run_ffmpeg
from core.ffprobe_reader import read_media_info, summarize_media_info
from core.file_scanner import scan_input_files
from core.job_manager import JobManager
from core.output_manager import build_output_path, ensure_output_directory
from core.validators import normalize_path, validate_input_mode, validate_input_path, validate_output_path, validate_preset, validate_type


BASE_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
APP_DATA_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else BASE_DIR
SETTINGS_PATH = APP_DATA_DIR / "config" / "app_settings.json"
HISTORY_PATH = APP_DATA_DIR / "logs" / "job_history.json"
RUNTIME_PRESET_DIR = APP_DATA_DIR / "presets"
DEFAULT_SETTINGS = {
    "ffmpeg_dir": "",
    "log_dir": "logs",
    "temp_dir": "temp",
    "host": "127.0.0.1",
    "port": 5000,
    "debug": True,
    "default_preset_ids": {},
}


def _load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return deepcopy(DEFAULT_SETTINGS)
    loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    settings = deepcopy(DEFAULT_SETTINGS)
    settings.update({key: loaded[key] for key in DEFAULT_SETTINGS if key in loaded})
    legacy_ffmpeg_path = str(loaded.get("ffmpeg_path", "")).strip()
    legacy_ffprobe_path = str(loaded.get("ffprobe_path", "")).strip()
    if not settings.get("ffmpeg_dir"):
        if legacy_ffmpeg_path:
            settings["ffmpeg_dir"] = str(Path(legacy_ffmpeg_path).expanduser().resolve().parent)
        elif legacy_ffprobe_path:
            settings["ffmpeg_dir"] = str(Path(legacy_ffprobe_path).expanduser().resolve().parent)
    settings["default_preset_ids"] = _normalize_default_preset_ids(loaded.get("default_preset_ids", {}))
    return settings


def _resource_path(*parts: str) -> Path:
    return BUNDLE_DIR.joinpath(*parts)


def _ensure_runtime_preset_dir() -> Path:
    bundled_preset_dir = _resource_path("presets")
    if RUNTIME_PRESET_DIR.exists():
        return RUNTIME_PRESET_DIR
    if bundled_preset_dir.exists():
        shutil.copytree(bundled_preset_dir, RUNTIME_PRESET_DIR)
    else:
        RUNTIME_PRESET_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_PRESET_DIR


def _save_settings(settings: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_app_settings(payload: dict) -> dict:
    normalized = deepcopy(DEFAULT_SETTINGS)
    for key in DEFAULT_SETTINGS:
        if key in payload:
            normalized[key] = payload[key]
    if not normalized.get("ffmpeg_dir"):
        legacy_ffmpeg_path = str(payload.get("ffmpeg_path", "")).strip()
        legacy_ffprobe_path = str(payload.get("ffprobe_path", "")).strip()
        if legacy_ffmpeg_path:
            normalized["ffmpeg_dir"] = str(Path(legacy_ffmpeg_path).expanduser().resolve().parent)
        elif legacy_ffprobe_path:
            normalized["ffmpeg_dir"] = str(Path(legacy_ffprobe_path).expanduser().resolve().parent)
    normalized["default_preset_ids"] = _normalize_default_preset_ids(payload.get("default_preset_ids", {}))
    return normalized


def _normalize_default_preset_ids(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for preset_type in ("video", "audio", "image"):
        preset_id = value.get(preset_type, "")
        if isinstance(preset_id, str) and preset_id.strip():
            normalized[preset_type] = preset_id.strip()
    return normalized


APP_SETTINGS = _load_settings()


def _get_default_preset_ids(settings: dict) -> dict[str, str]:
    return _normalize_default_preset_ids(settings.get("default_preset_ids", {}))


def _set_default_preset_id(settings: dict, preset_type: str, preset_id: str) -> None:
    default_ids = _get_default_preset_ids(settings)
    default_ids[preset_type] = preset_id
    settings["default_preset_ids"] = default_ids
    _save_settings(settings)


def _clear_default_preset_id(settings: dict, preset_type: str) -> None:
    default_ids = _get_default_preset_ids(settings)
    if preset_type in default_ids:
        default_ids.pop(preset_type, None)
        settings["default_preset_ids"] = default_ids
        _save_settings(settings)


def _serialize_preset(preset: Preset) -> dict:
    return {
        "id": preset.id,
        "name": preset.name,
        "type": preset.type,
        "description": preset.description,
        "output_extension": preset.output_extension,
        "settings": preset.settings,
        "ffmpeg_args_template": preset.ffmpeg_args_template,
    }


def _serialize_preset_entry(preset: Preset, source: str, is_default: bool = False) -> dict:
    data = _serialize_preset(preset)
    data["source"] = source
    data["is_default"] = is_default
    return data


def _normalize_encoder_name(value: str) -> str:
    return value.strip().lower()


def _get_available_encoders(ffmpeg_dir: str, cache: dict[str, set[str]]) -> set[str]:
    resolved = ffmpeg_dir or "__default__"
    cached = cache.get(resolved)
    if cached is not None:
        return cached
    command = _resolve_executable_from_dir(ffmpeg_dir, "ffmpeg.exe")
    try:
        completed = subprocess.run(
            [command, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        cache[resolved] = set()
        return cache[resolved]

    encoders: set[str] = set()
    for line in (completed.stdout or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("------"):
            continue
        parts = stripped.split()
        if len(parts) >= 2 and len(parts[0]) >= 6:
            flags = parts[0]
            if all(ch in "A.VS.DILF" or ch == "." for ch in flags[:6]):
                encoders.add(_normalize_encoder_name(parts[1]))
    cache[resolved] = encoders
    return encoders


def _get_required_encoders(preset: Preset) -> list[str]:
    required: list[str] = []
    if preset.type == "video":
        video_codec = str(preset.settings.get("video_codec", "")).strip()
        audio_codec = str(preset.settings.get("audio_codec", "")).strip()
        if video_codec and video_codec != "copy":
            required.append(video_codec)
        if audio_codec and audio_codec != "copy":
            required.append(audio_codec)
        return required
    if preset.type == "audio":
        audio_codec = str(preset.settings.get("audio_codec", "")).strip()
        if audio_codec and audio_codec != "copy":
            required.append(audio_codec)
        return required
    if preset.type == "image":
        extension = str(preset.output_extension).lower()
        if extension == ".webp":
            required.append("libwebp_anim")
        elif extension in {".jpg", ".jpeg"}:
            required.append("mjpeg")
        elif extension == ".png":
            required.append("png")
        return required
    return required


def _check_preset_available(preset: Preset, available_encoders: set[str]) -> tuple[bool, list[str]]:
    required = _get_required_encoders(preset)
    missing = [name for name in required if _normalize_encoder_name(name) not in available_encoders]
    return not missing, missing


def _build_preset_from_payload(preset_type: str, preset_data: dict) -> Preset:
    if not isinstance(preset_data, dict):
        raise ValueError("preset is required")

    preset = Preset(
        id=preset_data.get("id", ""),
        name=preset_data.get("name", ""),
        type=preset_type,
        description=preset_data.get("description", ""),
        output_extension=preset_data.get("output_extension", ""),
        settings=preset_data.get("settings", {}),
        ffmpeg_args_template=preset_data.get("ffmpeg_args_template", []),
    )
    validate_preset(preset)
    return preset


def _get_json_object():
    payload = request.get_json(force=True)
    if not isinstance(payload, dict):
        return None, (jsonify({"ok": False, "message": "JSON が不正です。"}), 400)
    return payload, None


def _validate_type_or_400(preset_type: str):
    try:
        validate_type(preset_type)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    return None


def _validate_input_mode_or_400(input_mode: str):
    try:
        validate_input_mode(input_mode)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    return None


def _export_configuration(settings: dict, preset_manager: PresetManager) -> dict:
    return {
        "schema_version": 1,
        "app_settings": settings,
        "user_presets": {
            "video": [_serialize_preset(item) for item in preset_manager.list_user_presets("video")],
            "audio": [_serialize_preset(item) for item in preset_manager.list_user_presets("audio")],
            "image": [_serialize_preset(item) for item in preset_manager.list_user_presets("image")],
        },
    }


def _import_configuration(payload: dict, settings: dict, preset_manager: PresetManager) -> tuple[dict, str]:
    imported_settings = payload.get("app_settings")
    if imported_settings is None:
        normalized_settings = None
    elif isinstance(imported_settings, dict):
        normalized_settings = _normalize_app_settings(imported_settings)
    else:
        raise ValueError("app_settings must be an object")

    imported_presets = payload.get("user_presets")
    validated_presets: dict[str, list[Preset]] = {"video": [], "audio": [], "image": []}
    if imported_presets is None:
        pass
    elif isinstance(imported_presets, dict):
        for preset_type in ("video", "audio", "image"):
            items = imported_presets.get(preset_type, [])
            if not isinstance(items, list):
                raise ValueError(f"{preset_type} presets must be an array")
            for item in items:
                validated_presets[preset_type].append(_build_preset_from_payload(preset_type, item))
    else:
        raise ValueError("user_presets must be an object")

    if normalized_settings is not None:
        settings.clear()
        settings.update(normalized_settings)
        _save_settings(settings)

    if isinstance(imported_presets, dict):
        for preset_type in ("video", "audio", "image"):
            preset_manager.clear_user_presets(preset_type)
            for preset in validated_presets[preset_type]:
                preset_manager.save_user_preset(preset)

    return settings, "設定をインポートしました。"


def _resolve_executable(configured_path: str | None, executable_name: str) -> str:
    if configured_path:
        return configured_path
    discovered = shutil.which(executable_name)
    if discovered:
        return discovered
    return executable_name


def _resolve_executable_from_dir(configured_dir: str | None, executable_name: str) -> str:
    configured = str(configured_dir or "").strip()
    if configured:
        candidate = Path(configured).expanduser().resolve() / executable_name
        if candidate.is_file():
            return str(candidate)
    discovered = shutil.which(executable_name)
    if discovered:
        return discovered
    return executable_name


def _resolve_executable_status(configured_dir: str | None, executable_name: str) -> tuple[bool, str, str]:
    configured = str(configured_dir or "").strip()
    if configured:
        candidate = Path(configured).expanduser().resolve() / executable_name
        if candidate.is_file():
            return True, str(candidate), "directory"
        return False, str(candidate), "configured_missing"
    discovered = shutil.which(executable_name)
    if discovered:
        return True, discovered, "path"
    return False, executable_name, "missing"


def _find_available_port(host: str, preferred_port: int, max_attempts: int = 100) -> int:
    if preferred_port < 1:
        preferred_port = 5000
    for port in range(preferred_port, preferred_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise OSError(f"No available port found from {preferred_port} to {preferred_port + max_attempts - 1}")


def _format_probe_summary(summary: dict) -> str:
    parts: list[str] = []
    if summary.get("duration_seconds") is not None:
        parts.append(f"duration={summary['duration_seconds']:.2f}s")
    if summary.get("width") and summary.get("height"):
        parts.append(f"resolution={summary['width']}x{summary['height']}")
    if summary.get("video_codec"):
        parts.append(f"video={summary['video_codec']}")
    if summary.get("audio_codec"):
        parts.append(f"audio={summary['audio_codec']}")
    if summary.get("sample_rate"):
        parts.append(f"sample_rate={summary['sample_rate']}")
    if summary.get("channels"):
        parts.append(f"channels={summary['channels']}")
    return ", ".join(parts) if parts else "probe info unavailable"


def _format_size(value: int | None) -> str:
    if value is None:
        return "-"
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value / (1024 * 1024):.1f} MiB"


def _summarize_ffmpeg_failure(log_lines: list[str], return_code: int) -> str:
    joined = "\n".join(log_lines).lower()
    if "no such file or directory" in joined:
        return "入力ファイルまたは出力先が見つかりません。"
    if "permission denied" in joined or "access denied" in joined:
        return "保存先の権限がありません。"
    if "invalid argument" in joined:
        return "FFmpeg の引数が不正です。"
    if "unknown encoder" in joined:
        return "指定したコーデックが使えません。"
    if "encoder not found" in joined:
        return "エンコーダが見つかりません。"
    if return_code < 0:
        return "FFmpeg が異常終了しました。"
    return f"ffmpeg exit code {return_code}"


def _serialize_file_task(file_task):
    data = asdict(file_task)
    input_size = file_task.size_before
    output_size = file_task.size_after
    if input_size is not None and output_size is not None and input_size > 0:
        data["compression_ratio"] = round((output_size / input_size) * 100, 1)
    else:
        data["compression_ratio"] = None
    data["size_before_label"] = _format_size(input_size)
    data["size_after_label"] = _format_size(output_size)
    return data


def _serialize_history_entry(entry: dict) -> dict:
    return entry


def _record_history_entry(history_manager: HistoryManager, job) -> None:
    if job.state not in {"completed", "failed", "stopped"}:
        return
    duration_seconds = None
    if job.started_at and job.finished_at:
        duration_seconds = (job.finished_at - job.started_at).total_seconds()
    history_manager.append_entry(
        {
            "job_id": job.job_id,
            "type": job.type,
            "state": job.state,
            "preset_id": job.preset_id,
            "total_count": len(job.target_files),
            "completed_count": len(job.completed_files),
            "failed_count": len(job.failed_files),
            "remaining_count": len(job.remaining_files),
            "input_mode": job.input_mode,
            "input_path": job.input_path,
            "output_path": job.output_path,
            "duration_seconds": duration_seconds,
        }
    )


def _mark_remaining(job, remaining_files):
    for file_task in remaining_files:
        file_task.status = "remaining"
    job.remaining_files.extend(remaining_files)


def _pick_with_tkinter(kind: str, preset_type: str | None = None) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        if kind == "file":
            filetypes = [
                ("All files", "*.*"),
            ]
            if preset_type == "video":
                filetypes = [("Video files", "*.mp4 *.mkv *.avi *.mov *.webm *.m4v"), *filetypes]
            elif preset_type == "audio":
                filetypes = [("Audio files", "*.mp3 *.wav *.m4a *.aac *.flac *.opus *.ogg"), *filetypes]
            elif preset_type == "image":
                filetypes = [("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), *filetypes]
            selected = filedialog.askopenfilename(parent=root, filetypes=filetypes)
        elif kind == "shader":
            filetypes = [
                ("Shader files", "*.hook *.glsl *.frag *.fs"),
                ("All files", "*.*"),
            ]
            selected = filedialog.askopenfilename(parent=root, filetypes=filetypes)
        else:
            selected = filedialog.askdirectory(parent=root, mustexist=False)
        return selected or None
    finally:
        root.destroy()


def create_app():
    app = Flask(
        __name__,
        template_folder=str(_resource_path("templates")),
        static_folder=str(_resource_path("static")),
    )
    settings = APP_SETTINGS
    preset_manager = PresetManager(_ensure_runtime_preset_dir())
    history_manager = HistoryManager(HISTORY_PATH)
    job_manager = JobManager()
    stop_events: dict[str, threading.Event] = {}
    worker_threads: dict[str, threading.Thread] = {}
    encoder_cache: dict[str, set[str]] = {}

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        ffmpeg_available, ffmpeg_path, ffmpeg_source = _resolve_executable_status(settings.get("ffmpeg_dir"), "ffmpeg.exe")
        ffprobe_available, ffprobe_path, ffprobe_source = _resolve_executable_status(settings.get("ffmpeg_dir"), "ffprobe.exe")
        encoders = _get_available_encoders(settings.get("ffmpeg_dir", ""), encoder_cache)
        download_url = "https://ffmpeg.org/download.html"
        messages = []
        if ffmpeg_available:
            messages.append(f"FFmpeg: {ffmpeg_path} ({ffmpeg_source})")
        else:
            messages.append(f"FFmpeg が見つかりません。フォルダを指定するか PATH に追加してください。ダウンロード: {download_url}")
        if ffprobe_available:
            messages.append(f"FFprobe: {ffprobe_path} ({ffprobe_source})")
        else:
            messages.append(f"FFprobe が見つかりません。フォルダを指定するか PATH に追加してください。ダウンロード: {download_url}")
        return jsonify(
            {
                "status": "ok",
                "ffmpeg": ffmpeg_path,
                "ffprobe": ffprobe_path,
                "ffmpeg_available": ffmpeg_available,
                "ffprobe_available": ffprobe_available,
                "ffmpeg_source": ffmpeg_source,
                "ffprobe_source": ffprobe_source,
                "available_encoder_count": len(encoders),
                "download_url": download_url,
                "message": "/ ".join(messages),
            }
        )

    @app.get("/api/settings")
    def get_settings():
        return jsonify(
            {
                "ok": True,
                "settings": {
                    "ffmpeg_dir": settings.get("ffmpeg_dir", ""),
                },
            }
        )

    @app.post("/api/settings/save")
    def save_settings():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        ffmpeg_dir = str(payload.get("ffmpeg_dir", "")).strip()
        if not ffmpeg_dir:
            legacy_ffmpeg_path = str(payload.get("ffmpeg_path", "")).strip()
            legacy_ffprobe_path = str(payload.get("ffprobe_path", "")).strip()
            if legacy_ffmpeg_path:
                ffmpeg_dir = str(Path(legacy_ffmpeg_path).expanduser().resolve().parent)
            elif legacy_ffprobe_path:
                ffmpeg_dir = str(Path(legacy_ffprobe_path).expanduser().resolve().parent)
        if ffmpeg_dir:
            normalized_dir = normalize_path(ffmpeg_dir)
            ffmpeg_exe = Path(normalized_dir) / "ffmpeg.exe"
            ffprobe_exe = Path(normalized_dir) / "ffprobe.exe"
            if not ffmpeg_exe.is_file() or not ffprobe_exe.is_file():
                return (
                    jsonify(
                        {
                            "ok": False,
                            "message": "指定フォルダ内に ffmpeg.exe と ffprobe.exe が見つかりません。フォルダを確認するか空欄にして PATH を使ってください。ダウンロード: https://ffmpeg.org/download.html",
                        }
                    ),
                    400,
                )
            settings["ffmpeg_dir"] = normalized_dir
        else:
            settings["ffmpeg_dir"] = ""
        _save_settings(settings)
        encoder_cache.clear()
        return jsonify({"ok": True, "message": "FFmpeg フォルダ設定を保存しました。"})

    @app.post("/api/probe")
    def probe_media():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        input_path = payload.get("path", "")
        if not input_path:
            return jsonify({"ok": False, "message": "path is required"}), 400
        try:
            normalized_path = normalize_path(input_path)
            validate_input_path(normalized_path)
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        ffprobe_path = _resolve_executable_from_dir(settings.get("ffmpeg_dir"), "ffprobe.exe")
        try:
            media_info = read_media_info(ffprobe_path, normalized_path)
        except FileNotFoundError:
            return jsonify({"ok": False, "message": "ffprobe が見つかりません。"}), 400
        except subprocess.CalledProcessError as exc:
            return jsonify({"ok": False, "message": f"ffprobe 失敗: {exc}"}), 400
        except Exception as exc:  # pragma: no cover - defensive guard
            return jsonify({"ok": False, "message": f"ffprobe 失敗: {exc}"}), 400
        summary = summarize_media_info(media_info)
        return jsonify({"ok": True, "media_info": summary})

    @app.errorhandler(ValueError)
    def handle_value_error(exc: ValueError):
        return jsonify({"ok": False, "message": str(exc)}), 400

    @app.errorhandler(FileNotFoundError)
    def handle_file_not_found_error(exc: FileNotFoundError):
        message = str(exc) or "ファイルが見つかりません。"
        return jsonify({"ok": False, "message": message}), 400

    @app.get("/api/config/export")
    def export_config():
        return jsonify(_export_configuration(settings, preset_manager))

    @app.post("/api/config/import")
    def import_config():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        try:
            _import_configuration(payload, settings, preset_manager)
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        return jsonify({"ok": True, "message": "設定をインポートしました。"})

    @app.get("/api/history")
    def get_history():
        limit = request.args.get("limit", "20")
        state = request.args.get("state", "all")
        try:
            limit_value = max(1, min(100, int(limit)))
        except ValueError:
            limit_value = 20
        if state not in {"all", "completed", "failed", "stopped"}:
            return jsonify({"ok": False, "message": "state is invalid"}), 400
        return jsonify(history_manager.list_history(limit_value, state=state))

    @app.get("/api/presets")
    def get_presets():
        preset_type = request.args.get("type", "")
        if not preset_type:
            return jsonify({"ok": False, "message": "type is required"}), 400
        error_response = _validate_type_or_400(preset_type)
        if error_response:
            return error_response
        default_preset_ids = _get_default_preset_ids(settings)
        default_preset_id = default_preset_ids.get(preset_type, "")
        encoders = _get_available_encoders(settings.get("ffmpeg_dir", ""), encoder_cache)
        presets = [
            {
                **_serialize_preset_entry(item, "builtin", item.id == default_preset_id),
                **({
                    "available": True,
                    "missing_encoders": [],
                } if _check_preset_available(item, encoders)[0] else {
                    "available": False,
                    "missing_encoders": _check_preset_available(item, encoders)[1],
                }),
            }
            for item in preset_manager.list_builtin_presets(preset_type)
        ]
        presets.extend(
            {
                **_serialize_preset_entry(item, "user", item.id == default_preset_id),
                **({
                    "available": True,
                    "missing_encoders": [],
                } if _check_preset_available(item, encoders)[0] else {
                    "available": False,
                    "missing_encoders": _check_preset_available(item, encoders)[1],
                }),
            }
            for item in preset_manager.list_user_presets(preset_type)
        )
        return jsonify(presets)

    @app.post("/api/presets/save")
    def save_preset():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        preset_type = payload.get("type", "")
        preset_data = payload.get("preset", {})
        if not preset_type:
            return jsonify({"ok": False, "message": "type is required"}), 400
        error_response = _validate_type_or_400(preset_type)
        if error_response:
            return error_response
        try:
            preset = _build_preset_from_payload(preset_type, preset_data)
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        if preset_manager.get_builtin_preset(preset_type, preset.id):
            return jsonify({"ok": False, "message": "初期プリセットと同じIDは使えません。"}), 400
        preset_manager.save_user_preset(preset)
        return jsonify({"ok": True, "message": "プリセットを保存しました。"})

    @app.post("/api/presets/save-as-default")
    def save_preset_as_default():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        preset_type = payload.get("type", "")
        preset_data = payload.get("preset", {})
        if not preset_type:
            return jsonify({"ok": False, "message": "type is required"}), 400
        error_response = _validate_type_or_400(preset_type)
        if error_response:
            return error_response
        try:
            preset = _build_preset_from_payload(preset_type, preset_data)
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        if preset_manager.get_builtin_preset(preset_type, preset.id):
            return jsonify({"ok": False, "message": "初期プリセットと同じIDは使えません。"}), 400
        preset_manager.save_user_preset(preset)
        _set_default_preset_id(settings, preset_type, preset.id)
        return jsonify({"ok": True, "message": "プリセットを保存して既定に設定しました。"})

    @app.post("/api/presets/delete")
    def delete_preset():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        preset_type = payload.get("type", "")
        preset_id = payload.get("preset_id", "")
        if not preset_type:
            return jsonify({"ok": False, "message": "type is required"}), 400
        error_response = _validate_type_or_400(preset_type)
        if error_response:
            return error_response
        if not preset_id:
            return jsonify({"ok": False, "message": "preset_id is required"}), 400
        if preset_manager.get_builtin_preset(preset_type, preset_id):
            return jsonify({"ok": False, "message": "初期プリセットは削除できません。"}), 400
        preset_manager.delete_user_preset(preset_type, preset_id)
        if _get_default_preset_ids(settings).get(preset_type) == preset_id:
            _clear_default_preset_id(settings, preset_type)
        return jsonify({"ok": True, "message": "プリセットを削除しました。"})

    @app.post("/api/presets/restore-defaults")
    def restore_defaults():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        preset_type = payload.get("type", "")
        if not preset_type:
            return jsonify({"ok": False, "message": "type is required"}), 400
        error_response = _validate_type_or_400(preset_type)
        if error_response:
            return error_response
        preset_manager.clear_user_presets(preset_type)
        _clear_default_preset_id(settings, preset_type)
        return jsonify({"ok": True, "message": "初期状態に戻しました。"})

    @app.post("/api/presets/clear-default")
    def clear_default_preset():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        preset_type = payload.get("type", "")
        if not preset_type:
            return jsonify({"ok": False, "message": "type is required"}), 400
        error_response = _validate_type_or_400(preset_type)
        if error_response:
            return error_response
        _clear_default_preset_id(settings, preset_type)
        return jsonify({"ok": True, "message": "既定を解除しました。"})

    @app.post("/api/scan")
    def scan():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        preset_type = payload.get("type", "")
        input_mode = payload.get("input_mode", "file")
        input_path = payload.get("input_path", "")
        include_subfolders = bool(payload.get("include_subfolders", False))
        if not preset_type:
            return jsonify({"ok": False, "message": "type is required"}), 400
        error_response = _validate_type_or_400(preset_type)
        if error_response:
            return error_response
        error_response = _validate_input_mode_or_400(input_mode)
        if error_response:
            return error_response
        try:
            result = scan_input_files(
                input_type=preset_type,
                input_mode=input_mode,
                input_path=input_path,
                include_subfolders=include_subfolders,
            )
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        return jsonify(
            {
                "files": [asdict(file) for file in result.files],
                "count": len(result.files),
                "excluded_count": result.excluded_count,
            }
        )

    @app.post("/api/start")
    def start():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        preset_type = payload.get("type", "")
        input_mode = payload.get("input_mode", "file")
        input_path = payload.get("input_path", "")
        include_subfolders = bool(payload.get("include_subfolders", False))
        output_path = payload.get("output_path", "")
        keep_folder_structure = bool(payload.get("keep_folder_structure", False))
        overwrite = bool(payload.get("overwrite", False))
        preset_id = payload.get("preset_id", "")

        if not preset_type:
            return jsonify({"ok": False, "message": "type is required"}), 400
        error_response = _validate_type_or_400(preset_type)
        if error_response:
            return error_response
        error_response = _validate_input_mode_or_400(input_mode)
        if error_response:
            return error_response
        if not output_path:
            return jsonify({"ok": False, "message": "output_path is required"}), 400
        validate_output_path(output_path)

        presets = {item.id: item for item in preset_manager.list_presets(preset_type)}
        preset = presets.get(preset_id)
        if preset is None:
            return jsonify({"ok": False, "message": "プリセットが見つかりません。"}), 400
        encoders = _get_available_encoders(settings.get("ffmpeg_dir", ""), encoder_cache)
        available, missing_encoders = _check_preset_available(preset, encoders)
        if not available:
            return jsonify(
                {
                    "ok": False,
                    "message": f"必要なエンコーダが見つかりません: {', '.join(missing_encoders)}",
                }
            ), 400

        try:
            scan_result = scan_input_files(
                input_type=preset_type,
                input_mode=input_mode,
                input_path=input_path,
                include_subfolders=include_subfolders,
            )
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        if not scan_result.files:
            return jsonify({"ok": False, "message": "処理対象ファイルがありません。"}), 400

        job = job_manager.create_job(preset_type)
        job.input_mode = input_mode
        job.input_path = normalize_path(input_path)
        job.include_subfolders = include_subfolders
        job.output_path = normalize_path(output_path)
        job.keep_folder_structure = keep_folder_structure
        job.overwrite = overwrite
        job.preset_id = preset_id
        job.target_files = scan_result.files
        job_manager.update_state(job.job_id, "running")
        ffprobe_path = _resolve_executable_from_dir(settings.get("ffmpeg_dir"), "ffprobe.exe")

        stop_event = threading.Event()
        stop_events[job.job_id] = stop_event
        history_written = False

        def worker() -> None:
            nonlocal history_written
            try:
                for index, file_task in enumerate(job.target_files):
                    if stop_event.is_set():
                        job_manager.append_log(job.job_id, "停止要求を受け付けました。")
                        _mark_remaining(job, job.target_files[index:])
                        job_manager.update_state(job.job_id, "stopped")
                        return

                    source = Path(file_task.source_path)
                    media_info: dict = {}
                    try:
                        media_info = read_media_info(ffprobe_path, str(source))
                        file_task.media_info = summarize_media_info(media_info)
                        file_task.duration = file_task.media_info.get("duration_seconds")
                        try:
                            file_task.size_before = source.stat().st_size
                        except OSError:
                            file_task.size_before = None
                        job.current_media_info = file_task.media_info
                        job_manager.append_log(job.job_id, f"probe: {_format_probe_summary(file_task.media_info)}")
                    except FileNotFoundError:
                        job_manager.append_log(job.job_id, "ffprobe が見つかりません。")
                    except Exception as exc:  # pragma: no cover - defensive guard
                        job_manager.append_log(job.job_id, f"ffprobe 失敗: {exc}")

                    output_file = build_output_path(
                        source_path=str(source),
                        output_root=job.output_path,
                        output_extension=preset.output_extension,
                        keep_folder_structure=job.keep_folder_structure,
                        source_root=job.input_path if job.input_mode == "folder" else None,
                        overwrite=job.overwrite,
                    )
                    file_task.output_path = output_file
                    job.current_file = str(source)

                    try:
                        command = build_ffmpeg_command(
                            _resolve_executable_from_dir(settings.get("ffmpeg_dir"), "ffmpeg.exe"),
                            str(source),
                            output_file,
                            preset,
                            overwrite=job.overwrite,
                            media_info=media_info,
                        )
                    except ValueError as exc:
                        file_task.status = "failed"
                        file_task.error_message = str(exc)
                        job.failed_files.append(file_task)
                        job_manager.append_log(job.job_id, f"設定エラー: {source.name} / {exc}")
                        continue
                    job_manager.append_log(job.job_id, f"開始: {source.name}")
                    ffmpeg_lines: list[str] = []
                    try:
                        return_code, process_id = run_ffmpeg(
                            command,
                            on_line=lambda line: (job_manager.append_log(job.job_id, line), ffmpeg_lines.append(line)),
                            stop_event=stop_event,
                        )
                        job.process_id = process_id
                    except FileNotFoundError:
                        file_task.status = "failed"
                        file_task.error_message = "ffmpeg が見つかりません。"
                        job.failed_files.append(file_task)
                        job_manager.append_log(job.job_id, "ffmpeg が見つかりません。")
                        job_manager.update_state(job.job_id, "failed")
                        return
                    except Exception as exc:  # pragma: no cover - defensive guard
                        file_task.status = "failed"
                        file_task.error_message = str(exc)
                        job.failed_files.append(file_task)
                        job_manager.append_log(job.job_id, f"例外: {exc}")
                        job_manager.update_state(job.job_id, "failed")
                        return

                    if stop_event.is_set():
                        file_task.status = "remaining"
                        job.remaining_files.append(file_task)
                        job_manager.append_log(job.job_id, f"停止: {source.name}")
                        remaining_index = index + 1
                        if remaining_index < len(job.target_files):
                            _mark_remaining(job, job.target_files[remaining_index:])
                        job_manager.update_state(job.job_id, "stopped")
                        return
                    elif return_code == 0:
                        file_task.status = "completed"
                        try:
                            file_task.size_after = Path(output_file).stat().st_size
                        except OSError:
                            file_task.size_after = None
                        job.completed_files.append(file_task)
                        if file_task.size_before is not None and file_task.size_after is not None:
                            ratio = (file_task.size_after / file_task.size_before) * 100 if file_task.size_before else 0
                            job_manager.append_log(
                                job.job_id,
                                f"サイズ: {_format_size(file_task.size_before)} -> {_format_size(file_task.size_after)} ({ratio:.1f}%)",
                            )
                        job_manager.append_log(job.job_id, f"成功: {source.name}")
                    else:
                        file_task.status = "failed"
                        file_task.error_message = _summarize_ffmpeg_failure(ffmpeg_lines[-20:], return_code)
                        job.failed_files.append(file_task)
                        job_manager.append_log(job.job_id, f"失敗: {source.name} / {file_task.error_message}")

                if stop_event.is_set():
                    job_manager.update_state(job.job_id, "stopped")
                else:
                    job_manager.update_state(job.job_id, "completed")
            finally:
                if not history_written and job.state in {"completed", "failed", "stopped"}:
                    _record_history_entry(history_manager, job)
                    history_written = True
                stop_events.pop(job.job_id, None)
                worker_threads.pop(job.job_id, None)

        thread = threading.Thread(target=worker, daemon=True)
        worker_threads[job.job_id] = thread
        thread.start()

        return jsonify(
            {
                "ok": True,
                "job_id": job.job_id,
                "state": job.state,
                "total_count": len(job.target_files),
                "completed_count": len(job.completed_files),
                "failed_count": len(job.failed_files),
            }
        )

    @app.post("/api/stop")
    def stop():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        job_id = payload.get("job_id", "")
        stop_event = stop_events.get(job_id)
        job = job_manager.get_job(job_id)
        if job is None:
            return jsonify({"ok": False, "message": "ジョブが見つかりません。"}), 404
        if stop_event is None:
            return jsonify({"ok": False, "message": "停止可能な実行ジョブがありません。"}), 400
        job_manager.update_state(job_id, "stopping")
        stop_event.set()
        return jsonify({"ok": True, "message": "停止要求を送信しました。"})

    @app.get("/api/status")
    def status():
        job_id = request.args.get("job_id", "")
        job = job_manager.get_job(job_id)
        if job is None:
            return jsonify({"ok": False, "message": "ジョブが見つかりません。"}), 404
        total_count = len(job.target_files)
        completed_count = len(job.completed_files)
        failed_count = len(job.failed_files)
        progress = 0
        if total_count:
            progress = int((completed_count + failed_count) / total_count * 100)
        return jsonify(
            {
                "ok": True,
                "job_id": job.job_id,
                "state": job.state,
                "total_count": total_count,
                "completed_count": completed_count,
                "failed_count": failed_count,
                "remaining_count": len(job.remaining_files),
                "current_file": job.current_file,
                "current_media_info": job.current_media_info,
                "completed_files": [_serialize_file_task(item) for item in job.completed_files],
                "failed_files": [_serialize_file_task(item) for item in job.failed_files],
                "remaining_files": [_serialize_file_task(item) for item in job.remaining_files],
                "progress_percent": progress,
                "last_log_lines": job.logs[-20:],
            }
        )

    @app.post("/api/open-output")
    def open_output():
        payload, error_response = _get_json_object()
        if error_response:
            return error_response
        path = payload.get("path", "")
        if not path:
            return jsonify({"ok": False, "message": "保存先が空です。"}), 400
        try:
            output_dir = ensure_output_directory(path)
            os.startfile(output_dir)  # type: ignore[attr-defined]
        except OSError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        return jsonify({"ok": True, "message": "保存先を開きました。"})

    @app.get("/api/pick-file")
    def pick_file():
        preset_type = request.args.get("type", "video")
        if preset_type:
            try:
                validate_type(preset_type)
            except ValueError as exc:
                return jsonify({"ok": False, "message": str(exc)}), 400
        selected = _pick_with_tkinter("file", preset_type)
        if not selected:
            return jsonify({"ok": False, "message": "選択がキャンセルされました。"}), 400
        return jsonify({"ok": True, "path": selected})

    @app.get("/api/pick-folder")
    def pick_folder():
        selected = _pick_with_tkinter("folder")
        if not selected:
            return jsonify({"ok": False, "message": "選択がキャンセルされました。"}), 400
        return jsonify({"ok": True, "path": selected})

    @app.get("/api/pick-shader")
    def pick_shader():
        selected = _pick_with_tkinter("shader")
        if not selected:
            return jsonify({"ok": False, "message": "選択がキャンセルされました。"}), 400
        return jsonify({"ok": True, "path": selected})

    return app


app = create_app()


if __name__ == "__main__":
    server_host = APP_SETTINGS.get("host", "127.0.0.1")
    preferred_port = int(APP_SETTINGS.get("port", 5000))
    server_port = _find_available_port(server_host, preferred_port)
    server_url = f"http://{server_host}:{server_port}"
    auto_open_browser = getattr(sys, "frozen", False) or os.environ.get("BROWSER_FFMPEG_OPEN_BROWSER", "0") == "1"

    if auto_open_browser:
        def _open_browser() -> None:
            webbrowser.open(server_url)

        threading.Timer(1.0, _open_browser).start()
    if server_port != preferred_port:
        print(f"Port {preferred_port} is in use. Falling back to {server_port}.")
    print(f"Server URL: {server_url}")
    app.run(
        host=server_host,
        port=server_port,
        debug=bool(APP_SETTINGS.get("debug", True)) and not getattr(sys, "frozen", False),
    )