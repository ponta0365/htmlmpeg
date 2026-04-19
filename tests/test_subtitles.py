from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from app import create_app
from core.command_builder import build_ffmpeg_command
from core.ffprobe_reader import classify_subtitle_codec
from core.models import Preset


def _ffmpeg_executable() -> str:
    return shutil.which("ffmpeg") or ""


def _ffprobe_executable() -> str:
    return shutil.which("ffprobe") or ""


@unittest.skipUnless(_ffmpeg_executable() and _ffprobe_executable(), "ffmpeg/ffprobe is required")
class SubtitleHandlingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.root = Path(self.tmpdir.name)
        self.ffmpeg = _ffmpeg_executable()
        self.ffprobe = _ffprobe_executable()

    def _run(self, command: list[str]) -> None:
        subprocess.run(command, check=True, capture_output=True, text=True)

    def _create_text_subtitle_sample(self) -> Path:
        base_video = self.root / "base.mp4"
        subtitle_file = self.root / "subtitle.srt"
        subtitle_video = self.root / "subtitle_sample.mkv"

        subtitle_file.write_text(
            "\n".join(
                [
                    "1",
                    "00:00:00,000 --> 00:00:00,800",
                    "Hello subtitle",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        self._run(
            [
                self.ffmpeg,
                "-hide_banner",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=128x128:rate=10:duration=1",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(base_video),
            ]
        )
        self._run(
            [
                self.ffmpeg,
                "-hide_banner",
                "-y",
                "-i",
                str(base_video),
                "-i",
                str(subtitle_file),
                "-c",
                "copy",
                "-c:s",
                "srt",
                str(subtitle_video),
            ]
        )
        return subtitle_video

    def test_classify_subtitle_codec(self) -> None:
        self.assertEqual(classify_subtitle_codec("ass"), "text")
        self.assertEqual(classify_subtitle_codec("subrip"), "text")
        self.assertEqual(classify_subtitle_codec("hdmv_pgs_subtitle"), "image")
        self.assertEqual(classify_subtitle_codec("pgs"), "image")
        self.assertEqual(classify_subtitle_codec("unknown_codec"), "other")

    def test_probe_reports_text_subtitles(self) -> None:
        subtitle_video = self._create_text_subtitle_sample()
        app = create_app()
        client = app.test_client()

        response = client.post("/api/probe", json={"path": str(subtitle_video)})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        media_info = payload["media_info"]
        self.assertEqual(media_info["subtitle_stream_count"], 1)
        self.assertEqual(media_info["subtitle_text_stream_count"], 1)
        self.assertEqual(media_info["subtitle_image_stream_count"], 0)

    def test_build_command_uses_mov_text_for_mp4_text_subtitles(self) -> None:
        preset = Preset(
            id="test_mp4",
            name="test",
            type="video",
            description="test",
            output_extension=".mp4",
            settings={
                "video_codec": "libx264",
                "audio_codec": "aac",
                "subtitle_mode": "text",
            },
            ffmpeg_args_template=[
                "-c:v",
                "{video_codec}",
                "-c:a",
                "{audio_codec}",
            ],
        )

        command = build_ffmpeg_command(
            self.ffmpeg,
            str(self.root / "input.mkv"),
            str(self.root / "output.mp4"),
            preset,
            overwrite=True,
            media_info={"streams": [{"codec_type": "subtitle", "codec_name": "subrip"}]},
        )

        self.assertIn("-c:s", command)
        self.assertIn("mov_text", command)

    def test_build_command_text_mode_skips_image_subtitles(self) -> None:
        preset = Preset(
            id="test_mp4",
            name="test",
            type="video",
            description="test",
            output_extension=".mp4",
            settings={
                "video_codec": "libx264",
                "audio_codec": "aac",
                "subtitle_mode": "text",
            },
            ffmpeg_args_template=[
                "-c:v",
                "{video_codec}",
                "-c:a",
                "{audio_codec}",
            ],
        )

        command = build_ffmpeg_command(
            self.ffmpeg,
            str(self.root / "input.mkv"),
            str(self.root / "output.mp4"),
            preset,
            overwrite=True,
            media_info={
                "streams": [
                    {"codec_type": "subtitle", "codec_name": "subrip"},
                    {"codec_type": "subtitle", "codec_name": "hdmv_pgs_subtitle"},
                ]
            },
        )

        self.assertIn("0:0?", command)
        self.assertNotIn("0:1?", command)
        self.assertIn("mov_text", command)

    def test_build_command_uses_source_audio_languages(self) -> None:
        preset = Preset(
            id="test_mp4",
            name="test",
            type="video",
            description="test",
            output_extension=".mp4",
            settings={
                "video_codec": "libx264",
                "audio_codec": "aac",
                "subtitle_mode": "hidden",
            },
            ffmpeg_args_template=[
                "-c:v",
                "{video_codec}",
                "-c:a",
                "{audio_codec}",
            ],
        )

        command = build_ffmpeg_command(
            self.ffmpeg,
            str(self.root / "input.mkv"),
            str(self.root / "output.mp4"),
            preset,
            overwrite=True,
            media_info={
                "streams": [
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "eng"}},
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "jpn"}},
                ]
            },
        )

        self.assertIn("-metadata:s:a:0", command)
        first_language_index = command.index("language=eng")
        self.assertGreaterEqual(first_language_index, 0)
        self.assertIn("language=jpn", command)

    def test_build_command_prefers_japanese_default_audio_track(self) -> None:
        preset = Preset(
            id="test_mp4",
            name="test",
            type="video",
            description="test",
            output_extension=".mp4",
            settings={
                "video_codec": "libx264",
                "audio_codec": "aac",
                "subtitle_mode": "hidden",
            },
            ffmpeg_args_template=[
                "-c:v",
                "{video_codec}",
                "-c:a",
                "{audio_codec}",
            ],
        )

        command = build_ffmpeg_command(
            self.ffmpeg,
            str(self.root / "input.mkv"),
            str(self.root / "output.mp4"),
            preset,
            overwrite=True,
            media_info={
                "streams": [
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "eng"}},
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "jpn"}},
                ]
            },
        )

        disposition_target = command[command.index("-disposition:a:1") + 1]
        self.assertEqual(disposition_target, "default")

    def test_build_command_keeps_japanese_only_audio_tracks(self) -> None:
        preset = Preset(
            id="test_mp4",
            name="test",
            type="video",
            description="test",
            output_extension=".mp4",
            settings={
                "video_codec": "libx264",
                "audio_codec": "aac",
                "subtitle_mode": "hidden",
                "audio_stream_mode": "japanese_only",
            },
            ffmpeg_args_template=[
                "-c:v",
                "{video_codec}",
                "-c:a",
                "{audio_codec}",
            ],
        )

        command = build_ffmpeg_command(
            self.ffmpeg,
            str(self.root / "input.mkv"),
            str(self.root / "output.mp4"),
            preset,
            overwrite=True,
            media_info={
                "streams": [
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "eng"}},
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "jpn"}},
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "jpn"}},
                ]
            },
        )

        self.assertIn("-map", command)
        self.assertIn("0:a:1?", command)
        self.assertIn("0:a:2?", command)
        self.assertNotIn("0:a:0?", command)

    def test_build_command_falls_back_to_all_tracks_when_japanese_missing(self) -> None:
        preset = Preset(
            id="test_mp4",
            name="test",
            type="video",
            description="test",
            output_extension=".mp4",
            settings={
                "video_codec": "libx264",
                "audio_codec": "aac",
                "subtitle_mode": "hidden",
                "audio_stream_mode": "japanese_only",
            },
            ffmpeg_args_template=[
                "-c:v",
                "{video_codec}",
                "-c:a",
                "{audio_codec}",
            ],
        )

        command = build_ffmpeg_command(
            self.ffmpeg,
            str(self.root / "input.mkv"),
            str(self.root / "output.mp4"),
            preset,
            overwrite=True,
            media_info={
                "streams": [
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "eng"}},
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "deu"}},
                ]
            },
        )

        self.assertIn("0:a:0?", command)
        self.assertIn("0:a:1?", command)

    def test_build_command_keeps_only_first_japanese_audio_track(self) -> None:
        preset = Preset(
            id="test_mp4",
            name="test",
            type="video",
            description="test",
            output_extension=".mp4",
            settings={
                "video_codec": "libx264",
                "audio_codec": "aac",
                "subtitle_mode": "hidden",
                "audio_stream_mode": "japanese_only_first",
            },
            ffmpeg_args_template=[
                "-c:v",
                "{video_codec}",
                "-c:a",
                "{audio_codec}",
            ],
        )

        command = build_ffmpeg_command(
            self.ffmpeg,
            str(self.root / "input.mkv"),
            str(self.root / "output.mp4"),
            preset,
            overwrite=True,
            media_info={
                "streams": [
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "eng"}},
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "jpn"}},
                    {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "jpn"}},
                ]
            },
        )

        self.assertIn("0:a:1?", command)
        self.assertNotIn("0:a:2?", command)
        self.assertNotIn("0:a:0?", command)

    def test_build_command_rejects_image_subtitles_for_mp4(self) -> None:
        preset = Preset(
            id="test_mp4",
            name="test",
            type="video",
            description="test",
            output_extension=".mp4",
            settings={
                "video_codec": "libx264",
                "audio_codec": "aac",
                "subtitle_mode": "copy",
            },
            ffmpeg_args_template=[
                "-c:v",
                "{video_codec}",
                "-c:a",
                "{audio_codec}",
            ],
        )

        with self.assertRaises(ValueError):
            build_ffmpeg_command(
                self.ffmpeg,
                str(self.root / "input.mkv"),
                str(self.root / "output.mp4"),
                preset,
                overwrite=True,
                media_info={"streams": [{"codec_type": "subtitle", "codec_name": "hdmv_pgs_subtitle"}]},
            )

    def test_text_subtitle_mkv_job_runs(self) -> None:
        subtitle_video = self._create_text_subtitle_sample()
        app = create_app()
        client = app.test_client()
        output_dir = self.root / "out"
        output_dir.mkdir(parents=True, exist_ok=True)

        response = client.post(
            "/api/start",
            json={
                "type": "video",
                "input_mode": "file",
                "input_path": str(subtitle_video),
                "output_path": str(output_dir),
                "keep_folder_structure": False,
                "overwrite": True,
                "preset_id": "video_mp4_light_720p",
            },
        )
        self.assertEqual(response.status_code, 200)
        job_id = response.get_json()["job_id"]

        deadline = time.time() + 60
        status = None
        while time.time() < deadline:
            status_response = client.get("/api/status", query_string={"job_id": job_id})
            if status_response.status_code == 200:
                status = status_response.get_json()
                if status["state"] in {"completed", "failed", "stopped"}:
                    break
            time.sleep(0.2)

        self.assertIsNotNone(status)
        self.assertEqual(status["state"], "completed")
        self.assertEqual(status["completed_count"], 1)
        self.assertEqual(status["failed_count"], 0)


if __name__ == "__main__":
    unittest.main()
