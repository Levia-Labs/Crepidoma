# Models

1. Run the main thread on Opus (`claude-opus-5-5`).
2. Run every subagent on Sonnet (`claude-sonnet-5-5`), pinned in committed settings, agent frontmatter and each Agent call.
3. Use Haiku only for classification and graph indexing; never a heavier model there.
4. Never change a model per session.
5. Check usage allowance before a batch of agents. Launch none at 95 percent of any usage window.
