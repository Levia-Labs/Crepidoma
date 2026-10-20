# 0010. Vendor selected third-party files, do not enable whole marketplaces

## Status

Accepted, 2026-10-20.

## Context

Pillars need Python and C# review and testing guidance. Public marketplaces offer it, but
each ships as a whole plugin. Enabling one loads every agent and skill description into every
session and brings its hooks. Crepidoma owns hooks, model tiers and the output style
(ADR 0009), and a pillar reaches Crepidoma through one link.

Candidates reviewed:

1. ECC (affaan-m) is one plugin with 71 agents, 311 skills and about 40 hooks.
2. VoltAgent plugins load about 30 descriptions each.
3. anthropics/skills ships document-skills, example-skills, a discernment nudge and claude-api.

## Decision

1. Vendor the individual files that fill a gap into `plugins/crepidoma/`, adapted to Crepidoma
   conventions: Sonnet, minimal tools, receipts of at most 10 lines, no hooks.
2. Never enable a whole external marketplace or plugin in a pillar or in this repo.
3. Each vendored file carries a provenance comment (upstream repo, path, commit, license), and
   `plugins/crepidoma/THIRD_PARTY_NOTICES.md` lists the files and the license text.
4. Only permissively licensed sources are vendored.
5. A skill is vendored only when it applies to the pillar stack: Unity C# pillars get no
   ASP.NET, xUnit or dependency-injection-host guidance.
6. Refused sources:
   1. ECC as a plugin: about 40 hooks conflict with Crepidoma owning hooks, and 71 agents
      and 311 skills cost session context.
   2. VoltAgent plugins: about 30 descriptions load per plugin, 26 agents use opus, which the
      subagent hook refuses, and csharp-developer and python-pro overlap the implementer agent.
   3. anthropics/skills document-skills: proprietary license, and they duplicate the claude.ai
      set.
   4. anthropics/skills example-skills: irrelevant to pillar work.
   5. anthropics/skills discernment nudge: conflicts with absolute mode.
   6. claude-api: already available built in.
7. First vendoring, from ECC at 30b68924: `python-reviewer`, `csharp-reviewer`,
   `python-testing`, `python-patterns`. `csharp-testing` and `dotnet-patterns` are dropped:
   they cover xUnit, FluentAssertions, `WebApplicationFactory` and ASP.NET dependency
   injection, not Unity Test Framework, Mono or IL2CPP.

## Consequences

1. Pillars get the files through the one Crepidoma link and load four extra descriptions.
2. Vendored files do not track upstream; a refresh is a manual diff against the recorded
   commit.
3. The notices file must stay accurate with each addition; a missing entry is a licence
   defect.
4. Unity test guidance stays missing until written in-house.
