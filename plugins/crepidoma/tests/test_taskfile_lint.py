import subprocess
from pathlib import Path

import taskfile_lint


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def lint(capsys, *argv: str) -> tuple[int, list[str]]:
    code = taskfile_lint.main(list(argv))
    return code, capsys.readouterr().out.splitlines()


def test_vars_flags_unprefixed_and_inherited(tmp_path, capsys):
    root = write(
        tmp_path / "Taskfile.yml",
        "version: '3'\nvars:\n  PY: python3\nincludes:\n  rust: ./rust\n",
    )
    write(
        tmp_path / "rust" / "Taskfile.yml",
        "version: '3'\nvars:\n  RUN: cargo\n  RUST_OK: x\n"
        "tasks:\n  go:\n    cmds:\n      - uv run {{.PY}} x.py\n",
    )
    code, out = lint(capsys, "vars", str(root))
    assert code == 1
    assert any("rule4" in r and "RUN" in r and ":3:" in r for r in out)
    assert not any("RUST_OK" in r for r in out)
    assert any(
        r.endswith("rule3 include rust inherits PY; pass in vars:") and ":5:" in r for r in out
    )


def test_vars_passed_is_clean(tmp_path, capsys):
    root = write(
        tmp_path / "Taskfile.yml",
        "vars:\n  PY: python3\nincludes:\n  rust:\n    taskfile: ./rust\n"
        '    vars:\n      PY: "{{.PY}}"\n',
    )
    write(
        tmp_path / "rust" / "Taskfile.yml",
        "vars:\n  RUST_X: 1\ntasks:\n  go:\n    cmds:\n      - uv run {{.PY}} x.py\n",
    )
    assert lint(capsys, "vars", str(root)) == (0, [])


def test_vars_flow_passed(tmp_path, capsys):
    root = write(
        tmp_path / "Taskfile.yml",
        'vars:\n  PY: python3\nincludes:\n  rust: { taskfile: ./rust, vars: { PY: "{{.PY}}" } }\n',
    )
    write(
        tmp_path / "rust" / "Taskfile.yml", "tasks:\n  go:\n    cmds:\n      - uv run {{.PY}} x\n"
    )
    assert lint(capsys, "vars", str(root)) == (0, [])


def test_shell_flags_rules(tmp_path, capsys):
    path = write(
        tmp_path / "Taskfile.yml",
        "tasks:\n"
        "  a:\n"
        "    env:\n"
        "      PATH: /x\n"
        "    cmds:\n"
        "      - |\n"
        "        if [[ -n $A ]]; then echo hi; fi\n"
        "        arr=(1 2)\n"
        "        cat <<< hi\n"
        "        function f { :; }\n"
        "        mv -f a b\n"
        "        .venv/bin/python x.py\n"
        "        python3 y.py\n"
        "      - python z.py\n",
    )
    code, out = lint(capsys, "shell", str(path))
    text = "\n".join(out)
    assert code == 1
    for needle in (
        ":4: rule7",
        ":7: rule1",
        ":8: rule1",
        ":9: rule1",
        ":10: rule1",
        ":11: rule9",
        ":12: rule2",
        ":13: rule2",
        ":14: rule2",
    ):
        assert needle in text, needle


def test_shell_clean(tmp_path, capsys):
    path = write(
        tmp_path / "Taskfile.yml",
        'tasks:\n  a:\n    cmds:\n      - |\n        if [ -n "$A" ]; then rm -f b; mv a b; fi\n'
        "        uv run {{.PY}} x.py\n        uv run python y.py\n"
        "      - cmd: uv run {{.PY}} z.py\n",
    )
    assert lint(capsys, "shell", str(path)) == (0, [])


def test_output_capped(tmp_path, capsys):
    body = "".join(f"      - mv -f a{i} b\n" for i in range(30))
    path = write(tmp_path / "Taskfile.yml", "tasks:\n  a:\n    cmds:\n" + body)
    report = tmp_path / "full.txt"
    code, out = lint(capsys, "all", str(path), "--report", str(report))
    assert code == 1
    assert len(out) == 20
    assert out[-1] == "... 11 more (use --report FILE)"
    assert len(report.read_text(encoding="utf-8").splitlines()) == 30


def test_shellcheck_monkeypatched(tmp_path, capsys, monkeypatch):
    path = write(
        tmp_path / "Taskfile.yml",
        "tasks:\n  a:\n    cmds:\n      - |\n        echo ok\n        echo $x\n",
    )
    calls = []

    def fake_run(args, text):
        calls.append((args, text))
        return subprocess.CompletedProcess(args, 1, "-:2:6: warning: Double quote [SC2086]\n", "")

    monkeypatch.setattr(taskfile_lint, "run", fake_run)
    monkeypatch.setattr(taskfile_lint.shutil, "which", lambda name: "/bin/shellcheck")
    code, out = lint(capsys, "shell", "--shellcheck", str(path))
    assert calls[0][0] == ["shellcheck", "-s", "sh", "-f", "gcc", "-"]
    assert code == 1
    assert out == [f"{path.as_posix()}:6: shellcheck warning: Double quote [SC2086]"]


def test_shellcheck_missing_skipped(tmp_path, capsys, monkeypatch):
    path = write(tmp_path / "Taskfile.yml", "tasks:\n  a:\n    cmds:\n      - echo ok\n")
    monkeypatch.setattr(taskfile_lint.shutil, "which", lambda name: None)
    assert lint(capsys, "shell", "--shellcheck", str(path)) == (0, [])


def test_tracked_default(tmp_path, capsys, monkeypatch):
    write(tmp_path / "Taskfile.yml", "tasks:\n  a:\n    cmds:\n      - mv -f a b\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(taskfile_lint, "tracked", lambda root: [root / "Taskfile.yml"])
    code, out = lint(capsys, "all")
    assert code == 1
    assert out == ["Taskfile.yml:4: rule9 `mv -f`; use `rm` then `mv`"]


def test_usage_error(capsys):
    assert taskfile_lint.main(["bogus"]) == 2
    capsys.readouterr()
