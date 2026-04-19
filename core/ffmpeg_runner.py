"""FFmpeg process execution helpers."""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable


def run_ffmpeg(
    command: list[str],
    on_line: Callable[[str], None] | None = None,
    stop_event: threading.Event | None = None,
) -> tuple[int, int | None]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    watcher: threading.Thread | None = None
    if stop_event is not None:
        watcher = threading.Thread(target=_watch_stop_signal, args=(process, stop_event), daemon=True)
        watcher.start()

    assert process.stdout is not None
    for line in process.stdout:
        cleaned = line.rstrip()
        if _should_suppress_log_line(cleaned):
            continue
        if on_line:
            on_line(cleaned)
        if stop_event and stop_event.is_set():
            _terminate_process(process)
            break

    return_code = process.wait()
    if watcher is not None:
        watcher.join(timeout=0.1)
    return return_code, process.pid


def _watch_stop_signal(process: subprocess.Popen[str], stop_event: threading.Event) -> None:
    stop_event.wait()
    _terminate_process(process)


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if hasattr(process, "terminate"):
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if hasattr(process, "kill"):
            process.kill()


def _should_suppress_log_line(line: str) -> bool:
    normalized = line.lower()
    return (
        "[image2 @" in normalized
        and "use a pattern such as" in normalized
        and "write a single image" in normalized
    )
