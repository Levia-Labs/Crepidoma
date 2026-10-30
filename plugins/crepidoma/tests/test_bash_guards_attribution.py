import hooks_bash_guards as guards
import pytest

TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"
GENERATED = "Generated with [Claude Code](https://claude.com/claude-code)"
REFUSED = [
    f'git commit -m "feat: x\n\n{TRAILER}"',
    f"git commit -m \"$(cat <<'EOF'\nfeat: x\n\n{TRAILER}\nEOF\n)\"",
    f'task git:commit -- "feat: x\n\n{TRAILER}"',
    f'gh pr create --title t --body "{GENERATED}"',
    f"gh pr edit 3 --body '{GENERATED}'",
    'gh pr create --title "Generated with Claude Code" --body b',
    f'gh issue create --title t --body "{GENERATED}"',
    f'gh release create v1 --notes "{GENERATED}"',
    f"bash -c 'gh pr create --body \"{GENERATED}\"'",
]
ALLOWED = [
    'task git:commit -- "feat: x\n\nCo-Authored-By: Jane <jane@example.com>"',
    'gh pr create --title t --body "plain body"',
    'gh issue create --title t --body "plain"',
    'gh release create v1 --notes "notes"',
    f'echo "{TRAILER}"',
    f"gh pr view 3 --comments # {GENERATED}",
    "grep -r 'Generated with Claude Code' docs",
]


@pytest.mark.parametrize("command", REFUSED)
def test_refuses_attribution(command):
    reason = guards.bash_refusal(command)
    assert "AI attribution" in reason
    assert "30-conventions" in reason


@pytest.mark.parametrize("command", ALLOWED)
def test_allows_clean_or_unrelated(command):
    assert "AI attribution" not in guards.bash_refusal(command)
