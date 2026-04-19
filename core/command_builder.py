"""FFmpeg command generation helpers."""

from __future__ import annotations

from string import Formatter

from .models import Preset
from .ffprobe_reader import summarize_media_info


def build_ffmpeg_command(
    ffmpeg_path: str,
    input_path: str,
    output_path: str,
    preset: Preset,
    overwrite: bool = False,
    media_info: dict | None = None,
) -> list[str]:
    command = [ffmpeg_path, "-hide_banner", "-y" if overwrite else "-n", "-i", input_path]
    variables = {**preset.settings}
    pre_args: list[str] = []
    post_args: list[str] = []

    if media_info and preset.type == "video":
        summary = summarize_media_info(media_info)
        source_height = summary.get("height")
        target_height = variables.get("scale_height")
        if isinstance(source_height, int) and isinstance(target_height, int) and source_height < target_height:
            variables["scale_height"] = source_height

    if preset.type == "image":
        image_filter = _build_image_filter(variables)
        if image_filter:
            pre_args.extend(["-vf", image_filter])
        image_mode = str(variables.get("image_mode", "lossy"))
        enhance_mode = str(variables.get("image_enhance_mode", "off"))
        image_webp_preset = str(variables.get("image_webp_preset", "")).strip()
        image_jpeg_huffman = str(variables.get("image_jpeg_huffman", "")).strip()
        preserve_metadata = variables.get("image_preserve_metadata", True)
        compression_level = variables.get("compression_level")
        output_extension = str(preset.output_extension).lower()

        if preserve_metadata:
            post_args.extend(["-map_metadata", "0"])
        else:
            post_args.extend(["-map_metadata", "-1"])

        if output_extension == ".webp" and (image_mode == "lossless" or variables.get("lossless")):
            post_args.extend(["-lossless", "1"])

        if output_extension == ".webp" and image_webp_preset:
            post_args.extend(["-preset", image_webp_preset])

        if output_extension in {".jpg", ".jpeg"} and image_jpeg_huffman:
            post_args.extend(["-huffman", image_jpeg_huffman])

        if isinstance(compression_level, int) and output_extension in {".webp", ".png"}:
            normalized_level = max(0, min(9, compression_level))
            post_args.extend(["-compression_level", str(normalized_level)])

        post_args.extend(["-frames:v", "1", "-update", "1"])

    if preset.type == "video":
        audio_stream_mode = str(variables.get("audio_stream_mode", "all"))
        subtitle_mode = str(variables.get("subtitle_mode", "hidden"))
        audio_languages = variables.get("audio_languages")
        output_extension = str(preset.output_extension).lower()
        audio_stream_count = None
        source_audio_streams: list[dict[str, object]] = []
        source_audio_languages: list[str] = []
        source_subtitle_streams: list[dict[str, object]] = []
        subtitle_stream_kinds: list[str] = []
        if media_info:
            summary = summarize_media_info(media_info)
            count = summary.get("audio_stream_count")
            if isinstance(count, int) and count > 0:
                audio_stream_count = count
            streams = summary.get("audio_streams")
            if isinstance(streams, list):
                source_audio_streams = [stream for stream in streams if isinstance(stream, dict)]
            source_languages = summary.get("audio_stream_languages")
            if isinstance(source_languages, list):
                source_audio_languages = [str(language).strip() for language in source_languages]
            subtitle_streams = summary.get("subtitle_streams")
            if isinstance(subtitle_streams, list):
                source_subtitle_streams = [stream for stream in subtitle_streams if isinstance(stream, dict)]
            kinds = summary.get("subtitle_stream_kinds")
            if isinstance(kinds, list):
                subtitle_stream_kinds = [str(kind).lower() for kind in kinds if str(kind).strip()]

        pre_args.extend(["-map", "0:v:0"])
        selected_audio_indices = _select_audio_stream_indices(audio_stream_mode, source_audio_streams)
        if audio_stream_mode == "all":
            pre_args.extend(["-map", "0:a?"])
        elif audio_stream_mode == "first":
            pre_args.extend(["-map", "0:a:0?"])
            audio_stream_count = 1
        elif audio_stream_mode in {"japanese_only", "japanese_only_first"}:
            if selected_audio_indices:
                for index in selected_audio_indices:
                    pre_args.extend(["-map", f"0:a:{index}?"])
                audio_stream_count = len(selected_audio_indices)
            else:
                pre_args.extend(["-map", "0:a?"])
        else:
            pre_args.extend(["-map", "0:a?"])
        if subtitle_mode == "hidden":
            pre_args.extend(["-sn"])
        elif subtitle_mode in {"text", "copy"}:
            if output_extension in {".mp4", ".m4v", ".mov"} and "image" in subtitle_stream_kinds:
                if subtitle_mode == "copy":
                    raise ValueError("画像字幕を含む字幕をそのまま保持する場合は MKV を選んでください。")
            if subtitle_mode == "text":
                selected_subtitle_indices = _select_subtitle_stream_indices("text", source_subtitle_streams)
                for index in selected_subtitle_indices:
                    pre_args.extend(["-map", f"0:{index}?"])
                if output_extension in {".mp4", ".m4v", ".mov"}:
                    post_args.extend(["-c:s", "mov_text"])
                else:
                    post_args.extend(["-c:s", "copy"])
            else:
                selected_subtitle_indices = _select_subtitle_stream_indices("copy", source_subtitle_streams)
                if output_extension in {".mp4", ".m4v", ".mov"}:
                    raise ValueError("画像字幕を含む字幕をそのまま保持する場合は MKV を選んでください。")
                for index in selected_subtitle_indices:
                    pre_args.extend(["-map", f"0:{index}?"])
                post_args.extend(["-c:s", "copy"])

        pre_args.extend(["-map_chapters", "0", "-map_metadata", "0"])
        selected_source_languages = _pick_selected_audio_languages(source_audio_languages, selected_audio_indices)
        language_map = _resolve_audio_language_map(audio_languages, selected_source_languages, audio_stream_count)
        for index, lang in enumerate(language_map):
            if lang:
                post_args.extend([f"-metadata:s:a:{index}", f"language={lang}"])
        default_audio_index = _select_preferred_audio_default_index(language_map, selected_source_languages)
        if default_audio_index is not None:
            post_args.extend([f"-disposition:a:{default_audio_index}", "default"])

    if preset.type == "audio":
        audio_mode = str(variables.get("audio_mode", "reencode"))
        bitrate_mode = str(variables.get("audio_bitrate_mode", "cbr"))
        preserve_metadata = variables.get("preserve_metadata", True)
        if audio_mode == "copy":
            variables["audio_codec"] = "copy"
        elif bitrate_mode == "vbr":
            if str(variables.get("audio_codec", "")) == "libopus":
                post_args.extend(["-vbr", "on"])
        elif str(variables.get("audio_codec", "")) == "libopus":
            post_args.extend(["-vbr", "off"])

        if preserve_metadata:
            post_args.extend(["-map_metadata", "0", "-map_chapters", "0"])

    command.extend(pre_args)

    formatter = Formatter()
    for token in preset.ffmpeg_args_template:
        command.append(_format_token(token, variables, formatter))

    command.extend(post_args)
    command.append(output_path)
    return command


