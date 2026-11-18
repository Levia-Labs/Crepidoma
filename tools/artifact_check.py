"""Lint claude.ai artifact HTML pages against the publish rules.

Usage:
  artifact_check.py FILE [FILE ...]

Prints one line per finding as `path:line: severity rule: message` (at most 40, then `... N more`),
then a summary line. Exit 1 when any finding is an error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from artifact_check_css import (
    FLAGS,
    Finding,
    Rule,
    blank,
    check_colours,
    check_tokens,
    line_of,
    parse_css,
)

MAX_LINES = 40
MAX_BYTES = 16 * 1024 * 1024
SCRIPT_HOSTS = (
    "https://cdnjs.cloudflare.com/",
    "https://cdn.jsdelivr.net/npm/",
    "https://unpkg.com/",
    "https://cdn.tailwindcss.com",
    "https://code.jquery.com/",
)
STYLE_HOST = "https://fonts.googleapis.com/"
EXPLAINERS = (" - ", f" {chr(0x2013)} ", f" {chr(0x2014)} ", ": ")
STORAGE = re.compile(r"\b(?:localStorage|sessionStorage|indexedDB)\b")
CALLS = re.compile(r"(?<![\w.$])(?:alert|confirm|prompt)\s*\(|(?<![\w$])window\.print\s*\(")
SCRIPT_BODY = re.compile(r"<script\b(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script>", FLAGS)
JSON_TYPE = re.compile(r"""\btype\s*=\s*["']?[\w/.+-]*json""", re.I)
BLOCKED_TAGS = (
    (re.compile(r"<iframe\b", re.I), "<iframe> is blocked"),
    (re.compile(r"<object\b", re.I), "<object> is blocked"),
    (re.compile(r"<embed\b", re.I), "<embed> is blocked"),
    (re.compile(r"<a\b[^>]*\sdownload\b", FLAGS), "<a download> is blocked"),
    (re.compile(r"<form\b[^>]*\baction\s*=", FLAGS), "form action is blocked"),
)


def check_title(html: str, out: list[Finding]) -> None:
    m = re.search(r"<title[^>]*>(.*?)</title>", html[:8192], FLAGS)
    if not m:
        out.append(Finding(1, "title", "error", "no <title> in the first 8 KB"))
        return
    title, line = m.group(1).strip(), line_of(html, m.start())
    if any(s in title for s in EXPLAINERS):
        out.append(Finding(line, "title", "error", "title carries an explainer"))
    elif len(title.split()) > 5:
        out.append(Finding(line, "title", "warning", "title above 5 words"))


def check_hosts(html: str, out: list[Finding]) -> None:
    for m in re.finditer(r"<script\b[^>]*?\bsrc\s*=\s*[\"']([^\"']*)", html, FLAGS):
        url, line = m.group(1), line_of(html, m.start())
        if not url.startswith(SCRIPT_HOSTS):
            out.append(Finding(line, "script-host", "error", f"script host not allowed: {url}"))
        elif "@latest" in url or not (
            url.startswith("https://cdn.tailwindcss.com") or re.search(r"\d+\.\d+\.\d+", url)
        ):
            out.append(Finding(line, "script-pin", "error", f"no exact x.y.z version: {url}"))
    for m in re.finditer(r"<link\b[^>]*>", html, FLAGS):
        tag = m.group()
        href = re.search(r"\bhref\s*=\s*[\"']([^\"']*)", tag, FLAGS)
        if re.search(r"\brel\s*=\s*[\"']?stylesheet", tag, FLAGS) and not (
            href and href.group(1).startswith(STYLE_HOST)
        ):
            out.append(
                Finding(
                    line_of(html, m.start()),
                    "stylesheet-host",
                    "error",
                    "stylesheet host not allowed",
                )
            )
    for m in re.finditer(r"@import\s+(?:url\()?\s*[\"']?(\S+?)[\"')\s;]", html, FLAGS):
        if not m.group(1).startswith(STYLE_HOST):
            out.append(
                Finding(
                    line_of(html, m.start()),
                    "stylesheet-host",
                    "error",
                    f"@import host not allowed: {m.group(1)}",
                )
            )


