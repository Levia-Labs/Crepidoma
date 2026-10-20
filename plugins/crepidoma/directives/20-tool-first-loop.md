# Tool-first loop

1. Make each model turn a tool call with chosen parameters. Tool output is the minimum the next decision needs: pass or fail, counts, ids, failing lines, a receipt. Fix a tool that prints more.
2. Never read content to hand-write a single-use result. Query tools before reading files; check what the code already does before deciding.
3. No tool for the job: write a parametrized one first (script, test, task entry with description and usage line), then call it. No throwaway inline scripts, one-liners or heredocs.
4. Use named, single-job subagents and the specific skill for each job. Never use general-purpose, catch-all, fork, Explore or Plan agents. None fits: write the agent or skill first.
5. Keep briefs short: point at the agent definition, name the tool calls, receipt and owned paths. Give each agent only the tools it uses.
6. Agents call tools and return a receipt of at most 10 lines, never file contents.
7. Run at most 6 concurrent subagents, on disjoint paths.
8. Never let the main thread receive more than 20 lines or 1 KB of raw output per call. No `cat`, long `head`, `tail` or `sed -n`, whole-file reads or task output-file reads; a guard refuses raw reads.
9. Qualify a large file with `digest <file>` first, a small-model agent second.
10. Never re-read a file after editing; the edit errors on failure.
11. Audit session spend; turn repeated ad-hoc work into a tool.
12. Before optimizing a repo, finish and retire running lanes, then mine session history for repeated work and turn it into tools, tasks, skills and ADRs that parallel subagents can call.
