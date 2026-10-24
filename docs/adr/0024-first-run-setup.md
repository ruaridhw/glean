---
status: accepted
date: 2026-10-06
---

# First run is a short, skippable setup that ends by stocking the pantry

The app's first run is a **short preference setup**: dinners per week, servings, dietary flags, each skippable, each showing the value you've chosen as you set it. This replaced a walkthrough-style onboarding **on purpose** (AC-UX-04): the values drive meal-plan quality, and without being asked they stay at defaults forever. The setup **ends by pointing at receipt-scan** ("Stock your pantry"), because a plan generated against an empty pantry is worthless — but the scan lives at the *end* of the setup, not bolted onto an unrelated page.

Settings echo the same honesty: **auto-save** on change (no dirty-state trap), copy that states these values steer generation, and bounds surfaced before they're violated.

## Considered options

- **A value-prop walkthrough.** Deferred, not rejected: an intro may still be added later, but only *in addition to* the questions — never instead of them, since the setup is what collects what the plan needs.
- **Ask on first Generate instead.** Rejected: that's the moment of highest intent; the answer-gathering belongs earlier and skippably.

The walkthrough question stays open; nothing here precludes adding one later.

## Consequences

- **Onboarding status comes straight from stored config** — there is no separate "has seen onboarding" flag to drift out of sync.
- **The receipt-scan step is also the feature's demo:** the first thing the app does for you is turn paper into a pantry.
- **A "Describe your pantry" alternative belongs beside "Scan a receipt"** on that last step (ported from the Expo-era onboarding work, #74).
- **Amended by ADR 0027:** the taste interview sits between the basics and the pantry, still skippable, and still ending by stocking the pantry.
