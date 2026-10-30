import json

import hooks
import hooks_line_cap as cap


def raw(text):
    return text.encode()


def lines(count):
    return "x\n" * count


def write_event(root, name, content):
    return {"tool_name": "Write", "tool_input": {"file_path": str(root / name), "content": content}}


def edit_event(root, name, old, new, replace_all=False):
    return {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(root / name),
            "old_string": old,
            "new_string": new,
            "replace_all": replace_all,
        },
    }


def baseline(root, entries):
    folder = root / ".ratchet"
    folder.mkdir(exist_ok=True)
    body = "".join(f"{name}\t{count}\n" for name, count in entries.items())
    (folder / "long-files.baseline").write_bytes(raw(body))


def test_write_over_cap_refused(tmp_path):
    reason = cap.refusal(write_event(tmp_path, "a.py", lines(301)), tmp_path)
    assert reason and "301" in reason and "plit the file" in reason


def test_write_at_cap_allowed(tmp_path):
    assert cap.refusal(write_event(tmp_path, "a.py", lines(300)), tmp_path) is None


def test_edit_pushing_over_cap_refused(tmp_path):
    (tmp_path / "a.py").write_bytes(raw(lines(299) + "mark\n"))
    event = edit_event(tmp_path, "a.py", "mark\n", "one\ntwo\nthree\n")
    reason = cap.refusal(event, tmp_path)
    assert reason and "302" in reason


def test_edit_staying_under_allowed(tmp_path):
    (tmp_path / "a.py").write_bytes(raw(lines(299) + "mark\n"))
    assert cap.refusal(edit_event(tmp_path, "a.py", "mark\n", "one\n"), tmp_path) is None


def test_replace_all_counted(tmp_path):
    (tmp_path / "a.py").write_bytes(raw("a\n" * 150 + "b\n"))
    many = edit_event(tmp_path, "a.py", "a\n", "a\na\n", replace_all=True)
    reason = cap.refusal(many, tmp_path)
    assert reason and "301" in reason


def test_replace_all_false_counts_one_occurrence(tmp_path):
    (tmp_path / "a.py").write_bytes(raw("a\n" * 150 + "b\n"))
    assert cap.refusal(edit_event(tmp_path, "a.py", "a\n", "a\na\n"), tmp_path) is None


def test_baselined_file_not_growing_allowed(tmp_path):
    (tmp_path / "big.py").write_bytes(raw(lines(400)))
    baseline(tmp_path, {"big.py": 400})
    assert cap.refusal(edit_event(tmp_path, "big.py", "x\nx\n", "y\n"), tmp_path) is None
    same = edit_event(tmp_path, "big.py", "x\nx\n", "y\ny\n")
    assert cap.refusal(same, tmp_path) is None
    assert cap.refusal(write_event(tmp_path, "big.py", lines(400)), tmp_path) is None


def test_baselined_file_growing_refused(tmp_path):
    (tmp_path / "big.py").write_bytes(raw(lines(400)))
    baseline(tmp_path, {"big.py": 400})
    reason = cap.refusal(edit_event(tmp_path, "big.py", "x\nx\n", "y\ny\ny\n"), tmp_path)
    assert reason and "401" in reason
    assert cap.refusal(write_event(tmp_path, "big.py", lines(401)), tmp_path)


def test_unbaselined_long_file_shrinking_still_over_refused(tmp_path):
    (tmp_path / "big.py").write_bytes(raw(lines(400)))
    assert cap.refusal(edit_event(tmp_path, "big.py", "x\nx\n", "y\n"), tmp_path)


def test_uncapped_files_ignored(tmp_path):
    assert cap.refusal(write_event(tmp_path, "uv.lock", lines(900)), tmp_path) is None
    assert cap.refusal(write_event(tmp_path, ".ratchet/x.baseline", lines(900)), tmp_path) is None
    assert cap.refusal(write_event(tmp_path, "blob.bin", "a\0b\n" * 900), tmp_path) is None


def test_multi_edit_counted(tmp_path):
    (tmp_path / "a.py").write_bytes(raw(lines(298) + "m1\nm2\n"))
    event = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(tmp_path / "a.py"),
            "edits": [
                {"old_string": "m1\n", "new_string": "a\nb\n"},
                {"old_string": "m2\n", "new_string": "c\nd\n"},
            ],
        },
    }
    reason = cap.refusal(event, tmp_path)
    assert reason and "302" in reason


def test_unresolvable_edit_fails_open(tmp_path):
    assert cap.refusal(edit_event(tmp_path, "missing.py", "a", "b"), tmp_path) is None
    (tmp_path / "a.py").write_bytes(raw("hello\n"))
    assert cap.refusal(edit_event(tmp_path, "a.py", "absent", "b"), tmp_path) is None


def test_warning_at_threshold(tmp_path):
    (tmp_path / "a.py").write_bytes(raw(lines(270)))
    event = write_event(tmp_path, "a.py", "")
    assert cap.warning(event, tmp_path) == "a.py: 270/300 lines"


def test_warning_silent_below_threshold(tmp_path):
    (tmp_path / "a.py").write_bytes(raw(lines(269)))
    assert cap.warning(write_event(tmp_path, "a.py", ""), tmp_path) is None


def test_warning_silent_for_uncapped(tmp_path):
    (tmp_path / "uv.lock").write_bytes(raw(lines(290)))
    assert cap.warning(write_event(tmp_path, "uv.lock", ""), tmp_path) is None


def test_cli_handlers_emit_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cap, "ROOT", tmp_path)
    assert hooks.pre_edit(write_event(tmp_path, "a.py", lines(301))) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    (tmp_path / "b.py").write_bytes(raw(lines(280)))
    assert hooks.post_edit(write_event(tmp_path, "b.py", "")) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["additionalContext"] == "b.py: 280/300 lines"
    assert hooks.post_edit(write_event(tmp_path, "c.py", "")) == 0
    assert capsys.readouterr().out == ""
