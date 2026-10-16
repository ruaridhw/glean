---
status: accepted
date: 2026-10-06
---

# The app is Flutter; the Expo app is gone

The mobile app is the Flutter app in `app/`; the Expo/React Native app in `mobile/` was deleted when the port landed (#102). The port began in July 2026 because the Expo app had stalled short of MVP, and it shipped once it could run the owner's daily flows against prod. The Flutter app stays **local-first**: pantry, plan and shopping list live in an on-device SQLite database (drift), and the backend stays a stateless API in front of the catalogue and the LLM features.

The port initially carried over too much of the Expo app's structure, so it was immediately put through an extreme-YAGNI simplification (#127): seams with a single adapter were collapsed, duplicated widgets and flows were folded into one, and the migration's working papers (`FLUTTER_MIGRATION.md`, scratch audits, completed plans) were deleted once done. The house rules that came out of that pass are stated in `app/AGENTS.md` and the mechanical ones are enforced by a ratchet test with no allowlist.

## Considered options

- **Keep the Expo app and fix it.** Rejected: the port was already most of the way there, the owner was hitting prod failures on the Expo build, and maintaining two apps was not an option.
- **Keep the ported structure as-is.** Rejected: it wasn't Flutter-esque, and the extra seams were exactly the complexity that made the Expo app hard to change.

## Consequences

- **Open Expo-era PRs were closed, not merged.** Each was mined change-by-change for anything still worth porting, and the findings were recorded as comments on the closed PRs (#74, #90, #103, #104).
- **Simplification is a standing stance, not a one-off.** New code follows the house rules; the ratchet test fails the build if mechanical rules regress. Built-ins and libraries win over hand-rolled code wherever a library cleanly replaces bulk code — that's the owner's stated preference, not just a review finding.
- **While the app is in testing there is no backwards-compatibility duty** to old installs; data safety obligations are covered by ADR 0007 instead.
