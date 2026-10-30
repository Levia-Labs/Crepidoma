import gate_runner
import pytest


def fake_run(monkeypatch, results):
    calls = []

    def fake(cmd):
        calls.append(cmd)
        return results[cmd[-1]] if cmd[-1] in results else results["*"]

    monkeypatch.setattr(gate_runner, "run", fake)
    return calls


def test_run_pass_one_line_each(monkeypatch, capsys):
    calls = fake_run(monkeypatch, {"*": (0, "noise\n")})
    assert gate_runner.main(["run", "a", "b"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert calls == [["task", "a"], ["task", "b"]]
    assert len(lines) == 2
    assert lines[0].startswith("PASS a ") and lines[0].endswith("s")


def test_run_stops_at_first_failure(monkeypatch, capsys):
    calls = fake_run(monkeypatch, {"a": (1, "ok\nError: boom\n"), "*": (0, "")})
    assert gate_runner.main(["run", "a", "b"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert calls == [["task", "a"]]
    assert out[0].startswith("FAIL a ")
    assert out[1:] == ["Error: boom"]


def test_run_keep_going(monkeypatch, capsys):
    calls = fake_run(monkeypatch, {"a": (1, "failed x"), "*": (0, "")})
    assert gate_runner.main(["run", "a", "b", "--keep-going"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert len(calls) == 2
    assert out[0].startswith("FAIL a ")
    assert out[-1].startswith("PASS b ")


def test_excerpt_caps_and_selects():
    noisy = "\n".join(["Traceback (most recent call last):"] + [f"E  line {n}" for n in range(30)])
    assert len(gate_runner.excerpt(noisy)) == 12
    assert gate_runner.excerpt("a\nb\nc") == ["a", "b", "c"]
    plain = "\n".join(f"row {n}" for n in range(30))
    assert gate_runner.excerpt(plain) == [f"row {n}" for n in range(18, 30)]
    assert gate_runner.excerpt("x\nFAILED t::a\ny") == ["FAILED t::a"]


def test_quiet_success(monkeypatch, capsys):
    fake_run(monkeypatch, {"*": (0, "lots\nof\noutput")})
    assert gate_runner.main(["quiet", "--", "echo", "hi"]) == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("ok (") and out.endswith("s)")


def test_quiet_failure_propagates_code(monkeypatch, capsys):
    calls = fake_run(monkeypatch, {"*": (7, "one\nTraceback\ntwo")})
    assert gate_runner.main(["quiet", "--", "cmd", "arg"]) == 7
    assert calls == [["cmd", "arg"]]
    assert capsys.readouterr().out.splitlines() == ["Traceback"]


def test_quiet_requires_command():
    with pytest.raises(SystemExit) as info:
        gate_runner.main(["quiet", "--"])
    assert info.value.code == 2


def test_real_run_missing_binary():
    code, output = gate_runner.run(["definitely-not-a-real-binary-xyz"])
    assert code == 127
    assert "not found" in output


def test_unencodable_output_is_replaced_on_cp1250(monkeypatch):
    import io
    import sys

    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1250", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)
    fake_run(monkeypatch, {"*": (1, "Error: ● broke\n")})
    assert gate_runner.main(["run", "a"]) == 1
    stream.flush()
    assert raw.getvalue().decode("cp1250").splitlines()[1] == "Error: ? broke"
