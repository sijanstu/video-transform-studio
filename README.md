# Video Transform Studio

[![Stars](https://img.shields.io/github/stars/sijanstu/video-transform-studio?style=flat)](https://github.com/sijanstu/video-transform-studio/stargazers)
[![Forks](https://img.shields.io/github/forks/sijanstu/video-transform-studio?style=flat)](https://github.com/sijanstu/video-transform-studio/network/members)
[![Issues](https://img.shields.io/github/issues/sijanstu/video-transform-studio)](https://github.com/sijanstu/video-transform-studio/issues)
[![Last Commit](https://img.shields.io/github/last-commit/sijanstu/video-transform-studio)](https://github.com/sijanstu/video-transform-studio/commits/main)
[![Repo Size](https://img.shields.io/github/repo-size/sijanstu/video-transform-studio)](https://github.com/sijanstu/video-transform-studio)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)

A small Python + FFmpeg web app for applying creative video edits — mirroring,
picture-in-picture, color grading, micro zoom/shake, pitch & speed changes,
frame thinning, and intro title cards — with a live in-browser preview.

> **Use it on footage you own or are licensed to use** (original content,
> licensed material, or fair-use commentary). It is a video-editing tool, not a
> copyright-circumvention utility.

## Requirements

- Python 3.10+
- FFmpeg (`ffmpeg` and `ffprobe` on your `PATH`)
- Python packages: `flask`, `pillow`

```bash
brew install ffmpeg            # macOS (or apt/yum/winget equivalent)
python3 -m pip install flask pillow
```

> Note: some FFmpeg builds omit the `rubberband` and `drawtext` filters. This
> project does not rely on them — pitch uses `asetrate`/`aresample`/`atempo` and
> title cards are rendered to a PNG via Pillow.

## Run

```bash
python3 app.py
```

Open http://127.0.0.1:5000, upload a video, adjust the controls, then:

- **Preview (8s)** — renders only the first 8 seconds for a fast look.
- **Export** — renders the full clip and offers a download.

Uploaded files live in `uploads/`, rendered output in `outputs/`.

## Available transforms

| Group   | Control            | Effect                                              |
|---------|--------------------|-----------------------------------------------------|
| Visual  | Mirror             | Horizontal flip                                     |
| Visual  | Picture-in-Picture | Foreground clip over a blurred, scaled-up copy      |
| Visual  | PiP size           | Foreground scale (fraction of canvas)               |
| Visual  | Saturation         | Color intensity                                     |
| Visual  | Hue shift          | Tint rotation (degrees)                             |
| Visual  | Vignette           | Darkened edges                                      |
| Visual  | Zoom               | Micro zoom-in (crops edges, scales back)            |
| Visual  | Shake              | Gentle sinusoidal camera motion                     |
| Audio   | Pitch              | Pitch shift via resampling (preserves duration)     |
| Audio   | Speed              | Playback speed (video + audio stay in sync)         |
| Struct. | Frame skip         | Drops every Nth frame                              |
| Struct. | Intro card         | Prepends a generated title card of N seconds        |

Canvas size (used by PiP and the intro card) defaults to the source resolution;
override it with `canvas_w` / `canvas_h` if you want a square or vertical frame
(e.g. 1080×1080 for Reels).

## Project layout

```
app.py            Flask server: /upload, /render, /output
ffmpeg_utils.py   Filtergraph builder + ffprobe media probe
templates/
  index.html      Web UI with controls and live preview
uploads/          Uploaded source videos (git-ignored)
outputs/          Rendered previews/exports (git-ignored)
```

## Library usage

You can also call the engine directly:

```python
import ffmpeg_utils as fx

params = {"mirror": True, "pitch": 1.03, "speed": 1.05, "intro_seconds": 3}
cmd = fx.build_command(params, "input.mp4", "out.mp4", limit_seconds=8)
fx.run(cmd)
```

`build_command` returns an `ffmpeg` argument list; pass `limit_seconds` for a
short preview, omit it for a full export.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=sijanstu/video-transform-studio&type=Date)](https://star-history.com/#sijanstu/video-transform-studio&Date)
