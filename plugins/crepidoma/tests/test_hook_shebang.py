import subprocess
from pathlib import Path

import hook_shebang


def make_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    return hooks


def test_rewrites_only_legacy_sh_shebangs(tmp_path: Path, capsys):
    hooks = make_repo(tmp_path)
    (hooks / "pre-push.legacy").write_bytes(b"#!/bin/sh\necho lfs\n")
    (hooks / "post-merge.legacy").write_bytes(b"#!/bin/bash\necho x\n")
    (hooks / "pre-commit").write_bytes(b"#!/bin/sh\necho keep\n")
    assert hook_shebang.main(["--root", str(tmp_path)]) == 0
    assert (hooks / "pre-push.legacy").read_bytes() == b"#!/usr/bin/env sh\necho lfs\n"
    assert (hooks / "post-merge.legacy").read_bytes() == b"#!/bin/bash\necho x\n"
    assert (hooks / "pre-commit").read_bytes() == b"#!/bin/sh\necho keep\n"
    assert capsys.readouterr().out == "hook shebangs: 1 rewritten\n"


def test_idempotent(tmp_path: Path, capsys):
    hooks = make_repo(tmp_path)
    (hooks / "pre-push.legacy").write_bytes(b"#!/bin/sh\r\nrun\n")
    hook_shebang.main(["--root", str(tmp_path)])
    capsys.readouterr()
    assert hook_shebang.main(["--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "hook shebangs: 0 rewritten\n"
    assert (hooks / "pre-push.legacy").read_bytes() == b"#!/usr/bin/env sh\r\nrun\n"
