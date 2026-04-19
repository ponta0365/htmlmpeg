"""ffprobe metadata reader."""

from __future__ import annotations

import json
import subprocess
from typing import Any


TEXT_SUBTITLE_CODECS = {
    "ass",
    "dvbsub",
    "mov_text",
    "subrip",
    "srt",
    "ssa",
    "text",
    "webvtt",
}

IMAGE_SUBTITLE_CODECS = {
    "dvd_subtitle",
    "dvb_subtitle",
    "hdmv_pgs_subtitle",
    "pgs",
    "pgssub",
    "xsub",
}


def read_media_info(ffprobe_path: str, input_path: str) -> dict[str, Any]:
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        input_path,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return json.loads(result.stdout or "{}")


def extract_duration_seconds(info: dict[str, Any]) -> float | None:
    format_info = info.get("format", {})
    duration = format_info.get("duration")
    if duration is None:
        return None
    try:
        return float(duration)
    except (TypeError, ValueError):
        return None


def extract_first_stream(info: dict[str, Any], codec_type: str) -> dict[str, Any]:
    for stream in info.get("streams", []):
        if stream.get("codec_type") == codec_type:
            return stream
    return {}


def classify_subtitle_codec(codec_name: str | None) -> str:
    normalized = str(codec_name or "").lower()
    if normalized in TEXT_SUBTITLE_CODECS:
        return "text"
    if normalized in IMAGE_SUBTITLE_CODECS:
        return "image"
    return "other"


def summarize_media_info(info: dict[str, Any]) -> dict[str, Any]:
    video = extract_first_stream(info, "video")
    audio_streams = [stream for stream in info.get("streams", []) if stream.get("codec_type") == "audio"]
    audio = audio_streams[0] if audio_streams else {}
    subtitle_streams = [stream for stream in info.get("streams", []) if stream.get("codec_type") == "subtitle"]
    summary: dict[str, Any] = {}

    duration = extract_duration_seconds(info)
    if duration is not None:
        summary["duration_seconds"] = duration

    if video:
        summary["video_codec"] = video.get("codec_name")
        summary["width"] = video.get("width")
        summary["height"] = video.get("height")
        summary["frame_rate"] = video.get("r_frame_rate") or video.get("avg_frame_rate")

    if audio:
        summary["audio_codec"] = audio.get("codec_name")
        summary["sample_rate"] = audio.get("sample_rate")
        summary["channels"] = audio.get("channels")
    if audio_streams:
        summary["audio_stream_count"] = len(audio_streams)
        audio_details: list[dict[str, Any]] = []
        audio_languages: list[str] = []
        for index, stream in enumerate(audio_streams):
            codec_name = stream.get("codec_name")
            tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
            language = str(tags.get("language", "")).strip() if isinstance(tags, dict) else ""
            audio_details.append(
                {
                    "stream_index": index,
                    "codec_name": codec_name,
                    "language": language or None,
                }
            )
            audio_languages.append(language)
        summary["audio_streams"] = audio_details
        summary["audio_stream_languages"] = audio_languages

    if subtitle_streams:
        subtitle_details: list[dict[str, Any]] = []
        subtitle_kinds: list[str] = []
        for index, stream in enumerate(subtitle_streams):
            codec_name = stream.get("codec_name")
            kind = classify_subtitle_codec(codec_name)
            subtitle_kinds.append(kind)
            subtitle_details.append(
                {
                    "stream_index": stream.get("index", index),
                    "codec_name": codec_name,
                    "kind": kind,
                    "language": stream.get("tags", {}).get("language") if isinstance(stream.get("tags"), dict) else None,
                }
            )
        summary["subtitle_stream_count"] = len(subtitle_streams)
        summary["subtitle_text_stream_count"] = sum(1 for kind in subtitle_kinds if kind == "text")
        summary["subtitle_image_stream_count"] = sum(1 for kind in subtitle_kinds if kind == "image")
        summary["subtitle_other_stream_count"] = sum(1 for kind in subtitle_kinds if kind == "other")
        summary["subtitle_stream_kinds"] = subtitle_kinds
        summary["subtitle_streams"] = subtitle_details

    return summary
