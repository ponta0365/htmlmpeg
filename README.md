# htmlmpeg

Local FFmpeg compressor for video, audio, and image files.

This project provides:

- a browser-based UI
- a Python backend
- FFmpeg/FFprobe subprocess execution
- preset-based compression workflows

## Run

1. Install Python dependencies from `requirements.txt`
2. Make sure `ffmpeg.exe` and `ffprobe.exe` are available
3. Start the app with `start.ps1` or `python app.py`

## Notes

- Built-in presets live in `presets/`
- User presets and runtime logs are treated as local data
- `temp/`, `dist/`, `build/`, and generated logs are not tracked

## EXE Release

The repository includes a GitHub Actions workflow that builds the Windows EXE and publishes it as a release asset when a `release/**` branch is pushed.

Current release branch:

- `release/exe-latest`

The published asset is:

- `dist/ブラウザFFMPEG.exe`

To rebuild locally, run:

```powershell
.\build_exe.ps1
```
