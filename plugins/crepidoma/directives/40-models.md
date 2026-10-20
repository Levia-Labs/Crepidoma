# Models

1. Run the main thread on Opus (`claude-opus-5-5`). Committed settings pin it with `"model": "claude-opus-5-5"`.
2. Run every working subagent on Sonnet (`claude-sonnet-5-5`, alias `sonnet`): agent frontmatter and each Agent call name it. The PreToolUse hook refuses any subagent on Opus or on the inherited main-thread model.
3. Run grep, read, locate and other small lookups on Haiku (`claude-haiku-5-5`, alias `haiku`) through the `scout` agent; classification and graph indexing also run on Haiku. Never use a heavier model there.
4. Never set `CLAUDE_CODE_SUBAGENT_MODEL`: it overrides the Haiku tier.
5. Never change a model per session.
6. Check usage allowance before a batch of agents. Launch none at 95 percent of any usage window.
