"""Processing history persistence."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HistoryManager:
    def __init__(self, history_file: str | Path) -> None:
        self.history_file = Path(history_file)
        self._lock = threading.Lock()

    def list_history(self, limit: int = 50, state: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if not self.history_file.exists():
                return []
            try:
                data = json.loads(self.history_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return []
            if not isinstance(data, list):
                return []
            items = [item for item in data if isinstance(item, dict)]
            if state and state != "all":
                items = [item for item in items if item.get("state") == state]
            return list(reversed(items[-limit:]))

    def append_entry(self, entry: dict[str, Any]) -> None:
        with self._lock:
            items = []
            if self.history_file.exists():
                try:
                    loaded = json.loads(self.history_file.read_text(encoding="utf-8"))
                    if isinstance(loaded, list):
                        items = [item for item in loaded if isinstance(item, dict)]
                except json.JSONDecodeError:
                    items = []
            items.append({**entry, "recorded_at": datetime.now(timezone.utc).isoformat()})
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            self.history_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
