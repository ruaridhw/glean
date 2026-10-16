---
status: accepted
date: 2026-10-15
---

# Every branch is linear, every issue gets its own PR, and plans stay out of git

House rules for how work lands, set during the 2026-10-15 triage build and applying to humans and agents alike:

- **Linear history, always.** Restack by rebasing onto the parent (or `main`) and force-pushing with `--force-with-lease`. Never merge `main` or a parent branch *into* a feature branch, and never amend or squash-rewrite commits — fix forward with a new commit.
- **One issue, one PR.** Even when a lane of work ships as a stack of PRs, each PR closes its own issue, 1:1.
- **Worktrees branch from `origin/main`**, never from a local checkout's state (#137/#139).
- **Plans are ephemeral.** Plan documents, scratch files and migration working papers are not committed; the durable record is the issue, the PR and — for decisions — these ADRs. (The repo's `.gitignore` excludes `docs/*` for this reason, allowlisting only `docs/adr/` and the two standing ops docs.)
- **`delete_branch_on_merge` is on**, and stacks merge through GitHub's native stacked-PR support, base first.

## Considered options

- **Merge commits to restack.** Tried during the build's first hours; the owner called the resulting tangle out and set the linear rule instead.
- **Committing plans for posterity.** Rejected: plans go stale the moment the code moves, and AgentsView plus the PR record already preserve the "why" of a session.
- **Amending to keep branches pretty.** Rejected: a rewritten commit breaks anyone (or any agent) who already fetched it; a new commit is just as clean.

## Consequences

- **Builder and reviewer agents are torn down once a PR passes review** — continuing work resumes from AgentsView history, not a kept-warm session.
- **Housekeeping is part of "done":** merged branches are deleted, and obsolete worktrees are pruned.
- **Force-pushes are normal here,** but only ever with a lease.
