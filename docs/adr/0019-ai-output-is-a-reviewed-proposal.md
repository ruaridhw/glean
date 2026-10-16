---
status: accepted
date: 2026-10-06
---

# AI output is always a proposal the user reviews before anything is saved

Every AI feature in the app — receipt scan, describe-your-pantry, shopping-list parse, recipe import — returns an **ephemeral proposal** that lands on a review screen; nothing the model says is written to the pantry, plan or shopping list until the user confirms. The backend's remote endpoints are treated as *transformations, not resources*: they answer "what do you make of this?", and the commit into local storage is a separate, user-driven act.

The review experience is part of the decision: **one shared review screen** rather than per-feature lookalikes; **honest progress** (a real indicator with timeout and cancel, never fake time-based steps that add delay after the API has already answered); intake is a **modal task** with an explicit cancel, so a mid-scan tab tap can't silently lose a capture; and every intake mode (Scan / Describe / Manual) sits behind one **+** sheet, reachable whether the pantry is empty or full.

## Considered options

- **Save-then-fix.** Rejected: early versions did this in places (pantry-only review unconditionally mutating the shopping list, checkout deleting unmatched rows) and it produced silent data loss.
- **Clarifying questions as a blocking dialog.** Rejected: shopping parse *always proposes* items; the model's questions are optional hints with an answer field, and submitting re-parses the original description plus the answers.

## Consequences

- **Edits on the review screen are preserved** across a re-parse; the review is reconciliation, not a throwaway preview.
- **A parse that yields nothing reviewable** is a bug to surface, not a silent no-op.
- **New AI features inherit the pattern:** endpoint returns a proposal, app shows the shared review, user commits.
