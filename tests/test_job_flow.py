from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from core.command_builder import build_ffmpeg_command
from core.models import Preset


class CommandBuilderTemplateTests(unittest.TestCase):
    def test_missing_template_variable_raises_value_error(self) -> None:
        preset = Preset(
            id="broken",
            name="broken",
            type="video",
            description="broken",
            output_extension=".mp4",
            settings={
                "video_codec": "libx264",
                "audio_codec": "aac",
            },
            ffmpeg_args_template=[
                "-c:v",
                "{video_codec}",
                "-profile:v",
                "{missing_profile}",
            ],
        )

        with self.assertRaises(ValueError):
            build_ffmpeg_command(
                "ffmpeg",
                "input.mp4",
                "output.mp4",
                preset,
                overwrite=False,
            )


class JobFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.root = Path(self.tmpdir.name)

    def _wait_for_terminal_state(self, client, job_id: str, timeout_seconds: float = 5.0) -> dict:
        deadline = time.time() + timeout_seconds
        status = {}
        while time.time() < deadline:
            response = client.get("/api/status", query_string={"job_id": job_id})
            self.assertEqual(response.status_code, 200)
            status = response.get_json()
            if status["state"] in {"completed", "failed", "stopped"}:
                return status
            time.sleep(0.05)
        self.fail(f"job {job_id} did not reach a terminal state: {status}")

    def test_mixed_result_batch_finishes_completed(self) -> None:
        input_dir = self.root / "input"
        output_dir = self.root / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        (input_dir / "a.mp4").write_bytes(b"a")
        (input_dir / "b.mp4").write_bytes(b"b")

        app = create_app()
        client = app.test_client()

        run_results = iter([(1, 101), (0, 102)])

        def fake_run_ffmpeg(*args, **kwargs):
            return next(run_results)

        with (
            patch("app._get_available_encoders", return_value={"libx264", "aac"}),
            patch("app.read_media_info", return_value={}),
            patch("app.summarize_media_info", return_value={}),
            patch("app.build_ffmpeg_command", return_value=["ffmpeg"]),
            patch("app.run_ffmpeg", side_effect=fake_run_ffmpeg),
        ):
            response = client.post(
                "/api/start",
                json={
                    "type": "video",
                    "input_mode": "folder",
                    "input_path": str(input_dir),
                    "include_subfolders": False,
                    "output_path": str(output_dir),
                    "keep_folder_structure": False,
                    "overwrite": False,
                    "preset_id": "video_mp4_light_720p",
                },
            )

            self.assertEqual(response.status_code, 200)
            job_id = response.get_json()["job_id"]
            status = self._wait_for_terminal_state(client, job_id)

        self.assertEqual(status["state"], "completed")
        self.assertEqual(status["completed_count"], 1)
        self.assertEqual(status["failed_count"], 1)


if __name__ == "__main__":
    unittest.main()
