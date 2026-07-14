#!/usr/bin/env python3
"""Generate a self-hosted star-history SVG chart from the GitHub API.

Fetches stargazer timestamps and renders ``star_history.svg`` in the repo root.
Because the image is committed, it always renders in the README without relying
on a third-party chart service. Re-run this (e.g. on a schedule) to refresh it
as stars come in.

Usage:
    python3 scripts/star_chart.py
    GITHUB_TOKEN=xxx python3 scripts/star_chart.py   # higher rate limit
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = "sijanstu/video-transform-studio"
OUT = Path(__file__).resolve().parent.parent / "star_history.svg"

W, H = 720, 240
PAD_L, PAD_R, PAD_T, PAD_B = 48, 16, 16, 28


def fetch_stars() -> list[datetime]:
    """Return sorted list of stargazer timestamps (empty if none)."""
    token = os.environ.get("GITHUB_TOKEN")
    cmd = [
        "curl", "-s", "-L", "-A", "Mozilla/5.0",
        "-H", "Accept: application/vnd.github.star+json",
        f"https://api.github.com/repos/{REPO}/stargazers?per_page=100",
    ]
    if token:
        cmd[4:4] = ["-H", f"Authorization: Bearer {token}"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
        data = json.loads(out) if out.strip() else []
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(data, list):
        return []
    times = []
    for item in data:
        starred = item.get("starred_at") if isinstance(item, dict) else None
        if starred:
            try:
                times.append(datetime.fromisoformat(starred.replace("Z", "+00:00")))
            except ValueError:
                continue
    return sorted(times)


def build_svg(times: list[datetime]) -> str:
    now = datetime.now(timezone.utc)
    if times:
        start = times[0]
    else:
        start = now
    span = max((now - start).total_seconds(), 1.0)

    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    total = len(times)

    def x(t: datetime) -> float:
        return PAD_L + ((t - start).total_seconds() / span) * plot_w

    def y(n: int) -> float:
        if total <= 1:
            return PAD_T + plot_h
        return PAD_T + plot_h - (n / total) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="system-ui,Segoe UI,Roboto,sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#0d1117"/>',
        f'<text x="{PAD_L}" y="14" fill="#9aa3b2" font-size="12">'
        f'Star history — {REPO}</text>',
    ]

    # axes
    parts.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" '
                 f'y2="{PAD_T + plot_h}" stroke="#2a2f3a"/>')
    parts.append(f'<line x1="{PAD_L}" y1="{PAD_T + plot_h}" '
                 f'x2="{W - PAD_R}" y2="{PAD_T + plot_h}" stroke="#2a2f3a"/>')

    if total == 0:
        parts.append(
            f'<text x="{W/2}" y="{PAD_T + plot_h/2}" fill="#6b7280" '
            f'font-size="14" text-anchor="middle">No stars yet — chart will '
            f'populate as they arrive.</text>')
    else:
        # build area + line path
        pts = [(x(t), y(i + 1)) for i, t in enumerate(times)]
        line = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        area = (f"M {PAD_L:.1f},{PAD_T + plot_h:.1f} "
                + " L ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
                + f" L {pts[-1][0]:.1f},{PAD_T + plot_h:.1f} Z")
        parts.append(f'<path d="{area}" fill="#5b8cff" fill-opacity="0.18"/>')
        parts.append(f'<path d="{line}" fill="none" stroke="#5b8cff" '
                     f'stroke-width="2"/>')
        # last point dot + label
        lx, ly = pts[-1]
        parts.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="#5b8cff"/>')
        parts.append(
            f'<text x="{lx:.1f}" y="{ly - 8:.1f}" fill="#e7e9ee" '
            f'font-size="12" text-anchor="end">{total} ★</text>')

    # x-axis labels
    parts.append(f'<text x="{PAD_L}" y="{H - 8}" fill="#6b7280" font-size="11">'
                 f'{start.date()}</text>')
    parts.append(f'<text x="{W - PAD_R}" y="{H - 8}" fill="#6b7280" '
                 f'font-size="11" text-anchor="end">{now.date()}</text>')
    parts.append('</svg>')
    return "\n".join(parts)


def main() -> int:
    times = fetch_stars()
    OUT.write_text(build_svg(times))
    print(f"wrote {OUT} ({len(times)} stars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
