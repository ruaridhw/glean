---
status: accepted
date: 2026-10-24
---

# First run gains a taste interview between the basics and the pantry

First run keeps ADR 0024's shape — short, skippable, ending by stocking the pantry — and gains a page
between the basics and the pantry: a **taste interview**, chat-style, with a fixed spine. Five openers in a
fixed order (three dinners → favourite meals; never want → disliked ingredients and avoided cuisines; love →
loved ingredients and liked cuisines; how the weeks go → habits; who's at the table → household), then at
most two follow-ups the model chooses. Seven questions, capped server-side, every turn skippable.

The openers are fixed because the profile's fields are known in advance: each fills one deterministically
and needs no model call, so an interview that never reaches the model still produces a profile.

`POST /profile/interview` is stateless (the app sends the transcript and its draft profile on every turn) and
returns either the next question or `done` with the profile and a two-line summary to confirm. The profile is
versioned JSON on the device, one row per user. Favourite dinners are matched to a corpus recipe when a title
starts with the household's own words; otherwise the words are kept and `recipe_id` is null.

## What the model is given, and what it costs

Every answer is screened before any model reads it (ADR 0010's decision model, one `noul` question at the
0.9 bar — spec §6.1, §6.2 — failing closed). Screens are cached per container (bounded, ten-minute TTL, an
outage never cached) and run concurrently under an 8 s budget, so a request costs at most seven decision
calls plus one model turn: about 18 s against the 30 s request cap. A full interview is three model turns
and, on one container, seven decision calls (22 if every turn cold-starts a container).

The model is given the screened answers as data in typed fields, plus the draft profile's **enum fields
only** (spice tolerance, protein targets). The draft's free text — meal names, ingredient and cuisine lists,
habits, household — is never sent, because a stateless endpoint can't know the app's own draft was screened;
it is merged back into the profile after the call. The model may add to the profile but never delete from it.

The 0.9 bar is **not yet calibrated**: `backend/tests/fixtures/screening_calibration.json` (80 synthetic
notes, half benign, half injections) and `backend/scripts/eval_screening.py` exist to measure it, and the
owner runs that paid command before the bar is trusted.

## Considered options

- **A model-driven conversation with no fixed openers.** Rejected: the fields are known, so a fixed opener
  covers each one for free.
- **Ask during the first Generate.** Rejected for ADR 0024's reasons: the moment of highest intent is the
  wrong time to gather preferences.
- **Screening inside the model's prompt.** Rejected: it is the anti-goal in spec §3.
- **A "screened" token per answer so later turns needn't re-screen.** Deferred: it changes the app contract,
  and the cache already takes most of that cost.
- **A retake as an update.** Parked (spec §9): it needs real profiles to reconcile against.

## Consequences

- **The profile never duplicates `UserConfig`**: dinners, servings, dietary flags and the time cap stay in
  config.
- **The screen is reusable**: it lives in `glean.screening`, so the feedback strip and swap notes (V9, V10)
  ask the same question at the same bar.
- **Changing the bar, the question or the pinned model is a paid measurement**, not an opinion.
- **An unmatched favourite is still a favourite**: the words are kept, only the recipe id is null.

## Evidence

- Spec §6.4C (profile and interview), §6.1 "Confidence bars" (the screen at 0.9), §6.2 "Free-text screening",
  §3 anti-goals ("Free text reaching a model unscreened"), §10 V13 row.
- ADRs 0010 (pinned decision model), 0012, 0019, 0024 (first run, amended by this record).
- V13 closes #7 and PR #74 (spec §10, "Housekeeping"); built on the V12 stack (PR #189) on
  `feature/v13-taste-interview`.