def _format_token(token: str, variables: dict[str, object], formatter: Formatter) -> str:
    if "{" not in token:
        return token
    try:
        return formatter.vformat(token, (), variables)
    except (KeyError, IndexError) as exc:
        raise ValueError(f"プリセットテンプレートの変数が不足しています: {token}") from exc


def _resolve_audio_language_map(value: object, fallback_languages: list[str], limit: int | None = None) -> list[str]:
    if isinstance(value, list):
        languages = [str(item).strip() for item in value if str(item).strip()]
        if limit is not None and limit > 0:
            languages = languages[:limit]
        if languages:
            return languages
    if isinstance(value, str) and value.strip():
        languages = [value.strip()]
        if limit is not None and limit > 0:
            return languages[:limit]
        return languages
    normalized_fallbacks = [str(item).strip() for item in fallback_languages if str(item).strip()]
    if limit is not None and limit > 0:
        normalized_fallbacks = normalized_fallbacks[:limit]
    return normalized_fallbacks


def _pick_selected_audio_languages(source_languages: list[str], selected_indices: list[int]) -> list[str]:
    if not selected_indices:
        return list(source_languages)
    selected: list[str] = []
    for index in selected_indices:
        if 0 <= index < len(source_languages):
            selected.append(source_languages[index])
    return selected


