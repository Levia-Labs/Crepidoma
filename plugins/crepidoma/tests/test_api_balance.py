import io
import json
import urllib.error
from datetime import UTC, date, datetime

import api_balance
import pytest

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
KEY = "sk-ant-api03-SECRETKEY"
ADMIN = "sk-ant-admin01-SECRETADMIN"


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_opener(pages, calls=None):
    queue = list(pages)

    def opener(request, timeout=None):
        if calls is not None:
            calls.append(request)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return Resp(json.dumps(item).encode("utf-8"))

    return opener


def page(cents, more=False, nxt=None):
    results = [{"amount": str(c)} for c in cents]
    return {"data": [{"results": results}], "has_more": more, "next_page": nxt}


def env_for(tmp_path, **extra):
    return {"CREPIDOMA_API_LEDGER": str(tmp_path / "l.jsonl"), **extra}


def seed(tmp_path, rows):
    for ts, agent, cost in rows:
        api_balance.append_ledger(
            tmp_path / "l.jsonl", {"ts": ts, "agent": agent, "cost_usd": cost}
        )


def test_cycle_start_default_and_env():
    assert api_balance.cycle_start(date(2026, 10, 30), {}) == date(2026, 10, 1)
    env = {"CREPIDOMA_API_CYCLE_START": "2026-10-15"}
    assert api_balance.cycle_start(date(2026, 10, 30), env) == date(2026, 10, 15)


def test_cycle_start_bad_value():
    with pytest.raises(ValueError):
        api_balance.cycle_start(date(2026, 10, 30), {"CREPIDOMA_API_CYCLE_START": "x"})


def test_ledger_path_env_and_default(tmp_path):
    assert api_balance.ledger_path({"CREPIDOMA_API_LEDGER": str(tmp_path / "a")}) == tmp_path / "a"
    assert api_balance.ledger_path({}).name == "api-ledger.jsonl"


def test_ledger_append_read_sum_since(tmp_path):
    seed(tmp_path, [("2026-09-30T10:00:00+00:00", "a", 5), ("2026-10-02T10:00:00+00:00", "a", 1.5)])
    (tmp_path / "l.jsonl").open("a", encoding="utf-8").write("garbage\n")
    entries = api_balance.read_ledger(tmp_path / "l.jsonl")
    assert len(entries) == 2
    assert api_balance.ledger_sum(entries, date(2026, 10, 1)) == 1.5
    assert api_balance.ledger_sum(entries, date(2026, 9, 1)) == 6.5


def test_read_ledger_missing(tmp_path):
    assert api_balance.read_ledger(tmp_path / "none") == []


def test_per_agent_sorted():
    rows = [
        {"ts": "2026-10-02", "agent": "a", "cost_usd": 1},
        {"ts": "2026-10-03", "agent": "b", "cost_usd": 3},
        {"ts": "2026-10-04", "agent": "a", "cost_usd": 1},
    ]
    assert api_balance.per_agent(rows, date(2026, 10, 1)) == [("b", 3.0, 1), ("a", 2.0, 2)]


def test_parse_cost_page_cents_to_usd():
    assert api_balance.parse_cost_page(page([150, "250.5", "bad"])) == pytest.approx(4.005)
    assert api_balance.parse_cost_page({}) == 0


def test_fetch_cost_paginates():
    calls = []
    opener = fake_opener([page([1000], True, "tok"), page([500])], calls)
    assert api_balance.fetch_cost(opener, ADMIN, date(2026, 10, 1), NOW) == 15.0
    assert "page=tok" in calls[1].full_url
    assert "starting_at=2026-10-01T00%3A00%3A00Z" in calls[0].full_url
    assert calls[0].get_header("X-api-key") == ADMIN
    assert calls[0].get_header("Anthropic-version") == "2023-06-01"


def test_balance_ledger_source(tmp_path, capsys):
    seed(tmp_path, [("2026-10-02T10:00:00+00:00", "a", 20)])
    code = api_balance.main(["balance"], env_for(tmp_path), fake_opener([]), NOW)
    out = capsys.readouterr().out.strip()
    assert code == 0
    assert (
        out == "api credit: $180.00 left of $200.00 (spent $20.00 since 2026-10-01, source ledger)"
    )


def test_balance_admin_source(tmp_path, capsys):
    env = env_for(tmp_path, ANTHROPIC_ADMIN_KEY=ADMIN)
    code = api_balance.main(["balance"], env, fake_opener([page([5000])]), NOW)
    assert code == 0
    assert "spent $50.00" in capsys.readouterr().out
    assert "source admin" in api_balance.format_line(
        api_balance.estimate(env, fake_opener([page([1])]), NOW.date(), NOW)
    )


@pytest.mark.parametrize("spent,code", [(189, 0), (190, 3), (195, 3)])
def test_floor_exit_codes(tmp_path, spent, code):
    seed(tmp_path, [("2026-10-02T10:00:00+00:00", "a", spent)])
    assert api_balance.main(["balance"], env_for(tmp_path), fake_opener([]), NOW) == code


def test_admin_failure_is_unknown(tmp_path):
    env = env_for(tmp_path, ANTHROPIC_ADMIN_KEY=ADMIN)
    opener = fake_opener([urllib.error.URLError("down")])
    assert api_balance.main(["balance"], env, opener, NOW) == 1


def test_probe_without_key_is_one(tmp_path):
    assert api_balance.main(["balance", "--probe"], env_for(tmp_path), fake_opener([]), NOW) == 1


@pytest.mark.parametrize(
    "reply,word", [({"input_tokens": 1}, "ok"), (urllib.error.URLError("x"), "invalid")]
)
def test_probe_result_never_prints_key(tmp_path, capsys, reply, word):
    env = env_for(tmp_path, ANTHROPIC_API_KEY=KEY, ANTHROPIC_ADMIN_KEY=ADMIN)
    opener = fake_opener([page([100]), reply])
    api_balance.main(["balance", "--probe"], env, opener, NOW)
    cap = capsys.readouterr()
    assert f"key {word}" in cap.out
    assert KEY not in cap.out + cap.err
    assert ADMIN not in cap.out + cap.err


def test_json_output(tmp_path, capsys):
    api_balance.main(["balance", "--json"], env_for(tmp_path), fake_opener([]), NOW)
    data = json.loads(capsys.readouterr().out)
    assert data["left"] == 200 and data["source"] == "ledger"


def test_usage_errors_are_two(tmp_path):
    assert api_balance.main(["nope"], env_for(tmp_path), fake_opener([]), NOW) == 2
    assert api_balance.main(["ledger", "--since", "bad"], env_for(tmp_path), None, NOW) == 2


def test_bad_settings_unknown(tmp_path):
    env = env_for(tmp_path, CREPIDOMA_API_CREDIT_USD="abc")
    assert api_balance.main(["balance"], env, fake_opener([]), NOW) == 1


def test_ledger_command_caps_lines(tmp_path, capsys):
    seed(tmp_path, [("2026-10-02T10:00:00+00:00", f"a{i}", i) for i in range(30)])
    assert api_balance.main(["ledger"], env_for(tmp_path), None, NOW) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 21
    assert lines[1].startswith("a29 $29.00")


def test_ledger_command_since(tmp_path, capsys):
    seed(tmp_path, [("2026-09-02T10:00:00+00:00", "old", 4)])
    api_balance.main(["ledger", "--since", "2026-10-01", "--json"], env_for(tmp_path), None, NOW)
    assert json.loads(capsys.readouterr().out) == []
