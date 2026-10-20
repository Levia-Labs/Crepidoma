import git_after_merge as gam
import pytest


def test_default_branch_parses_symbolic_ref():
    assert gam.default_branch("refs/remotes/origin/main\n") == "main"
    assert gam.default_branch("refs/remotes/origin/release/x") == "release/x"
    assert gam.default_branch("") == "main"


def test_branches_to_delete_merged_and_gone():
    merged = "* main\n  feat/a\n+ wt\n"
    vv = (
        "* main  abc [origin/main] s\n"
        "  feat/a abc [origin/feat/a] s\n"
        "  sq     abc [origin/sq: gone] s\n"
        "  keep   abc [origin/keep] s\n"
    )
    assert gam.branches_to_delete(merged, vv, "main", "main") == ["feat/a", "sq"]


def test_branches_to_delete_excludes_current_and_default():
    merged = "* main\n  dev\n"
    assert gam.branches_to_delete(merged, "", "main", "dev") == []
    assert gam.branches_to_delete(merged, "", "main", "main") == ["dev"]


@pytest.mark.parametrize("out,n", [("", 0), (" M a\n?? b\n", 2)])
def test_dirty_count(out, n):
    assert gam.dirty_count(out) == n


def fake_git(monkeypatch, replies):
    calls = []

    def fake(path, args):
        calls.append(args)
        for key, val in replies.items():
            if args[: len(key)] == list(key):
                return val
        return 0, ""

    monkeypatch.setattr(gam, "git", fake)
    return calls


def test_main_receipt_and_named_branch(monkeypatch, capsys, tmp_path):
    calls = fake_git(
        monkeypatch,
        {
            ("symbolic-ref",): (0, "refs/remotes/origin/main\n"),
            ("log",): (0, "abc1234 feat: x\n"),
            ("status",): (0, " M a\n"),
            ("branch", "--show-current"): (0, "main\n"),
        },
    )
    code = gam.main([str(tmp_path), "feat/done"])
    assert code == 0
    assert capsys.readouterr().out.splitlines() == [
        "main abc1234 feat: x | dirty 1 | deleted feat/done"
    ]
    assert ["branch", "-D", "feat/done"] in calls
    assert ["pull", "--ff-only", "--prune"] in calls


def test_main_step_failure_exit_1(monkeypatch, capsys, tmp_path):
    fake_git(monkeypatch, {("pull",): (1, "fatal: not ff\n")})
    assert gam.main([str(tmp_path)]) == 1
    assert capsys.readouterr().out.startswith("after-merge: pull failed")


def test_main_missing_path_exit_2(tmp_path):
    assert gam.main([str(tmp_path / "nope")]) == 2