def _select_audio_stream_indices(audio_stream_mode: str, source_audio_streams: list[dict[str, object]]) -> list[int]:
    all_indices = [int(stream.get("stream_index", stream_index)) for stream_index, stream in enumerate(source_audio_streams)]
    if audio_stream_mode == "first":
        return [0] if all_indices else []
    if audio_stream_mode == "japanese_only":
        japanese_indices = _find_japanese_audio_stream_indices(source_audio_streams)
        return japanese_indices if japanese_indices else all_indices
    if audio_stream_mode == "japanese_only_first":
        japanese_indices = _find_japanese_audio_stream_indices(source_audio_streams)
        return japanese_indices[:1] if japanese_indices else all_indices
    return all_indices


def _select_subtitle_stream_indices(subtitle_mode: str, source_subtitle_streams: list[dict[str, object]]) -> list[int]:
    text_indices: list[int] = []
    all_indices: list[int] = []
    for stream in source_subtitle_streams:
        index = stream.get("stream_index")
        kind = str(stream.get("kind") or "").lower()
        if not isinstance(index, int):
            continue
        all_indices.append(index)
        if kind == "text":
            text_indices.append(index)
    if subtitle_mode == "text":
        return text_indices
    if subtitle_mode == "copy":
        return all_indices
    return []


def _find_japanese_audio_stream_indices(source_audio_streams: list[dict[str, object]]) -> list[int]:
    japanese_tags = {"jpn", "ja", "jp", "japanese"}
    selected: list[int] = []
    for stream in source_audio_streams:
        index = stream.get("stream_index")
        language = str(stream.get("language") or "").strip().lower()
        if not isinstance(index, int):
            continue
        if language in japanese_tags or any(tag in language for tag in japanese_tags):
            selected.append(index)
    return selected


def _select_preferred_audio_default_index(language_map: list[str], source_languages: list[str]) -> int | None:
    preferred_tags = {"jpn", "ja", "jp", "japanese"}
    combined_sources = [str(item).strip().lower() for item in language_map]
    if not any(combined_sources):
        combined_sources = [str(item).strip().lower() for item in source_languages]

    for preferred in preferred_tags:
        for index, lang in enumerate(combined_sources):
            if lang == preferred or preferred in lang:
                return index

    for index, lang in enumerate(combined_sources):
        if lang:
            return index
    return 0 if combined_sources else None


def _build_image_filter(variables: dict[str, object]) -> str:
    enhance_mode = str(variables.get("image_enhance_mode", "off"))
    if enhance_mode == "enhance":
        return _build_image_enhance_filter(variables)
    return _build_image_scale_filter(variables)


def _build_image_enhance_filter(variables: dict[str, object]) -> str:
    parts: list[str] = []
    max_width = variables.get("max_width")
    max_height = variables.get("max_height")
    has_width = isinstance(max_width, int) and max_width > 0
    has_height = isinstance(max_height, int) and max_height > 0
    if has_width or has_height:
        width_expr = f"min(iw,{max_width})" if has_width else "iw"
        height_expr = f"min(ih,{max_height})" if has_height else "ih"
        parts.append(f"w={width_expr}")
        parts.append(f"h={height_expr}")
        parts.append("force_original_aspect_ratio=decrease")
    upscaler = str(variables.get("image_upscaler", "spline36")).strip()
    downscaler = str(variables.get("image_downscaler", "mitchell")).strip()
    shader_path = str(variables.get("image_shader_path", "")).strip()
    shader_cache = str(variables.get("image_shader_cache", "")).strip()
    deband = variables.get("image_deband", True)
    if upscaler:
        parts.append(f"upscaler={upscaler}")
    if downscaler:
        parts.append(f"downscaler={downscaler}")
    if deband:
        parts.append("deband=true")
    if shader_path:
        parts.append(f"custom_shader_path={_escape_filter_value(shader_path)}")
    if shader_cache:
        parts.append(f"shader_cache={_escape_filter_value(shader_cache)}")
    return "libplacebo" if not parts else f"libplacebo={':'.join(parts)}"


def _build_image_scale_filter(variables: dict[str, object]) -> str:
    max_width = variables.get("max_width")
    max_height = variables.get("max_height")
    has_width = isinstance(max_width, int) and max_width > 0
    has_height = isinstance(max_height, int) and max_height > 0

    if not has_width and not has_height:
        return ""
    if has_width and has_height:
        return f"scale='min(iw,{max_width})':'min(ih,{max_height})':force_original_aspect_ratio=decrease"
    if has_width:
        return f"scale='min(iw,{max_width})':-2"
    return f"scale=-2:'min(ih,{max_height})'"


def _escape_filter_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace(",", "\\,")