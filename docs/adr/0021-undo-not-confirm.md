---
status: accepted
date: 2026-10-06
---

# Destructive actions are undoable through a snackbar, never gated behind a confirm dialog

Every destructive action in the app — delete, check-off, checkout — commits immediately and offers **Undo** in a snackbar, rather than asking "are you sure?" first. Fewer taps, and recoverable. This includes **"Cooked"**, which decrements pantry quantities: the delta is stored so Undo can reverse it exactly. Deletes are **swipe-only** (`Dismissible`), one gesture per row — no row carries two delete affordances.

Undo snackbars **auto-dismiss after five seconds** (#111/#140): an Undo that lingers forever trains the user to ignore it, and the action it offers is time-sensitive anyway.

## Considered options

- **Confirm dialogs.** Rejected: they add a tap to every routine action and, being routine, get dismissed on autopilot — protection in neither direction.
- **Undo only for "big" actions.** Rejected: the line is unenforceable; the rule is cheap precisely because it's universal.

## Consequences

- **Undo must be exact,** not approximate: it restores complete identity, linked shopping rows and cooked state, so the implementation stores what it needs at commit time.
- **Checkout is destructive and follows the same rule** — and it only removes rows the receipt actually resolved; unmatched checked items survive (and become pantry stock via "Done shopping", #108).
- **A snackbar that can't undo everything the action did** is a bug, not a copy problem.
