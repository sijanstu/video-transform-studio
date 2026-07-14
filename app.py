"""Web server: upload a video, preview applied transforms, export result."""

import json
import shutil
import subprocess
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_file, render_template
import ffmpeg_utils as fx

BASE = Path(__file__).parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
for d in (UPLOADS, OUTPUTS):
    d.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB


def _params_from(data: dict) -> dict:
    def f(k, default=0.0):
        try:
            return float(data.get(k, default))
        except (TypeError, ValueError):
            return default

    def b(k):
        v = data.get(k)
        return str(v).lower() in ("1", "true", "on", "yes")

    return {
        "mirror": b("mirror"),
        "pip": b("pip"),
        "pip_scale": f("pip_scale", 0.45),
        "color_saturation": f("color_saturation", 1.0),
        "color_hue": f("color_hue", 0.0),
        "vignette": f("vignette", 0.0),
        "zoom": f("zoom", 1.0),
        "shake": b("shake"),
        "pitch": f("pitch", 1.0),
        "speed": f("speed", 1.0),
        "frame_skip": int(f("frame_skip", 0)),
        "intro_seconds": f("intro_seconds", 0.0),
        "intro_text": data.get("intro_text", "Your Title"),
        "canvas_w": int(f("canvas_w", 0)),
        "canvas_h": int(f("canvas_h", 0)),
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        return jsonify(error="no file"), 400
    ext = Path(file.filename or "video.mp4").suffix or ".mp4"
    vid_id = uuid.uuid4().hex
    path = UPLOADS / f"{vid_id}{ext}"
    file.save(path)
    try:
        info = fx.probe(str(path))
    except Exception as e:  # noqa: BLE001
        path.unlink(missing_ok=True)
        return jsonify(error=f"cannot read video: {e}"), 400
    return jsonify(id=vid_id, ext=ext, info=info)


@app.route("/render", methods=["POST"])
def render():
    body = request.get_json(force=True, silent=True) or {}
    vid_id = body.get("id")
    mode = body.get("mode", "preview")  # preview | export
    if not vid_id:
        return jsonify(error="missing id"), 400

    src = next((p for p in UPLOADS.glob(f"{vid_id}.*") if p.is_file()), None)
    if not src:
        return jsonify(error="video not found"), 404

    params = _params_from(body.get("params", {}))
    out_name = f"{vid_id}_{mode}.mp4"
    dst = OUTPUTS / out_name

    limit = 8.0 if mode == "preview" else None
    try:
        cmd = fx.build_command(params, str(src), str(dst), limit_seconds=limit)
        fx.run(cmd, timeout=900 if mode == "export" else 120)
    except Exception as e:  # noqa: BLE001
        return jsonify(error=str(e)), 500

    return jsonify(url=f"/output/{out_name}", mode=mode)


@app.route("/output/<name>")
def output(name):
    # prevent path traversal
    safe = OUTPUTS / Path(name).name
    if not safe.exists():
        return jsonify(error="not ready"), 404
    return send_file(safe, mimetype="video/mp4")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