def check_body_and_gutter(html: str, rules: list[Rule], out: list[Finding]) -> None:
    bg = re.compile(r"(?<![\w-])background(?:-color)?\s*:")
    ok = any(
        "body" in [s.strip() for s in r.selector.split(",")]
        and any(bg.search(d) for d, _ in r.decls)
        for r in rules
    ) or re.search(r"<body\b[^>]*style\s*=\s*\"[^\"]*background", html, FLAGS)
    if not ok:
        out.append(Finding(1, "body-background", "error", "no body rule sets background"))
    meta = re.search(r"<meta\b[^>]*claude:viewport-fit-sides[^>]*cover", html, FLAGS)
    if meta:
        missing = [
            side
            for side in ("left", "right")
            if not any(
                int(m.group(1)) >= 16
                for m in re.finditer(rf"max\(\s*(\d+)px\s*,\s*env\(safe-area-inset-{side}", html)
            )
        ]
        if missing:
            out.append(
                Finding(
                    line_of(html, meta.start()),
                    "side-gutter",
                    "error",
                    f"missing max(16px, env(safe-area-inset-...)) padding: {', '.join(missing)}",
                )
            )


def check_scripts(html: str, out: list[Finding]) -> None:
    for pattern, msg in BLOCKED_TAGS:
        for m in pattern.finditer(html):
            out.append(Finding(line_of(html, m.start()), "blocked-api", "error", msg))
    for sm in SCRIPT_BODY.finditer(html):
        if JSON_TYPE.search(sm.group(0).split(">", 1)[0]):
            continue
        body, base = sm.group(1), sm.start(1)
        for m in CALLS.finditer(body):
            out.append(
                Finding(
                    line_of(html, base + m.start()),
                    "blocked-api",
                    "error",
                    f"{m.group().strip('( ')} is blocked",
                )
            )
        for m in STORAGE.finditer(body):
            if not re.search(r"\btry\b", body[max(0, m.start() - 200) : m.start()]):
                out.append(
                    Finding(
                        line_of(html, base + m.start()),
                        "storage",
                        "warning",
                        f"{m.group()} outside try",
                    )
                )


def lint(html: str, size: int | None = None) -> list[Finding]:
    out: list[Finding] = []
    check_title(html, out)
    check_hosts(html, out)
    skeleton = html.lstrip().lower().startswith(("<!doctype", "<html"))
    rules = parse_css(html)
    check_tokens(rules, out)
    # The publish skeleton's own first <style> sets plain body colours; they are not the author's.
    first_style = re.search(r"<style[^>]*>.*?</style>", html, FLAGS)
    own = html
    if skeleton and first_style:
        own = html[: first_style.start()] + html[first_style.end() :]
    check_colours(own, parse_css(own), out)
    check_body_and_gutter(html, rules, out)
    check_scripts(html, out)
    for m in re.finditer(r"(?<![\d.])100vh", html):
        out.append(
            Finding(
                line_of(html, m.start()),
                "viewport-height",
                "warning",
                "100vh; use dvh or a flex layout",
            )
        )
    if skeleton:
        out.append(
            Finding(
                1, "own-skeleton", "warning", "page starts with its own skeleton; publish wraps one"
            )
        )
    if (len(html.encode()) if size is None else size) > MAX_BYTES:
        out.append(Finding(1, "size", "error", "page above 16 MB"))
    text = blank(html, r"<(script|style|title)\b.*?</\1>|<!--.*?-->|<[^>]+>")
    for m in re.finditer("—", text):
        out.append(
            Finding(line_of(html, m.start()), "em-dash", "warning", "em dash in visible text")
        )
    return sorted(out, key=lambda f: f.line)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description="Lint claude.ai artifact HTML pages.")
    parser.add_argument("files", nargs="+", metavar="FILE")
    lines: list[str] = []
    errors = warnings = 0
    files = parser.parse_args(argv).files
    for name in files:
        try:
            raw = Path(name).read_bytes()
        except OSError as exc:
            found = [Finding(1, "read", "error", str(exc))]
        else:
            found = lint(raw.decode("utf-8", errors="replace"), len(raw))
        for f in found:
            errors += f.severity == "error"
            warnings += f.severity == "warning"
            lines.append(f"{name}:{f.line}: {f.severity} {f.rule}: {f.message}")
    print("\n".join(lines[:MAX_LINES]) if lines else "", end="\n" if lines else "")
    if len(lines) > MAX_LINES:
        print(f"... {len(lines) - MAX_LINES} more")
    print(f"artifact check: {len(files)} files, {errors} errors, {warnings} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
