import json
import tomllib
from pathlib import Path

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
