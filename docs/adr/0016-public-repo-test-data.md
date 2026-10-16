---
status: accepted
date: 2026-10-14
---

# Eval fixtures are real, redacted receipts — and the repo is public, so no personal data ever stays in it

Receipt-scan evals run against **photos of the owner's real receipts**, because synthetic fixtures don't reproduce glare, shadow and crumple (#116/#150). The bargain that makes that acceptable: the repo is **public**, so every committed photo is **redacted first** (store location, dates, times, card digits), and when a first commit missed the timestamp and store lines, the files were **purged from git history**, not just edited in a later commit. The same rule covers the expected-output JSON beside each photo.

## Considered options

- **Synthetic or hand-typed receipts.** Rejected: they don't exercise the failure modes the owner actually hits at the till.
- **Redact going forward without a history rewrite.** Rejected: the repo is public; a later commit doesn't unpublish the earlier one.

## Consequences

- **Redaction is checked before any fixture branch is pushed or a PR opened** — the coordinator held a branch locally until the purge was done.
- **Scorers match deterministically** (no fuzzy string matching: "eggs" must not match "eggplant"), because flaky matching hid real redaction and parsing bugs.
- **Any future fixture from real life** (screenshots, exports) follows the same rule: redact, review, then commit.
