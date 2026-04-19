# htmlmpeg

Local FFmpeg compressor for video, audio, and image files.

![Application preview](assets/readme-preview.png)

## Why this exists

FFmpeg is powerful, but its command-line workflow is often too technical for everyday use. This project wraps common compression tasks in a browser UI with presets, local file handling, and persistent settings so the tool stays practical on Windows.

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

Download from:

- https://github.com/ponta0365/htmlmpeg/releases/tag/exe-latest

Published assets:

- `FFMPEG.exe`
- `FFMPEG.zip`

How to use the release:

1. Open the release page
2. Download `FFMPEG.zip` if you want the packaged file, or `FFMPEG.exe` directly
3. Extract the zip if needed
4. Run the EXE on Windows

To rebuild locally, run:

```powershell
.\build_exe.ps1
```

To publish a GitHub Release with `gh`, run:

```powershell
.\publish_release.ps1
```

## Acknowledgments

This project uses FFmpeg and related libraries and tools provided by their respective authors and maintainers. I would like to express my gratitude to everyone who created and maintains the libraries and EXE-related tools used here.

This application was developed with the assistance of AI, and the source code and release workflow were prepared and published with AI support. The project is intended to be used transparently so that there is no misunderstanding about how it was created.
