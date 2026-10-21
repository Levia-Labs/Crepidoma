# Models

1. Main thread: Opus (`claude-opus-5-5`), pinned by `"model"` in committed settings; it orchestrates.
2. Working subagents: Sonnet (`sonnet`). Committed settings set `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` as the default; agent frontmatter and the Agent `model` parameter override it.
3. Grep, read, locate, small lookups, classification and graphify LLM indexing: Haiku (`haiku`), through the `scout` agent.
4. The PreToolUse hook refuses subagents on Opus or the inherited main model, and every dispatch while `CLAUDE_CODE_SUBAGENT_MODEL` names anything but sonnet or haiku.
5. Usage ceiling 95 percent of any window: check `task claude:budget:check` before a batch; launch nothing at the ceiling.
