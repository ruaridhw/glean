---
status: accepted
date: 2026-10-06
---

# First run is a short, skippable setup — not a walkthrough — and it ends by stocking the pantry

The app's first run is a **short preference setup**, not a product tour: dinners per week, servings, dietary flags, each skippable, each showing the value you've chosen as you set it. This replaced a walkthrough-style onboarding **on purpose** (AC-UX-04): the values drive meal-plan quality, and without being asked they stay at defaults forever. The setup **ends by pointing at receipt-scan** ("Stock your pantry"), because a plan generated against an empty pantry is worthless — but the scan lives at the *end* of the setup, not bolted onto an unrelated page.

Settings echo the same honesty: **auto-save** on change (no dirty-state trap), copy that states these values steer generation, and bounds surfaced before they're violated.

## Considered options

- **A value-prop walkthrough.** Rejected: it teaches nothing the app needs and collects nothing the plan needs; a later pass may add a short intro, but never at the cost of the questions.
- **Ask on first Generate instead.** Rejected: that's the moment of highest intent; the answer-gathering belongs earlier and skippably.

## Consequences

- **Onboarding status comes straight from stored config** — there is no separate "has seen onboarding" flag to drift out of sync.
- **The receipt-scan step is also the feature's demo:** the first thing the app does for you is turn paper into a pantry.
- **A "Describe your pantry" alternative belongs beside "Scan a receipt"** on that last step (ported from the Expo-era onboarding work, #74).
