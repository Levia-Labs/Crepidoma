"""Build self-contained claude.ai artifact pages from a JSON spec.

Usage:
  artifact.py build SPEC.json [-o OUT.html] [--standalone]
  artifact.py new OUT.json [--kind graph|board|timeline|cards|layers|pivot|treemap|sankey|heatmap]
  artifact.py check FILE.html...
  artifact.py shot PAGE.html --out PNG [--width 1280] [--height 4000] [--theme light|dark|system]

`build` validates the spec (`spec:<json path>: message` lines, exit 1) and writes one page: styles,
data and only the scripts its section types need. Without --standalone the page is an artifact
fragment (no doctype, html, head or body); --standalone wraps it for local viewing. `new` writes a
small example spec and never overwrites. `check` runs artifact_check on built pages. `shot` takes a
headless-browser screenshot in a forced theme (artifact_shot). The schema
lives in artifact_kit/SPEC.md.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import artifact_budget
import artifact_examples
import artifact_spec

KIT = Path(__file__).resolve().parent / "artifact_kit"
TYPES = (
    "prose",
    "cards",
    "board",
    "timeline",
    "graph",
    "layers",
    "pivot",
    "treemap",
    "sankey",
    "heatmap",
)
SCRIPTS = {s: f"{s}.js" for s in TYPES}
FONTS = (
    "https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..100,500..800"
    "&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap"
)
KINDS = sorted(artifact_examples.SECTIONS)


def read_kit(name: str) -> str:
    return (KIT / name).read_text(encoding="utf-8").strip()


def data_script(spec: dict) -> str:
    """The spec as inert JSON; every `<` becomes \\u003c, so no text can close the script."""
    payload = json.dumps(spec, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return f'<script type="application/json" id="artifact-data">{payload}</script>'


def script_for(spec: dict) -> str:
    kinds = {s.get("type") for s in spec["sections"]}
    dictionary = json.dumps(
        artifact_spec.ui_dictionary(), ensure_ascii=False, separators=(",", ":")
    )
    parts = [f"var UIDICT={dictionary};", read_kit("core.js")]
    parts += [read_kit(SCRIPTS[k]) for k in SCRIPTS if k in kinds]
    parts.append("R.boot();")
    return "\n".join(parts)


def render(spec: dict, standalone: bool) -> str:
    """The page text; a fragment starting at <title>, or a full document when standalone."""
    head = "\n".join(
        [
            f"<title>{html.escape(spec['title'], quote=False)}</title>",
            '<meta name="claude:viewport-fit-sides" content="cover">',
            '<link rel="preconnect" href="https://fonts.googleapis.com">',
            f'<link rel="stylesheet" href="{FONTS}">',
            f"<style>\n{read_kit('kit.css')}\n</style>",
        ]
    )
    body = "\n".join(
        [
            '<div class="wrap" id="app"></div>',
            data_script(spec),
            f"<script>\n{script_for(spec)}\n</script>",
        ]
    )
    if not standalone:
        return f"{head}\n{body}\n"
    lang = html.escape(str(spec.get("lang", "en")))
    meta = (
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    )
    opening = f'<!doctype html>\n<html lang="{lang}"><head>'
    return f"{opening}\n{meta}\n{head}\n</head><body>\n{body}\n</body></html>\n"


def load_spec(path: Path) -> tuple[dict | None, list[str]]:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, [f"spec:$: cannot read {path}: {exc}"]
    errors = artifact_spec.validate(spec)
    return (None if errors else spec), errors


def build(args: argparse.Namespace) -> int:
    spec, errors = load_spec(args.spec)
    if spec is None:
        print("\n".join(errors), file=sys.stderr)
        return 1
    for line in artifact_budget.warnings(spec):
        print(line, file=sys.stderr)
    out = args.output or args.spec.with_suffix(".html")
    page = render(spec, args.standalone)
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(page)
    print(f"artifact build: {out} {len(page.encode('utf-8'))} B, {len(spec['sections'])} sections")
    return 0


def new(args: argparse.Namespace) -> int:
    if args.out.exists():
        print(f"artifact new: {args.out} exists; not overwriting", file=sys.stderr)
        return 1
    text = json.dumps(artifact_examples.example(args.kind), ensure_ascii=False, indent=2) + "\n"
    with args.out.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"artifact new: {args.out} {args.kind}")
    return 0


def check(args: argparse.Namespace) -> int:
    import artifact_check

    return artifact_check.main([str(f) for f in args.files])


def shot(args: argparse.Namespace) -> int:
    import artifact_shot

    argv = [str(args.page), "--out", str(args.out), "--width", str(args.width)]
    return artifact_shot.main([*argv, "--height", str(args.height), "--theme", args.theme])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="artifact.py", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    sub = commands.add_parser("build")
    sub.add_argument("spec", type=Path)
    sub.add_argument("-o", "--output", type=Path)
    sub.add_argument("--standalone", action="store_true")
    sub.set_defaults(run=build)
    sub = commands.add_parser("new")
    sub.add_argument("out", type=Path)
    sub.add_argument("--kind", choices=KINDS, default="graph")
    sub.set_defaults(run=new)
    sub = commands.add_parser("check")
    sub.add_argument("files", nargs="+", type=Path)
    sub.set_defaults(run=check)
    sub = commands.add_parser("shot")
    sub.add_argument("page", type=Path)
    sub.add_argument("--out", type=Path, required=True)
    sub.add_argument("--width", type=int, default=1280)
    sub.add_argument("--height", type=int, default=4000)
    sub.add_argument("--theme", choices=["light", "dark", "system"], default="light")
    sub.set_defaults(run=shot)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
