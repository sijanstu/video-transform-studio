"""
Video transform engine.

Builds FFmpeg filtergraphs for common creative video edits:
mirroring, picture-in-picture, color grading, micro zoom/shake,
pitch & speed adjustment, frame thinning, and intro title cards.

All transforms are standard, lawful video-editing operations intended
for use on footage you own or are licensed to use (e.g. original
content, fair-use commentary, licensed material).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont


def probe(path: str):
    """Return basic media properties for a video file using ffprobe."""
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)

    width = height = 0
    fps = 30.0
    has_audio = False
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            width = int(s.get("width", width))
            height = int(s.get("height", height))
            fr = s.get("avg_frame_rate", "30/1")
            if "/" in fr:
                num, den = fr.split("/")
                if float(den):
                    fps = float(num) / float(den)
        elif s.get("codec_type") == "audio":
            has_audio = True

    duration = float(data.get("format", {}).get("duration", 0.0))
    return {"width": width, "height": height, "fps": fps,
            "duration": duration, "has_audio": has_audio}


def _num(v, default):
    return default if v is None else float(v)


def _main_video_filter(p: dict, info: dict) -> str:
    """Video filtergraph applied to the source clip (no intro wrapper)."""
    chain: list[str] = []

    if p.get("mirror"):
        chain.append("hflip")

    zoom = _num(p.get("zoom"), 1.0)
    if zoom != 1.0 or p.get("shake"):
        if p.get("shake"):
            chain.append(
                f"crop=iw*(1/{zoom}):ih*(1/{zoom}):"
                f"x='(iw-iw/{zoom})/2+sin(t*1.5)*(iw*0.01)':"
                f"y='(ih-ih/{zoom})/2+cos(t*1.2)*(ih*0.01)'"
            )
        else:
            chain.append(f"crop=iw*(1/{zoom}):ih*(1/{zoom})")
        chain.append(f"scale={info['width']}:{info['height']}")

    eq: list[str] = []
    sat = _num(p.get("color_saturation"), 1.0)
    if sat != 1.0:
        eq.append(f"saturation={sat:.3f}")
    if eq:
        chain.append("eq=" + ":".join(eq))

    hue = _num(p.get("color_hue"), 0.0)
    if hue != 0.0:
        chain.append(f"hue=h={hue:.2f}")

    vig = _num(p.get("vignette"), 0.0)
    if vig > 0:
        a = min(0.5, vig * 0.5)
        chain.append(f"vignette=PI/4:{(1 - a):.3f}")

    speed = _num(p.get("speed"), 1.0)
    if speed != 1.0:
        chain.append(f"setpts={1 / speed:.6f}*PTS")

    skip = int(_num(p.get("frame_skip"), 0))
    if skip > 1:
        chain.append(f"select='not(eq(mod(n\\,{skip}),0))'")
        chain.append("setpts=N/FRAME_RATE/TB")

    return ",".join(chain) if chain else "null"


def _pip_filter(p: dict, info: dict) -> str:
    """Picture-in-picture filtergraph: blurred bg + scaled foreground.

    Self-contained: consumes [0:v], outputs [mv].
    """
    cw = int(p.get("canvas_w") or 1080)
    ch = int(p.get("canvas_h") or 1080)
    fg_w = max(80, int(cw * _num(p.get("pip_scale"), 0.45)))
    base = _main_video_filter({k: v for k, v in p.items()
                               if k not in ("pip", "pip_scale")}, info)
    fg = f"[0:v]{base},scale={fg_w}:-1[fg]"
    bg = (f"[0:v]scale={cw}:{ch}:force_original_aspect_ratio=increase,"
          f"crop={cw}:{ch},gblur=25[bg]")
    ov = f"[bg][fg]overlay=(W-w)/2:(H-h)/2[mv]"
    return f"{fg};{bg};{ov}"


def _atempo_chain(factor: float) -> list[str]:
    """Split an atempo factor into 0.5..2.0 chunks (ffmpeg limit)."""
    out: list[str] = []
    f = factor
    while f > 2.0:
        out.append("atempo=2.0")
        f /= 2.0
    while f < 0.5:
        out.append("atempo=0.5")
        f /= 0.5
    if abs(f - 1.0) > 1e-4:
        out.append(f"atempo={f:.4f}")
    return out


def _audio_filter(p: dict) -> Optional[str]:
    pitch = _num(p.get("pitch"), 1.0)
    speed = _num(p.get("speed"), 1.0)
    if pitch == 1.0 and speed == 1.0:
        return None

    parts: list[str] = []
    if pitch != 1.0:
        # pitch shift via resample, then correct tempo so duration tracks `speed`
        parts.append(f"asetrate=44100*{pitch:.4f}")
        parts.append("aresample=44100")
        parts += _atempo_chain(speed / pitch)
    else:
        parts += _atempo_chain(speed)
    return ",".join(parts)


def build_command(p: dict, src: str, dst: str,
                  limit_seconds: Optional[float] = None) -> list[str]:
    info = probe(src)
    src_has_audio = info["has_audio"]
    ac = _audio_filter(p)
    intro = _num(p.get("intro_seconds"), 0.0)

    # Effective canvas: explicit canvas_w/h, else source size. Used consistently
    # by both the picture-in-picture frame and the intro title card so the
    # concat dimensions always match.
    eff_cw = int(p.get("canvas_w") or info["width"] or 1080)
    eff_ch = int(p.get("canvas_h") or info["height"] or 1080)
    p["canvas_w"] = eff_cw
    p["canvas_h"] = eff_ch

    # Pre-compute the "main" video graph (always outputs label [mv])
    if p.get("pip"):
        main_graph = _pip_filter(p, info)
    else:
        chain = _main_video_filter(p, info)
        main_graph = f"[0:v]{chain}[mv]"

    if intro <= 0:
        fcg = main_graph
        maps = ["[mv]"]
        if src_has_audio and ac:
            fcg += f";[0:a]{ac}[ma]"
            maps.append("[ma]")
        elif src_has_audio:
            maps.append("0:a")
        cmd = ["ffmpeg", "-y", "-i", src, "-filter_complex", fcg]
        for m in maps:
            cmd += ["-map", m]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
        if src_has_audio:
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        else:
            cmd += ["-an"]
        cmd += ["-movflags", "+faststart"]
        if limit_seconds:
            cmd += ["-t", str(limit_seconds)]
        cmd += [dst]
        return cmd

    # --- Intro title card path ---
    cw = int(p.get("canvas_w") or info["width"] or 1080)
    ch = int(p.get("canvas_h") or info["height"] or 1080)
    fps = info["fps"] or 30.0

    card_path = str(Path(dst).with_suffix(".card.png"))
    make_title_card(str(p.get("intro_text", "Your Title")), cw, ch, card_path)

    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-loop", "1", "-framerate", f"{fps}", "-t", f"{intro}", "-i", card_path,
    ]
    fcg = f"{main_graph};[1:v]scale={cw}:{ch}[intv];" \
          f"[intv][mv]concat=n=2:v=1:a=0[vout]"
    maps = ["[vout]"]

    if src_has_audio:
        cmd += ["-f", "lavfi", "-i",
                f"anullsrc=r=44100:cl=stereo:d={intro}"]
        if ac:
            fcg += f";[0:a]{ac}[ma];[2:a][ma]concat=n=2:v=0:a=1[aout]"
        else:
            fcg += f";[2:a][0:a]concat=n=2:v=0:a=1[aout]"
        maps.append("[aout]")

    cmd += ["-filter_complex", fcg]
    for m in maps:
        cmd += ["-map", m]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    if src_has_audio:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart"]
    if limit_seconds:
        cmd += ["-t", str(limit_seconds)]
    cmd += [dst]
    return cmd


def make_title_card(text: str, w: int, h: int, path: str) -> None:
    """Render a centered title card PNG (avoids ffmpeg drawtext dependency)."""
    img = Image.new("RGB", (w, h), (10, 10, 12))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(24, h // 12))
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()

    words = str(text).split()
    lines, cur = [], ""
    for word in words:
        if draw.textlength((cur + " " + word).strip(), font=font) > w * 0.9 and cur:
            lines.append(cur.strip())
            cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur:
        lines.append(cur.strip())
    lines = lines or [str(text)]

    lh = font.getbbox("Ag")[3] + 10
    total = lh * len(lines)
    y = (h - total) // 2
    for line in lines:
        lw = draw.textlength(line, font=font)
        draw.text(((w - lw) / 2, y), line, font=font, fill=(235, 238, 245))
        y += lh
    img.save(path)


def run(cmd: list[str], timeout: int = 900) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(
            "ffmpeg failed:\n" + (res.stderr[-2000:] if res.stderr else "no output")
        )
