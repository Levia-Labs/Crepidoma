"""Screenshot an artifact page with a headless browser, in a forced colour theme.

Usage:
  artifact_shot.py PAGE.html --out PNG [--width 1280] [--height 4000] [--theme light|dark|system]
The browser comes from ARTIFACT_BROWSER, else the usual Edge, Chrome or Chromium location of the
OS. The theme is forced by shooting a temp copy wrapped in `<html data-theme="...">`; the page
itself is untouched.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM_FILES = (
    os.environ.get("PROGRAMFILES", r"C:\Program Files"),
    os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
)
WINDOWS = [
    str(Path(root) / rel)
    for root in PROGRAM_FILES
    for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe")
]
MAC = [
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
LINUX_NAMES = [
    "microsoft-edge",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
]
HEAD = (
    '<!doctype html>\n<html data-theme="{theme}" lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    "</head><body>\n"
)


def find_browser() -> str:
    """Path of a Chromium-family browser; raise FileNotFoundError naming how to point at one."""
    env = os.environ.get("ARTIFACT_BROWSER")
    if env:
        if Path(env).exists() or shutil.which(env):
            return env
        raise FileNotFoundError(f"ARTIFACT_BROWSER={env} does not exist")
    if sys.platform == "win32":
        paths = WINDOWS
    elif sys.platform == "darwin":
        paths = MAC
    else:
        paths = [found for name in LINUX_NAMES if (found := shutil.which(name))]
    for path in paths:
        if Path(path).exists():
            return path
    raise FileNotFoundError(
        "no Edge, Chrome or Chromium found; set ARTIFACT_BROWSER to a browser executable"
    )


def themed(page: str, theme: str) -> str:
    """The page forced into a theme: standalone pages get the attribute, fragments a wrapper."""
    if theme == "system":
        return (
            page
            if re.search(r"<html\b", page, re.I)
            else HEAD.format(theme="system") + page + "\n</body></html>\n"
        )
    if re.search(r"<html\b", page, re.I):
        page = re.sub(r"\sdata-theme=\"[^\"]*\"", "", page, count=1)
        return re.sub(r"<html\b", f'<html data-theme="{theme}"', page, count=1, flags=re.I)
    return HEAD.format(theme=theme) + page + "\n</body></html>\n"


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        head = handle.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    return struct.unpack(">II", head[16:24])


def shoot(page: Path, out: Path, width: int, height: int, theme: str) -> tuple[int, int]:
    browser = find_browser()
    text = themed(page.read_text(encoding="utf-8"), theme)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="artifact-shot-") as tmp:
        copy = Path(tmp) / "page.html"
        copy.write_text(text, encoding="utf-8", newline="\n")
        argv = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--user-data-dir={Path(tmp) / 'profile'}",
            f"--window-size={width},{height}",
            "--virtual-time-budget=4000",
            f"--screenshot={out.resolve()}",
            copy.resolve().as_uri(),
        ]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode != 0 or not out.exists():
        raise RuntimeError(
            f"browser exited {result.returncode}: {(result.stderr or '').strip()[-200:]}"
        )
    return png_size(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="artifact_shot.py", description=__doc__.splitlines()[0])
    parser.add_argument("page", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=4000)
    parser.add_argument("--theme", choices=["light", "dark", "system"], default="light")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    try:
        width, height = shoot(args.page, args.out, args.width, args.height, args.theme)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"artifact shot: {exc}", file=sys.stderr)
        return 1
    print(f"artifact shot: {args.out} {width}x{height} {args.theme}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
