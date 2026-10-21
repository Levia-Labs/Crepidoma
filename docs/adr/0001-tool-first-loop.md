# 0001. The model calls tools; tools return only what the next decision needs

## Status

Accepted, 2026-10-20. Supersedes the per-pillar ADRs on this topic.

## Context

Work is done by a model in a loop: decide, act, read the result, decide again. Every turn
re-reads the whole context, so cost grows with what has been pasted into it, not with the
work done. Session audits showed the same shape everywhere:

1. 98 percent of session tokens were cache reads. One session carried 99.7 million cached
   tokens in its main context; the first turn of another already held 58.9 thousand tokens
   before any file was opened.
2. 33 of 34 subagents in one pillar were `general-purpose` and consumed 32.2 million tokens,
   976 thousand each. Briefs (2-4 KB) and reports (1-10 KB) were small; the turns were not.
   Each agent oriented itself by reading 50-220 KB of files and paid for them on every later
   turn. One reviewer spent 968 thousand tokens to return 8.6 thousand characters.
3. The same configuration, task and instruction files were read whole 6 to 8 times per
   session, and full gate logs were read on every run.
4. The main thread wrote dozens of inline and scratchpad scripts, each run once and thrown
   away.

The waste has one form: a model reads content to hand-write a single-use answer that a
parametrized tool would have produced in a line. Instructions alone did not stop it; the
sessions above ran under instructions that already said to ask tools first. Shorter briefs
and "be concise" prompts do not address it, because the brief is not where the tokens go. A
per-agent token cap does not exist to set, and stopping an agent mid-edit loses its work.

## Decision

1. The model's output is a tool call with chosen parameters. A tool's output is the minimum
   the next decision needs: a pass is one line, a listing is one line per item, a failure is
   the lines that explain it. The model does not read content to hand-write a single-use
   result.
2. A job with no tool gets one before it is done the first time: a parametrized script under
   the repository's task directory, grouped by domain, with its test and a task-runner entry
   carrying a `Usage:` line. Then the tool is called. No inline or throwaway scripts against
   repository data. A dedicated tool-builder agent writes these.
3. Subagents are named, single-job agents defined in the repository's agent directory or
   provided by a plugin. `general-purpose`, `claude`, `fork`, `Explore`, `Plan` and an agent
   call with no type are refused. When no agent fits, one is written first.
4. Subagents run on a smaller model than the orchestrator. A dispatch with a missing or
   orchestrator-tier model is refused; a brief that seems to need one needs sharpening.
5. A subagent calls tools and returns a receipt of at most 10 lines, never file contents. No
   agent is exempt.
6. At most 6 subagents run at once. Parallel agents share one checkout, so each owns disjoint
   paths and commits with `git commit -- <paths>`. The pre-commit hook formats only staged
   files.
7. A brief names the tool calls the agent should make and the receipt it should return, not
   the files it should read.
8. Reads are targeted. An outline tool lists a file's functions, headings or tasks with line
   numbers so a read takes an offset and limit. Gate runs report one line per gate plus the
   decisive lines of a failure, and keep the full log on disk for a targeted read.
9. Permissions allow the task runner as a whole, with no per-task allow rules. A check fails
   on a redundant rule, a deny rule without its compressed-output twin, or an unwired agent
   hook.
10. A pre-dispatch hook enforces rules 3, 4 and 6. It reserves a slot at dispatch, holds it
    until the subagent stop event, and releases a slot untouched for 3 hours. A reset task
    frees slots left by a crashed session.
11. A token-accounting task reports where a session spent: totals, heaviest tool results,
    each dispatch's prompt and result size.

## Consequences

1. A new kind of job costs a script and a test before it costs a result. The second run is
   nearly free.
2. Work with no fitting agent waits until one is written. A new agent definition is not
   dispatchable until the harness reloads it; until then the nearest specific named plugin
   agent is used, never a catch-all.
3. Agents stay small: their context holds task output, not files. The orchestrator's job is
   choosing calls and reading receipts.
4. Truly one-off work, such as reading an unfamiliar upstream source before adopting it,
   still needs a read. The rule is to read a part, not to never read.
5. The type and model rules need no ledger and always apply. The concurrency count depends on
   files the harness writes; if those are missing or change shape, the cap fails open and
   never blocks. Slots are reserved at dispatch, not when the harness first records the
   agent, so the cap holds inside a single batch of dispatches, not only across batches.
6. The rules live in a hook, so they hold in every session whether or not the model
   remembers this record. A named agent's contract is a reviewed file; a general agent's
   prompt is rewritten on every dispatch and drifts.
7. The allowlist is no longer an index of tasks; the task runner's listing is.
