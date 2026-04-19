"""Preset management helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Preset
from .validators import validate_preset


class PresetManager:
    def __init__(self, preset_dir: str | Path = "presets") -> None:
        self.preset_dir = Path(preset_dir)
        self.user_preset_file = self.preset_dir / "user_presets.json"

    def load_builtin_presets(self, preset_type: str) -> list[Preset]:
        file_map = {
            "video": "video_default.json",
            "audio": "audio_default.json",
            "image": "image_default.json",
        }
        preset_file = self.preset_dir / file_map[preset_type]
        return self._load_preset_file(preset_file)

    def list_builtin_presets(self, preset_type: str) -> list[Preset]:
        return self.load_builtin_presets(preset_type)

    def load_user_presets(self, preset_type: str) -> list[Preset]:
        if not self.user_preset_file.exists():
            return []
        try:
            data = json.loads(self.user_preset_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(data, dict):
            return []
        items = data.get(preset_type, [])
        if not isinstance(items, list):
            return []
        presets: list[Preset] = []
        migrated = False
        for item in items:
            try:
                preset, changed = self._to_preset(item, migrate_legacy=True)
                presets.append(preset)
                migrated = migrated or changed
            except (KeyError, TypeError, ValueError):
                continue
        if migrated:
            self._rewrite_migrated_user_presets(data)
        return presets

    def list_user_presets(self, preset_type: str) -> list[Preset]:
        return self.load_user_presets(preset_type)

    def list_presets(self, preset_type: str) -> list[Preset]:
        return self.load_builtin_presets(preset_type) + self.load_user_presets(preset_type)

    def save_user_preset(self, preset: Preset) -> None:
        validate_preset(preset)
        all_user_presets = self._read_user_preset_map()
        bucket = all_user_presets.setdefault(preset.type, [])
        bucket = [item for item in bucket if item["id"] != preset.id]
        bucket.append(self._preset_to_dict(preset))
        all_user_presets[preset.type] = bucket
        self.preset_dir.mkdir(parents=True, exist_ok=True)
        self.user_preset_file.write_text(json.dumps(all_user_presets, ensure_ascii=False, indent=2), encoding="utf-8")

    def delete_user_preset(self, preset_type: str, preset_id: str) -> None:
        all_user_presets = self._read_user_preset_map()
        bucket = all_user_presets.get(preset_type, [])
        all_user_presets[preset_type] = [item for item in bucket if item["id"] != preset_id]
        self.user_preset_file.write_text(json.dumps(all_user_presets, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear_user_presets(self, preset_type: str) -> None:
        all_user_presets = self._read_user_preset_map()
        all_user_presets[preset_type] = []
        self.user_preset_file.write_text(json.dumps(all_user_presets, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_builtin_preset(self, preset_type: str, preset_id: str) -> Preset | None:
        for preset in self.load_builtin_presets(preset_type):
            if preset.id == preset_id:
                return preset
        return None

    def get_user_preset(self, preset_type: str, preset_id: str) -> Preset | None:
        for preset in self.load_user_presets(preset_type):
            if preset.id == preset_id:
                return preset
        return None

    def get_preset(self, preset_type: str, preset_id: str) -> Preset | None:
        return self.get_user_preset(preset_type, preset_id) or self.get_builtin_preset(preset_type, preset_id)

    def _load_preset_file(self, path: Path) -> list[Preset]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        presets: list[Preset] = []
        for item in data:
            try:
                preset, _ = self._to_preset(item, migrate_legacy=False)
                presets.append(preset)
            except (KeyError, TypeError, ValueError):
                continue
        return presets

    def _read_user_preset_map(self) -> dict[str, list[dict[str, Any]]]:
        if not self.user_preset_file.exists():
            return {"video": [], "audio": [], "image": []}
        try:
            loaded = json.loads(self.user_preset_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"video": [], "audio": [], "image": []}
        if not isinstance(loaded, dict):
            return {"video": [], "audio": [], "image": []}
        return {
            "video": loaded.get("video", []),
            "audio": loaded.get("audio", []),
            "image": loaded.get("image", []),
        }

    def _to_preset(self, item: dict[str, Any], migrate_legacy: bool = False) -> tuple[Preset, bool]:
        normalized_item = dict(item)
        migrated = False
        if migrate_legacy and normalized_item.get("type") == "video":
            settings = normalized_item.get("settings")
            if isinstance(settings, dict) and self._is_legacy_audio_language_default(settings):
                settings = dict(settings)
                settings.pop("audio_languages", None)
                normalized_item["settings"] = settings
                migrated = True
        preset = Preset(
            id=normalized_item["id"],
            name=normalized_item["name"],
            type=normalized_item["type"],
            description=normalized_item.get("description", ""),
            output_extension=normalized_item["output_extension"],
            settings=normalized_item.get("settings", {}),
            ffmpeg_args_template=normalized_item.get("ffmpeg_args_template", []),
        )
        validate_preset(preset)
        return preset, migrated

    def _rewrite_migrated_user_presets(self, loaded: dict[str, Any]) -> None:
        normalized: dict[str, list[dict[str, Any]]] = {"video": [], "audio": [], "image": []}
        for preset_type in ("video", "audio", "image"):
            items = loaded.get(preset_type, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    preset, _ = self._to_preset(item, migrate_legacy=True)
                except (KeyError, TypeError, ValueError):
                    continue
                normalized[preset_type].append(self._preset_to_dict(preset))
        self.preset_dir.mkdir(parents=True, exist_ok=True)
        self.user_preset_file.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def _is_legacy_audio_language_default(self, settings: dict[str, Any]) -> bool:
        audio_languages = settings.get("audio_languages")
        if not isinstance(audio_languages, list):
            return False
        normalized = [str(item).strip().lower() for item in audio_languages if str(item).strip()]
        return normalized == ["jpn", "jpn", "eng"]

    def _preset_to_dict(self, preset: Preset) -> dict[str, Any]:
        return {
            "id": preset.id,
            "name": preset.name,
            "type": preset.type,
            "description": preset.description,
            "output_extension": preset.output_extension,
            "settings": preset.settings,
            "ffmpeg_args_template": preset.ffmpeg_args_template,
        }
