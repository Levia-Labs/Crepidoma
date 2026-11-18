"""CSS-side rules of artifact_check: stylesheet parsing, theme tokens and literal colours."""

from __future__ import annotations

import re
from typing import NamedTuple

FLAGS = re.I | re.S
COLOUR = re.compile(
    r"(?<![\w-])#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})(?![\w-])|(?<![\w-])(?:rgb|hsl)a?\(", re.I
)
PROP = re.compile(r"(--[\w-]+)\s*:")
DARK_SCHEME = re.compile(r"color-scheme\s*:\s*dark")


class Finding(NamedTuple):
    line: int
    rule: str
    severity: str
    message: str


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def blank(text: str, pattern: str) -> str:
    """Replace matches with spaces, keeping newlines, so offsets and line numbers survive."""
    return re.sub(pattern, lambda m: re.sub(r"[^\n]", " ", m.group()), text, flags=FLAGS)


class Rule(NamedTuple):
    ctx: str
    selector: str
    decls: list[tuple[str, int]]
    line: int


def parse_css(html: str) -> list[Rule]:
    """Flat list of style rules from all <style> blocks; at-rule preludes land in ctx."""
    rules: list[Rule] = []
    for sm in re.finditer(r"<style\b[^>]*>(.*?)</style>", html, FLAGS):
        css = blank(sm.group(1), r"/\*.*?\*/")
        base, stack, last = sm.start(1), [], 0
        for m in re.finditer(r"[{};]", css):
            chunk = css[last : m.start()]
            last = m.end()
            if m.group() == "{":
                sel = " ".join(chunk.split())
                if sel.startswith("@"):
                    stack.append(Rule("", sel, [], 0))
                else:
                    ctx = " ".join(" ".join(f.selector.split()) for f in stack)
                    stack.append(Rule(ctx, sel, [], line_of(html, base + m.start())))
            elif stack:
                if chunk.strip():
                    stack[-1].decls.append((chunk, base + m.start() - len(chunk)))
                if m.group() == "}":
                    done = stack.pop()
                    if not done.selector.startswith("@"):
                        rules.append(done)
    return rules


def token_kind(rule: Rule) -> str | None:
    sel = rule.selector.replace("'", '"').replace(" ", "")
    if sel == ":root" and not rule.ctx:
        return "root"
    if sel == ':root:not([data-theme="light"])' and "prefers-color-scheme:dark" in rule.ctx.replace(
        " ", ""
    ):
        return "media"
    if sel == ':root[data-theme="dark"]' and not rule.ctx:
        return "attr"
    return None


def props(rule: Rule) -> set[str]:
    return {m.group(1) for d, _ in rule.decls for m in PROP.finditer(d)}


def check_tokens(rules: list[Rule], out: list[Finding]) -> None:
    kinds: dict[str, list[Rule]] = {"root": [], "media": [], "attr": []}
    for r in rules:
        if (k := token_kind(r)) is not None:
            kinds[k].append(r)
    root = set().union(*(props(r) for r in kinds["root"]))
    dark = {k: set().union(*(props(r) for r in kinds[k])) for k in ("media", "attr")}
    if bool(kinds["media"]) != bool(kinds["attr"]):
        line = (kinds["media"] or kinds["attr"])[0].line
        out.append(Finding(line, "theme-tokens", "error", "only one of the two dark blocks exists"))
    for k in ("media", "attr"):
        for r in kinds[k]:
            if not any(DARK_SCHEME.search(d) for d, _ in r.decls):
                out.append(
                    Finding(r.line, "theme-tokens", "error", "dark block lacks color-scheme: dark")
                )
        for p in sorted(dark[k] - root):
            out.append(
                Finding(
                    kinds[k][0].line,
                    "theme-tokens",
                    "error",
                    f"{p} defined in dark block but missing on :root",
                )
            )
    if kinds["media"] and kinds["attr"] and dark["media"] != dark["attr"]:
        diff = ", ".join(sorted(dark["media"] ^ dark["attr"]))
        out.append(
            Finding(kinds["attr"][0].line, "theme-tokens", "error", f"dark blocks differ: {diff}")
        )


def check_colours(html: str, rules: list[Rule], out: list[Finding]) -> None:
    def warn(pos: int, where: str) -> None:
        out.append(
            Finding(line_of(html, pos), "literal-colour", "warning", f"literal colour in {where}")
        )

    for r in rules:
        if token_kind(r) is None:
            for d, off in r.decls:
                if COLOUR.search(re.sub(r"url\([^)]*\)", "", d)):
                    warn(off, f"rule {r.selector}")
    for m in re.finditer(r"(?<![\w-])style\s*=\s*\"([^\"]*)\"", html, FLAGS):
        if COLOUR.search(m.group(1)):
            warn(m.start(), "inline style")
    for m in re.finditer(r"(?<![\w-])(?:fill|stroke)\s*=\s*[\"']([^\"']*)[\"']", html, FLAGS):
        if COLOUR.search(m.group(1)):
            warn(m.start(), "fill/stroke attribute")
