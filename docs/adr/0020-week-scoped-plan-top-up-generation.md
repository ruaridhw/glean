---
status: accepted
date: 2026-10-06
---

# The plan is week-scoped, uncooked meals roll forward, and generation only ever tops up

The Plan tab is **a week, with pagination** — not a lifetime list. `planned_date` is load-bearing: cooked meals stay visible in their week but stop counting towards "left to plan", and **uncooked meals roll forward** into the new week, oldest first, filling only its remaining capacity. Rollover is idempotent, so reopening the app on a Monday never duplicates entries. This replaced a model where "This Week" had no date filter and capacity was gated on *lifetime* entry count — which after a few weeks made "Plan full" block every add, permanently.

**Generation is top-up only.** Generate fills empty slots and never replaces or moves entries the user (or a previous generation) placed. Capacity is re-checked at persistence time, and Generate stays disabled from tap to finish. Rejecting a plan wholesale means deleting meals individually — acceptable because every delete carries Undo (ADR 0021).

## Considered options

- **Regenerate-the-week.** Rejected: it would silently discard deliberate choices the user already made; top-up keeps the user in charge of the week.
- **Day-mapped slots.** Deferred deliberately: it forces decisions about skipped days and drag-reordering — a feature effort, not part of the core loop.
- **Rollover of everything uncooked, unlimited.** Rejected: per-week capacity naturally limits accumulation; a meal ignored for weeks still rolls, but it can't crowd out a fresh week.

## Consequences

- **Adding a meal by hand targets the week being viewed**, with a guard against double-taps and a transactional capacity check.
- **A meal deleted from the plan removes its shopping rows;** deleting a *recipe* keeps plan entries — they snapshot what you're cooking and just lose the link.
- **`meals_per_week` (dinners) and servings are first-class settings** that generation actually honours; the first-run setup asks for them (ADR 0024) rather than leaving defaults forever.
