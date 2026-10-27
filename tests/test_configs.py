import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = ROOT / "configs"
EXPECTED = [
    ".editorconfig",
    ".gitattributes",
    ".prettierrc",
    "eslint.config.js",
    "ruff.toml",
    ".yamllint",
    "sgconfig.yml",
    "gitleaks.toml",
    "semgrep/rules.yml",
    "zizmor.yml",
    ".hadolint.yaml",
    "tsconfig.base.json",
]


def test_all_configs_present():
    missing = [name for name in EXPECTED if not (CONFIGS / name).is_file()]
    assert missing == []


def test_structured_configs_parse():
    tomllib.loads((CONFIGS / "ruff.toml").read_text(encoding="utf-8"))
    tomllib.loads((CONFIGS / "gitleaks.toml").read_text(encoding="utf-8"))
    json.loads((CONFIGS / ".prettierrc").read_text(encoding="utf-8"))


def test_root_ruff_extends_shared():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["tool"]["ruff"]["extend"] == "configs/ruff.toml"


def test_eslint_config_has_scoped_globals():
    text = (CONFIGS / "eslint.config.js").read_text(encoding="utf-8")
    for name in ("document", "window", "fetch", "process", "require"):
        assert f'"{name}"' in text
    for glob in ("**/*.browser.js", "**/*.mjs", "**/*.cjs"):
        assert glob in text


def test_eslint_config_ignores_vendored_dirs():
    text = (CONFIGS / "eslint.config.js").read_text(encoding="utf-8")
    for glob in ("**/.venv/**", "**/node_modules/**", "**/.crepidoma/**"):
        assert f'"{glob}"' in text


FIXTURES = {
    "web/app.js": "document.title = CSS.escape(String(window.innerWidth));\n",
    "web/app.mjs": "export const w = window.innerWidth;\n",
    "scripts/x.mjs": "export const p = process.argv;\n",
    "scripts/x.cjs": "module.exports = require('node:fs');\n",
}


@pytest.fixture(scope="module")
def eslint_dir(tmp_path_factory):
    npm = shutil.which("npm")
    if npm is None or shutil.which("node") is None:
        pytest.skip("node/npm not available")
    work = tmp_path_factory.mktemp("eslint")
    (work / "package.json").write_text('{"private": true, "type": "module"}', encoding="utf-8")
    install = subprocess.run(
        [npm, "install", "--no-audit", "--no-fund", "eslint", "@eslint/js", "typescript-eslint"],
        cwd=work,
        capture_output=True,
        text=True,
    )
    if install.returncode != 0:
        pytest.skip("eslint not installable: " + install.stderr[-200:])
    cfg = work / "eslint.config.js"
    cfg.write_text((CONFIGS / "eslint.config.js").read_text(encoding="utf-8"), encoding="utf-8")
    return work


def _lint(work, rel, source):
    target = work / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return subprocess.run(
        [shutil.which("npx"), "--no-install", "eslint", "--config", "eslint.config.js", rel],
        cwd=work,
        capture_output=True,
        text=True,
    )


def test_eslint_globals_behaviour(eslint_dir):
    for rel, source in FIXTURES.items():
        result = _lint(eslint_dir, rel, source)
        assert result.returncode == 0, rel + result.stdout[-400:] + result.stderr[-200:]
    bad = _lint(eslint_dir, "web/bad.js", "export const p = process.argv;\n")
    assert bad.returncode != 0
    bad_mjs = _lint(eslint_dir, "web/bad.mjs", "export const p = process.argv;\n")
    assert bad_mjs.returncode != 0
