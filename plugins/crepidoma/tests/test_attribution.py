import subprocess
from pathlib import Path

import attribution
import pytest

BAD = [
    "Co-Authored-By: Claude <noreply@anthropic.com>",
    "co-authored-by: Claude Sonnet 5.5 <x@example.com>",
    "CO-AUTHORED-BY: Anthropic Someone <someone@example.com>",
    "Co-authored-by : anthropic bot <a@b.c>",
    "Generated with [Claude Code](https://claude.com/claude-code)",
    "generated with claude code",
    "GENERATED WITH [CLAUDE CODE]",
    "contact noreply@Anthropic.com",
]
CLEAN = [
    "Co-Authored-By: Jane Doe <jane@example.com>",
    "co-authored-by: Bob <bob@users.noreply.github.com>",
    "feat: add parser",
    "Generated with protoc",
    "Fix the claude-free path",
    "",
]


@pytest.mark.parametrize("line", BAD)
def test_flags_attribution(line):
    assert attribution.has_attribution(line)
    assert attribution.has_attribution(f"feat: x\n\nbody\n\n{line}\n")


@pytest.mark.parametrize("line", CLEAN)
def test_passes_clean(line):
    assert not attribution.has_attribution(line)


@pytest.mark.parametrize("prefix", ["", "x ", "\t", "- "])
@pytest.mark.parametrize("line", BAD)
def test_line_number_reported(prefix, line):
    assert attribution.hits(f"a\nb\n{prefix}{line}") == [(3, f"{prefix}{line}".strip())]


def test_msg_mode(tmp_path, capsys):
    bad = tmp_path / "MSG"
    bad.write_text("feat: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n", encoding="utf-8")
    assert attribution.main(["msg", str(bad)]) == 1
    assert f"{bad}:3: Co-Authored-By: Claude" in capsys.readouterr().out
    good = tmp_path / "OK"
    good.write_text("feat: x\n\nCo-Authored-By: Jane <j@example.com>\n", encoding="utf-8")
    assert attribution.main(["msg", str(good)]) == 0


def run(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    run(tmp_path, "init", "-q")
    run(tmp_path, "config", "user.email", "t@example.com")
    run(tmp_path, "config", "user.name", "t")
    run(tmp_path, "config", "commit.gpgsign", "false")
    run(tmp_path, "commit", "-q", "--allow-empty", "-m", "first")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_range_mode(repo, capsys):
    run(repo, "commit", "-q", "--allow-empty", "-m", "ok\n\nCo-Authored-By: Jane <j@example.com>")
    assert attribution.main(["range"]) == 0
    run(repo, "commit", "-q", "--allow-empty", "-m", "bad\n\nGenerated with Claude Code")
    assert attribution.main(["range"]) == 1
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and out[0].endswith(": Generated with Claude Code")
    assert attribution.main(["range", "HEAD~2..HEAD~1"]) == 0


def test_range_default_last_commit(repo):
    assert attribution.default_range() == "HEAD"
    run(repo, "commit", "-q", "--allow-empty", "-m", "second")
    assert attribution.default_range() == "HEAD~1..HEAD"


def test_usage(capsys):
    assert attribution.main([]) == 2
