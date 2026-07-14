#!/usr/bin/env python3
"""Generate self-hosted shields-style SVG badges from the GitHub API.

Writes one SVG per badge into ``badges/`` so the README has no external image
dependencies. Re-run (optionally with GITHUB_TOKEN) to refresh the numbers.

Usage:
    python3 scripts/badges.py
    GITHUB_TOKEN=xxx python3 scripts/badges.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = "sijanstu/video-transform-studio"
BADGES = Path(__file__).resolve().parent.parent / "badges"
BADGES.mkdir(exist_ok=True)


def gh_repo() -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    cmd = ["curl", "-s", "-L", "-A", "Mozilla/5.0",
           f"https://api.github.com/repos/{REPO}"]
    if token:
        cmd[4:4] = ["-H", f"Authorization: Bearer {token}"]
    try:
        return json.loads(subprocess.run(cmd, capture_output=True,
                         text=True, timeout=30).stdout or "{}")
    except Exception:  # noqa: BLE001
        return {}


def make_badge(label: str, value: str, color: str) -> str:
    """Render a flat shields-style badge as an SVG string."""
    def esc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;"))
    # approximate text width: 7px per char + padding
    lw = max(40, len(label) * 7 + 14)
    vw = max(34, len(value) * 7 + 14)
    w = lw + vw
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" '
        f'viewBox="0 0 {w} 20" font-family="system-ui,Segoe UI,Roboto,sans-serif" '
        f'font-size="12">'
        f'<rect width="{lw}" height="20" rx="3" fill="#2a2f3a"/>'
        f'<rect x="{lw}" width="{vw}" height="20" rx="3" fill="{color}"/>'
        f'<rect width="{w}" height="20" rx="3" fill="none"/>'
        f'<text x="{lw/2:.0f}" y="14" fill="#cdd3de" text-anchor="middle">'
        f'{esc(label)}</text>'
        f'<text x="{lw + vw/2:.0f}" y="14" fill="#ffffff" text-anchor="middle">'
        f'{esc(value)}</text>'
        f'</svg>'
    )


def write(name: str, svg: str) -> None:
    (BADGES / f"{name}.svg").write_text(svg)


def main() -> int:
    d = gh_repo()
    stars = d.get("stargazers_count", 0)
    forks = d.get("forks_count", 0)
    issues = d.get("open_issues_count", 0)
    size_kb = d.get("size", 0)
    pushed = d.get("pushed_at", "")[:10]

    write("stars", make_badge("stars", str(stars), "#5b8cff"))
    write("forks", make_badge("forks", str(forks), "#7c8cff"))
    write("issues", make_badge("issues", str(issues), "#ff9f43"))
    write("last-commit", make_badge("last commit", pushed or "—", "#3fb950"))
    size = f"{size_kb//1024} MB" if size_kb >= 1024 else f"{size_kb} KB"
    write("size", make_badge("repo size", size, "#8b949e"))
    write("python", make_badge("python", "3.10+", "#3776ab"))

    print(f"wrote {len(os.listdir(BADGES))} badges to {BADGES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
