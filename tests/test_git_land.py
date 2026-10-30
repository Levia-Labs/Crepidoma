import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("land", ROOT / "taskfiles/git/land.py")
land = importlib.util.module_from_spec(spec)
spec.loader.exec_module(land)

SHA = "a" * 40
OLD = "b" * 40


class Fake:
    """Scripted gh/git: replies keyed by argument prefix, popped in order when a list."""

    def __init__(self, replies):
        self.replies = replies
        self.calls = []
        self.slept = []

    def __call__(self, args):
        self.calls.append(args)
        for key, val in self.replies.items():
            if args[: len(key)] == list(key):
                if isinstance(val, list):
                    return val.pop(0) if len(val) > 1 else val[0]
                return val
        return 0, ""

    def sleep(self, s):
        self.slept.append(s)

    def called(self, *prefix):
        return any(c[: len(prefix)] == list(prefix) for c in self.calls)


def pr(mergeable="MERGEABLE", oid=SHA, state="OPEN"):
    return 0, json.dumps(
        {
            "number": 7,
            "headRefName": "feat/x",
            "headRefOid": oid,
            "mergeable": mergeable,
            "state": state,
        }
    )


def checks(*buckets):
    return 0, json.dumps(
        [
            {"name": f"c{i}", "bucket": b, "link": f"https://x/runs/1/job/{90 + i}"}
            for i, b in enumerate(buckets)
        ]
    )


def go(fake, argv=None, capsys=None):
    code = land.main(["7"] if argv is None else argv, run=fake, sleep=fake.sleep)
    return code, capsys.readouterr().out.splitlines()


def happy(over=None):
    base = {
        ("gh", "pr", "view", "7", "--json", "state"): (0, '{"state": "MERGED"}'),
        ("gh", "pr", "view"): pr(),
        ("git", "ls-remote"): (0, f"{SHA}\trefs/heads/feat/x\n"),
        ("gh", "pr", "checks"): checks("pass"),
        ("git", "symbolic-ref"): (0, "refs/remotes/origin/main\n"),
    }
    base.update(over or {})
    return Fake(base)


def test_happy_path_squash_merges_and_deletes_branch(capsys):
    fake = happy()
    code, out = go(fake, capsys=capsys)
    assert code == 0
    assert len(out) <= 20
    assert fake.called("gh", "pr", "merge", "7", "--squash")
    assert fake.called("git", "pull", "--ff-only", "--prune")
    assert ["git", "branch", "-D", "feat/x"] in fake.calls
    assert not fake.called("git", "branch", "--merged")


def test_branch_kept_when_pr_not_merged(capsys):
    fake = happy({("gh", "pr", "view", "7", "--json", "state"): (0, '{"state": "OPEN"}')})
    code, _out = go(fake, capsys=capsys)
    assert code == 0
    assert ["git", "branch", "-D", "feat/x"] not in fake.calls


def test_current_branch_pr_resolved_without_argument(capsys):
    fake = happy()
    code, _ = go(fake, argv=[], capsys=capsys)
    assert code == 0
    assert fake.calls[0][:5] == ["gh", "pr", "view", "--json", land.PR_FIELDS]


def test_stale_head_reopens_once_then_proceeds(capsys):
    fake = happy(
        {
            ("gh", "pr", "view"): [pr(oid=OLD), pr(oid=SHA)],
            ("git", "ls-remote"): (0, f"{SHA}\trefs/heads/feat/x\n"),
        }
    )
    code, _out = go(fake, capsys=capsys)
    assert code == 0
    assert fake.called("gh", "pr", "close", "7")
    assert fake.called("gh", "pr", "reopen", "7")
    assert sum(c[:3] == ["gh", "pr", "close"] for c in fake.calls) == 1


def test_stale_after_reopen_exits(capsys):
    fake = happy({("gh", "pr", "view"): pr(oid=OLD)})
    code, out = go(fake, capsys=capsys)
    assert code == 1
    assert "stale" in out[-1]
    assert not fake.called("gh", "pr", "merge")


def test_conflicting_exits_naming_state(capsys):
    fake = happy({("gh", "pr", "view"): pr(mergeable="CONFLICTING")})
    code, out = go(fake, capsys=capsys)
    assert code == 1
    assert "CONFLICTING" in out[-1] and "origin/main" in out[-1]
    assert not fake.called("gh", "pr", "merge")


def test_polls_until_checks_register(capsys):
    fake = happy(
        {
            ("gh", "pr", "checks"): [
                (1, "no checks reported"),
                (1, "no checks reported"),
                checks("pass"),
            ]
        }
    )
    code, _ = go(fake, capsys=capsys)
    assert code == 0
    assert len(fake.slept) == 2
    assert fake.slept[1] > fake.slept[0]


def test_no_checks_times_out(capsys):
    fake = happy({("gh", "pr", "checks"): (1, "no checks reported")})
    code, out = go(fake, argv=["7", "--timeout", "20"], capsys=capsys)
    assert code == 1
    assert "none registered" in out[-1]
    assert not fake.called("gh", "pr", "merge")


def test_pending_then_pass(capsys):
    fake = happy({("gh", "pr", "checks"): [checks("pending"), checks("pass")]})
    code, _ = go(fake, capsys=capsys)
    assert code == 0


def test_failure_prints_names_and_capped_logs(capsys):
    log = "\n".join(f"step\tline\tError number {i}" for i in range(40)) + "\nnoise\n"
    fake = happy(
        {
            ("gh", "pr", "checks"): checks("pass", "fail"),
            ("gh", "run", "view"): (0, log),
        }
    )
    code, out = go(fake, capsys=capsys)
    assert code == 1
    assert len(out) <= 20
    assert any("c1" in ln for ln in out)
    assert ["gh", "run", "view", "--job", "91", "--log-failed"] in fake.calls
    assert sum("Error number" in ln for ln in out) <= 10
    assert not fake.called("gh", "pr", "merge")


def test_repo_flag_is_passed_to_gh_and_ls_remote(capsys):
    fake = happy()
    code, _ = go(fake, argv=["7", "--repo", "o/n"], capsys=capsys)
    assert code == 0
    assert all(c[-2:] == ["-R", "o/n"] for c in fake.calls if c[0] == "gh")
    assert any(c[:2] == ["git", "ls-remote"] and "o/n" in c[2] for c in fake.calls)


def test_decisive_lines_caps_and_falls_back_to_tail():
    assert len(land.decisive_lines("\n".join(f"error {i}" for i in range(30)))) == 10
    assert land.decisive_lines("a\nb\nc", 2) == ["b", "c"]
