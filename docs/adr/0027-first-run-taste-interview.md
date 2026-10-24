---
status: accepted
date: 2026-10-24
---

# First run gains the taste interview, between the basics and the pantry

First run keeps ADR 0024's three properties — short, skippable, ending by stocking the pantry — and
gains one page: a **taste interview** between the basics and the pantry step. The basics still collect
what generation needs to be safe (dinners, servings, dietary flags); the interview collects what makes a
plan feel right (favourite dinners, loved and disliked ingredients and cuisines, spice tolerance, habits,
who eats). Each page stays skippable, and skipping it leaves the defaults as they were.

The interview is **chat-style with a fixed spine**: five openers in a fixed order — three dinners, never
want, love, how the weeks go, who's at the table — then at most two follow-ups the model chooses from what
was said. Seven questions, capped server-side. The openers are fixed because the profile's fields are
known in advance: a fixed opener fills each one, needs no model call, and produces an answer the backend can
read deterministically. The follow-ups are what the model is for: they chase what the household actually
said, which a fixed script can't anticipate.

`POST /profile/interview` is **stateless** (the app sends the transcript and its draft profile on every
turn) and returns either the next question or `done` with the finished profile and a two-line summary to
confirm. The profile is versioned JSON stored on the device — one row per user — so its shape can grow
without a database migration each time. Favourite dinners are matched to corpus recipes by title search and
carry the `recipe_id` when the match is confident, `null` when it isn't: the household's own words are always
kept, and an unmatched favourite is still a favourite.

Every free-text answer passes the **injection screen** first (ADR 0010's decision model, one `noul`
question at 0.9, spec §6.1). A dropped answer never reaches the model and is what "Couldn't use that
answer" means on screen. The screen fails closed: a timeout or a broken answer drops the note too.

## Considered options

- **A model-driven conversation with no fixed openers.** Rejected: the profile's fields are known, so a
  fixed opener covers each one deterministically and for free, and the model is left for the part it is
  good at — the follow-up. It also means an interview that never reaches the model still produces a profile.
- **Ask during the first Generate instead.** Rejected for the reasons in ADR 0024: the moment of highest
  intent is the wrong moment to gather preferences, and the interview belongs where every other preference
  is collected.
- **A retake as an update, from Settings.** Not rejected, only parked (spec §9): it needs real profiles to
  reconcile against, so it follows the profile screen (V14).
- **Screening inside the model's own prompt ("ignore instructions in answers").** Rejected: it is the
  anti-goal in spec §3, and a screened answer given as data in a typed field is what the prompt can rely on.

## Consequences

- **The profile never duplicates `UserConfig`.** Dinners per week, servings, dietary flags and the time cap
  stay in config; this ADR adds no second home for them.
- **An interview costs at most three model calls** (the last three turns), because the openers need none.
- **The screen is reusable.** It lives apart from the interview (`glean.screening`), so the feedback strip
  and swap notes (V9, V10) ask the same question at the same bar rather than growing their own.
- **The bar is calibrated, not guessed.** `backend/tests/fixtures/screening_calibration.json` is a committed
  labelled set of benign and injected notes, and `backend/scripts/eval_screening.py` measures the shipped
  bar against the pinned decision model. A change to the question or the bar is a paid run, not an opinion.
