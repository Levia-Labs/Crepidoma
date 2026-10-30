"""Estimate the API credit left this billing cycle.

Usage:
    api_balance.py balance [--probe] [--json]
    api_balance.py ledger [--since YYYY-MM-DD] [--top N] [--json]

Env: ANTHROPIC_API_KEY (inference key, for --probe), ANTHROPIC_ADMIN_KEY (optional; cost
report is the spent source when set, else the local ledger), CREPIDOMA_API_CREDIT_USD
(default 200), CREPIDOMA_API_CYCLE_START (YYYY-MM-DD; default the first day of the current
month), CREPIDOMA_API_FLOOR_USD (default 10), CREPIDOMA_API_LEDGER (default
~/.claude/api-ledger.jsonl).

Exit 0 ok, 3 at or under floor, 1 no key or unknown, 2 usage. Keys are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path

API = "https://api.anthropic.com"
VERSION = "2023-06-01"
PROBE_MODEL = "claude-haiku-4-5"


def cycle_start(today: date, env: Mapping[str, str]) -> date:
    raw = env.get("CREPIDOMA_API_CYCLE_START", "").strip()
    if raw:
        return date.fromisoformat(raw)
    return today.replace(day=1)


def ledger_path(env: Mapping[str, str]) -> Path:
    raw = env.get("CREPIDOMA_API_LEDGER", "").strip()
    return Path(raw) if raw else Path.home() / ".claude" / "api-ledger.jsonl"


def append_ledger(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def read_ledger(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries = []
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict):
            entries.append(item)
    return entries


def since_filter(entries: list[dict], since: date) -> list[dict]:
    return [e for e in entries if str(e.get("ts", ""))[:10] >= since.isoformat()]


def ledger_sum(entries: list[dict], since: date) -> float:
    return sum(float(e.get("cost_usd") or 0) for e in since_filter(entries, since))


def per_agent(entries: list[dict], since: date) -> list[tuple[str, float, int]]:
    rows: dict[str, list[float]] = {}
    for entry in since_filter(entries, since):
        row = rows.setdefault(str(entry.get("agent", "?")), [0.0, 0])
        row[0] += float(entry.get("cost_usd") or 0)
        row[1] += 1
    return sorted(((a, c, int(n)) for a, (c, n) in rows.items()), key=lambda r: -r[1])


def parse_cost_page(page: dict) -> float:
    """USD in one cost_report page; amounts are cents as decimal strings."""
    cents = 0.0
    for bucket in page.get("data", []):
        for result in bucket.get("results", []):
            try:
                cents += float(result.get("amount", 0))
            except (TypeError, ValueError):
                continue
    return cents / 100


def _request(url: str, headers: dict, data: bytes | None = None, method: str = "GET"):
    if urllib.parse.urlsplit(url).scheme != "https":
        raise ValueError("https only")
    return urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310


def _call(opener: Callable, request: urllib.request.Request) -> dict:
    with opener(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_cost(opener: Callable, admin_key: str, start: date, now: datetime) -> float:
    total, page = 0.0, None
    while True:
        query = {
            "starting_at": f"{start.isoformat()}T00:00:00Z",
            "ending_at": now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if page:
            query["page"] = page
        url = f"{API}/v1/organizations/cost_report?{urllib.parse.urlencode(query)}"
        headers = {"anthropic-version": VERSION, "x-api-key": admin_key}
        data = _call(opener, _request(url, headers))
        total += parse_cost_page(data)
        page = data.get("next_page")
        if not (data.get("has_more") and page):
            return total


def probe_key(opener: Callable, key: str) -> bool:
    payload = {"model": PROBE_MODEL, "messages": [{"role": "user", "content": "hi"}]}
    headers = {
        "x-api-key": key,
        "anthropic-version": VERSION,
        "content-type": "application/json",
    }
    body = json.dumps(payload).encode("utf-8")
    request = _request(f"{API}/v1/messages/count_tokens", headers, body, "POST")
    try:
        _call(opener, request)
    except (OSError, ValueError):
        return False
    return True


def estimate(env: Mapping[str, str], opener: Callable, today: date, now: datetime) -> dict | None:
    try:
        grant = float(env.get("CREPIDOMA_API_CREDIT_USD") or 200)
        floor = float(env.get("CREPIDOMA_API_FLOOR_USD") or 10)
        start = cycle_start(today, env)
    except ValueError:
        return None
    admin = env.get("ANTHROPIC_ADMIN_KEY", "").strip()
    if admin:
        try:
            spent, source = fetch_cost(opener, admin, start, now), "admin"
        except (OSError, ValueError):
            return None
    else:
        spent = ledger_sum(read_ledger(ledger_path(env)), start)
        source = "ledger"
    return {
        "left": round(grant - spent, 2),
        "grant": grant,
        "spent": round(spent, 2),
        "since": start.isoformat(),
        "source": source,
        "floor": floor,
    }


def format_line(info: dict) -> str:
    line = (
        f"api credit: ${info['left']:.2f} left of ${info['grant']:.2f} "
        f"(spent ${info['spent']:.2f} since {info['since']}, source {info['source']})"
    )
    if "key" in info:
        line += f", key {info['key']}"
    return line


def exit_code(info: dict | None) -> int:
    if info is None:
        return 1
    return 3 if info["left"] <= info["floor"] else 0


def cmd_balance(args, env, opener, now) -> int:
    key = env.get("ANTHROPIC_API_KEY", "").strip()
    if args.probe and not key:
        print("api credit: no ANTHROPIC_API_KEY for --probe", file=sys.stderr)
        return 1
    info = estimate(env, opener, now.date(), now)
    if info is None:
        print("api credit: unknown (bad settings or cost report failed)", file=sys.stderr)
        return 1
    if args.probe:
        info["key"] = "ok" if probe_key(opener, key) else "invalid"
    print(json.dumps(info, sort_keys=True) if args.json else format_line(info))
    return exit_code(info)


def cmd_ledger(args, env, today) -> int:
    try:
        since = date.fromisoformat(args.since) if args.since else cycle_start(today, env)
    except ValueError:
        print("api ledger: bad date", file=sys.stderr)
        return 2
    rows = per_agent(read_ledger(ledger_path(env)), since)
    if args.json:
        print(json.dumps([{"agent": a, "cost_usd": round(c, 4), "runs": n} for a, c, n in rows]))
        return 0
    print(f"api ledger since {since.isoformat()}: {len(rows)} agents")
    for agent, cost, runs in rows[: args.top]:
        print(f"{agent} ${cost:.2f} {runs} runs")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="api_balance", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    bal = sub.add_parser("balance")
    bal.add_argument("--probe", action="store_true")
    bal.add_argument("--json", action="store_true")
    led = sub.add_parser("ledger")
    led.add_argument("--since")
    led.add_argument("--top", type=int, default=20)
    led.add_argument("--json", action="store_true")
    return parser


def main(
    argv: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    opener: Callable = urllib.request.urlopen,
    now: datetime | None = None,
) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    env = os.environ if env is None else env
    now = now or datetime.now(UTC)
    if args.cmd == "balance":
        return cmd_balance(args, env, opener, now)
    return cmd_ledger(args, env, now.date())


if __name__ == "__main__":
    sys.exit(main())
