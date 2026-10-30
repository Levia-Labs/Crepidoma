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


def test_squash_merged_branches_decided_by_pr_state(monkeypatch):
    replies = {("branch", "--format=%(refname:short)"): (0, "main\nsq\nwip\nfeat/a\n")}
    monkeypatch.setattr(gam, "git", lambda path, args: replies.get(tuple(args), (0, "")))
    monkeypatch.setattr(gam, "pr_merged", lambda path, b: b in ("sq", "feat/a"))
    assert gam.squash_merged("p", ["feat/a"], "main", "main") == ["sq"]


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


def test_main_already_deleted_branch_exit_0(monkeypatch, capsys, tmp_path):
    fake_git(
        monkeypatch,
        {
            ("symbolic-ref",): (0, "refs/remotes/origin/main\n"),
            ("log",): (0, "abc1234 feat: x\n"),
            ("branch", "-D"): (1, "error: branch 'feat/done' not found.\n"),
        },
    )
    assert gam.main([str(tmp_path), "feat/done"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "main abc1234 feat: x | dirty 0 | deleted none | branch feat/done already gone"
    ]


def test_main_other_delete_failure_exit_1(monkeypatch, capsys, tmp_path):
    fake_git(
        monkeypatch,
        {
            ("symbolic-ref",): (0, "refs/remotes/origin/main\n"),
            ("branch", "-D"): (1, "error: cannot delete checked out branch\n"),
        },
    )
    assert gam.main([str(tmp_path), "feat/done"]) == 1
    assert "branch -D failed" in capsys.readouterr().out
