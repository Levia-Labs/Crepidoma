import subprocess
from pathlib import Path

import jscpd_pct
import yaml

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "jscpd-report.json"
TASKFILE = ROOT / "taskfiles" / "quality" / "Taskfile.yml"


def quality_task(name: str) -> dict:
    return yaml.safe_load(TASKFILE.read_text(encoding="utf-8"))["tasks"][name]


def test_parse_percentage_reads_total():
    assert jscpd_pct.parse_percentage(FIXTURE.read_text(encoding="utf-8")) == 4.99


def test_main_accepts_report_dir_and_prints_percent(capsys):
    assert jscpd_pct.main([str(FIXTURE.parent)]) == 0
    assert jscpd_pct.main([str(FIXTURE)]) == 0
    assert capsys.readouterr().out.split() == ["4.99", "4.99"]


def test_main_fails_on_malformed_report(tmp_path):
    bad = tmp_path / "jscpd-report.json"
    bad.write_text('{"statistics": {}}', encoding="utf-8")
    assert jscpd_pct.main([str(tmp_path)]) == 1


def test_duplication_step_uses_json_report_not_console_grep():
    text = "\n".join(quality_task("duplication")["cmds"])
    assert "--reporters json" in text
    assert "mktemp -d" in text
    assert "trap" in text
    assert "grep 'Total'" not in text
    assert "jscpd_pct.py" in text


def test_bandit_excludes_vendored_crepidoma():
    data = yaml.safe_load(TASKFILE.read_text(encoding="utf-8"))
    exclude = data["vars"]["QUALITY_BANDIT_EXCLUDE"].split(",")
    assert "*/.crepidoma/*" in exclude
    assert "*/.worktrees/*" in exclude
    assert "./.crepidoma" in exclude
    assert "QUALITY_BANDIT_EXCLUDE" in "\n".join(quality_task("bandit")["cmds"])
    assert not (ROOT / "tools" / ".crepidoma").exists()


def test_quality_steps_are_posix_sh():
    for name in ("duplication", "bandit"):
        script = "\n".join(quality_task(name)["cmds"])
        script = script.replace("{{.QUALITY_DUP_THRESHOLD}}", "10")
        script = script.replace("{{.QUALITY_BANDIT_EXCLUDE}}", "x")
        script = script.replace("{{.QUALITY_TOOLS}}", "t")
        result = subprocess.run(
            ["sh", "-n"], input=script, capture_output=True, text=True, encoding="utf-8"
        )
        assert result.returncode == 0, result.stderr
        assert "[[" not in script
