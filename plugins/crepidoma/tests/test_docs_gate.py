import subprocess

import docs_gate
import pytest


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(docs_gate, "ROOT", tmp_path)
    return tmp_path


def write(root, name, text=""):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def fake_git(monkeypatch, names):
    monkeypatch.setattr(docs_gate, "run", lambda *command: "\n".join(names))


def test_links_flags_broken_and_accepts_good(repo, monkeypatch, capsys):
    write(repo, "a.md", "[ok](b.md)\n[bad](missing.md#x)\n`docs/b.md` and `src/gone.py`\n")
    write(repo, "b.md")
    write(repo, "docs/b.md")
    fake_git(monkeypatch, ["a.md", "b.md", "docs/b.md"])
    assert docs_gate.main(["links"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert "a.md:2: links missing.md#x" in out
    assert "a.md:3: links src/gone.py" in out
    assert not any("docs/b.md" in line and "links" in line for line in out)
    assert out[-1].startswith("2 new")


def test_links_skip_fenced_urls_and_wildcards(repo):
    write(repo, "a.md", "```\n[x](nope.md)\n```\n[u](https://x.io/a.md) `a/*.py` `~/x/y.py`\n")
    assert docs_gate.main(["links", "a.md"]) == 0


def test_links_case_exact(repo):
    write(repo, "Real.md")
    write(repo, "a.md", "[x](real.md)\n")
    assert docs_gate.main(["links", "a.md"]) == 1


def test_readme_missing_and_extra(repo, capsys):
    write(repo, "tools/README.md", "- `one.py` does x\n- `ghost.py` does y\n")
    write(repo, "tools/one.py")
    write(repo, "tools/two.py")
    assert docs_gate.main(["readme", "tools/README.md"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert "tools/README.md:2: readme extra ghost.py" in out
    assert "tools/README.md:1: readme missing two.py" in out


def test_readme_ignores_meta_sidecars(repo, capsys):
    write(repo, "tools/README.md", "- `one.py` does x\n- `gone.py.meta` does y\n")
    write(repo, "tools/one.py")
    write(repo, "tools/one.py.meta")
    assert docs_gate.main(["readme", "tools/README.md"]) == 0


def test_readme_without_list_is_skipped(repo):
    write(repo, "tools/README.md", "prose only\n")
    write(repo, "tools/one.py")
    assert docs_gate.main(["readme", "tools/README.md"]) == 0


def test_baseline_ratchet_and_update(repo, monkeypatch, capsys):
    write(repo, "a.md", "[bad](missing.md)\n")
    fake_git(monkeypatch, ["a.md"])
    assert docs_gate.main(["all", "--update"]) == 0
    baseline = (repo / ".ratchet" / "docs.baseline").read_text(encoding="utf-8")
    assert baseline == "a.md:1: links missing.md\n"
    capsys.readouterr()
    assert docs_gate.main(["all"]) == 0
    assert capsys.readouterr().out.strip() == "0 new, 1 baselined, 1 files"
    write(repo, "a.md", "[bad](missing.md)\n[worse](other.md)\n")
    assert docs_gate.main(["all"]) == 1
    assert "a.md:2: links other.md" in capsys.readouterr().out


def test_output_capped_at_20_lines(repo, capsys):
    write(repo, "a.md", "".join(f"[x](m{i}.md)\n" for i in range(40)))
    assert docs_gate.main(["links", "a.md"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 20
    assert out[-1].startswith("40 new")


def git_repo(root, tracked):
    for args in (["init", "-q"], ["add", *tracked]):
        subprocess.run(["git", *args], cwd=root, check=True)


def test_untracked_link_target_is_reported(repo, capsys):
    write(repo, "a.md", "[t](b.md) [u](local.md) [g](out/x.md) `out/x.md`\n")
    write(repo, "b.md")
    write(repo, "local.md")
    write(repo, "out/x.md")
    write(repo, "tools/README.md", "- `one.py` x\n")
    write(repo, "tools/one.py")
    write(repo, "tools/stray.py")
    git_repo(repo, ["a.md", "b.md", "tools/README.md", "tools/one.py"])
    assert docs_gate.main(["all"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert "a.md:1: untracked-link local.md" in out
    assert "a.md:1: untracked-link out/x.md" in out
    assert not any("b.md" in line for line in out)
    assert not any("stray.py" in line for line in out)


def test_generated_paths_are_not_reported_when_untracked(repo, capsys):
    write(repo, "a.md", "See `graphify-out/GRAPH_REPORT.md` and `dist/app.js`.\n")
    write(repo, "graphify-out/GRAPH_REPORT.md")
    git_repo(repo, ["a.md"])
    assert docs_gate.main(["all"]) == 0
    assert capsys.readouterr().out.count("untracked-link") == 0
