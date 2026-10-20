# Tool-first loop

1. Make each model turn a tool call with chosen parameters. Tool output is the minimum the next decision needs: pass or fail, counts, ids, failing lines, a receipt. Fix a tool that prints more.
2. Never read content to hand-write a single-use result. Query tools before reading files; check what the code already does before acting on a decision.
3. No tool for the job: write a parametrized one first (script, test, task entry with a description and usage line), then call it. No throwaway inline scripts, interpreter one-liners or heredoc scripts.
4. Use named, single-job subagents only. Never use general-purpose, catch-all, fork, Explore or Plan agents. None fits: write one first.
5. Keep briefs short: point at the agent definition, name the tool calls, the receipt and the paths the agent owns. Give each agent only the tools it uses.
6. An agent calls tools and returns a receipt of at most 10 lines, never file contents.
7. Run at most 6 concurrent subagents, each on paths disjoint from every other.
8. Never let the main thread receive more than 20 lines or 1 KB of raw output per call. No `cat`, long `head`, `tail` or `sed -n`, whole-file reads or task output-file reads; a guard refuses raw reads in the main thread.
9. Qualify a large file with `digest <file>` first, a small-model agent second.
10. Never re-read a file after editing it; the edit errors if it failed.
11. Audit session spend; turn repeated ad-hoc work into a tool.
