import json

import ci_runs
import pytest

RUN_OK = {
    "databaseId": 7,
    "status": "completed",
    "conclusion": "success",
    "url": "https://x/runs/7",
    "workflowName": "ci",
}


def test_strip_ansi_removes_escapes_and_timestamp():
    raw = "2026-01-01T00:00:00.1234567Z \x1b[31;1merror\x1b[0m: boom"
    assert ci_runs.clean_line(raw) == "error: boom"


def test_error_lines_filters_dedupes_and_caps():
    text = "ok\nError: a\nError: a\nfatal error b\nfine\nerror c\n"
    assert ci_runs.error_lines(text, 2) == ["Error: a", "fatal error b"]
    assert ci_runs.error_lines(text, 20) == ["Error: a", "fatal error b", "error c"]


def test_error_lines_never_exceeds_cap():
    text = "\n".join(f"error {i}" for i in range(500))
    for cap in (0, 1, 7, 20):
        assert len(ci_runs.error_lines(text, cap)) == cap


def test_failed_jobs_picks_failure_only():
    data = {
        "jobs": [
            {"databaseId": 1, "name": "a", "conclusion": "success", "url": "u1"},
            {"databaseId": 2, "name": "b", "conclusion": "failure", "url": "u2"},
        ]
    }
    assert [j["name"] for j in ci_runs.failed_jobs(data)] == ["b"]


def fake_gh(monkeypatch, handler):
    calls = []

    def fake(args):
        calls.append(args)
        return handler(args)

    monkeypatch.setattr(ci_runs, "gh", fake)
    monkeypatch.setattr(ci_runs.time, "sleep", lambda s: None)
    return calls


def test_watch_waits_for_run_then_reports(monkeypatch, capsys):
    seq = iter([[], [], [dict(RUN_OK, status="in_progress", conclusion="")]])

    def handler(args):
        if args[:2] == ["run", "list"]:
            return 0, json.dumps(next(seq))
        if args[:2] == ["run", "watch"]:
            return 0, ""
        if args[:2] == ["run", "view"]:
            return 0, json.dumps(RUN_OK)
        raise AssertionError(args)

    fake_gh(monkeypatch, handler)
    code = ci_runs.main(["watch", "--sha", "a" * 40, "--repo", "o/r"])
    out = capsys.readouterr().out.splitlines()
    assert code == 0
    assert out == ["run 7 success ci https://x/runs/7"]


def test_watch_failure_exit_1(monkeypatch, capsys):
    bad = dict(RUN_OK, conclusion="failure")

    def handler(args):
        if args[:2] == ["run", "list"]:
            return 0, json.dumps([bad])
        return 0, json.dumps(bad)

    fake_gh(monkeypatch, handler)
    assert ci_runs.main(["watch"]) == 1
    assert "failure" in capsys.readouterr().out


def test_watch_timeout_exit_3(monkeypatch, capsys):
    fake_gh(monkeypatch, lambda a: (0, "[]"))
    assert ci_runs.main(["watch", "--sha", "b" * 40, "--timeout", "10", "--interval", "5"]) == 3
    assert "no run" in capsys.readouterr().out


def test_fail_prints_job_url_and_error_lines(monkeypatch, capsys):
    jobs = {
        "jobs": [
            {"databaseId": 9, "name": "build", "conclusion": "failure", "url": "https://x/job/9"}
        ]
    }
    log = "2026-01-01T00:00:00Z \x1b[31mError: bad\x1b[0m\nnoise\n"

    def handler(args):
        if args[:2] == ["run", "view"]:
            return 0, json.dumps(jobs)
        if args[0] == "api" and "jobs/9/logs" in args[1]:
            assert "--allow-escape-sequences" in args
            return 0, log
        raise AssertionError(args)

    fake_gh(monkeypatch, handler)
    code = ci_runs.main(["fail", "--run", "5", "--repo", "o/r"])
    out = capsys.readouterr().out.splitlines()
    assert code == 1
    assert out == ["build https://x/job/9", "  Error: bad"]


def test_fail_no_failed_jobs_exit_0(monkeypatch, capsys):
    fake_gh(monkeypatch, lambda a: (0, json.dumps({"jobs": []})))
    assert ci_runs.main(["fail", "--run", "5", "--repo", "o/r"]) == 0
    assert capsys.readouterr().out.strip() == "ci: no failed jobs"


def test_fail_no_run_exit_3(monkeypatch, capsys):
    fake_gh(monkeypatch, lambda a: (0, "[]"))
    assert ci_runs.main(["fail", "--repo", "o/r"]) == 3


def test_usage_error_exit_2():
    with pytest.raises(SystemExit) as e:
        ci_runs.main(["watch", "--sha", "a", "--run", "1"])
    assert e.value.code == 2
