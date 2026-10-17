---
status: accepted
date: 2026-10-15
---

# The Cognito user pool is retained on stack deletion or replacement

On-device data is keyed by each user's Cognito `sub`. If CloudFormation ever deleted or replaced `GleanUserPool` — a stack teardown, or a change to an immutable property — every user would get a new `sub`, and each phone's pantry, plan and shopping list would be orphaned under the old one. The pool therefore carries `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` (#107), so it survives whatever happens to the rest of the stack.

## Considered options

- **No retention.** Rejected: the pool *is* the namespace the local-first data hangs off (ADRs 0005 and 0007); losing it is a data-loss event even though no user data sits in AWS.
- **Keying on-device data by something portable instead.** A larger redesign for a single-user app; retention removes the failure at one line each.

## Consequences

- **Stack deletion leaves the pool behind** as an orphaned resource; deleting it is a deliberate, manual act.
- **Replacement adopts, not recreates:** a new stack must import or reference the retained pool rather than mint a fresh one.
- **This protects identity, not data:** restorability of the data itself is ADR 0007's job.
