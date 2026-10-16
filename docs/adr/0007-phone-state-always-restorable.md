---
status: accepted
date: 2026-10-15
---

# The current on-phone state must always be restorable

The owner now uses the app for good, so there must be no data loss: **whatever is on the phone today can be restored after a reinstall, a bad upgrade or a lost phone.** This deliberately does *not* mandate that every change ships as a perfect database migration. Migration is one way; a verified export-and-restore is just as acceptable. What is not acceptable is a state where the only copy of the pantry, plan and shopping list can be stranded.

In practice this landed as belt and braces: Android Auto Backup stays on and keeps the database; a schema snapshot test blocks any table change without a migration; the app refuses to open a database written by a newer build; and the app can **back up and restore its whole state across a reinstall** (#157).

## Considered options

- **Migrations only, as a hard rule.** Rejected as the sole mechanism: it makes every schema change carry upgrade code forever, and it doesn't help when the phone itself is the problem. The guarantee the owner asked for is restorability of current state, by whatever mechanism survives verification.
- **Server-side sync of household data.** Rejected by the local-first stance (ADRs 0001 and 0005); only the catalogue is shared reference data.

## Consequences

- **Restore overwrites the owner's real database,** so restore paths get the strictest review in the repo (the backup/restore PR had multiple blocker rounds on staging and sidecar cleanup).
- **Every schema change** must keep an upgrade or export path working; the schema snapshot test is the enforcement point.
- **User identity is part of data safety:** on-device data is keyed by the Cognito `sub`, which is why the user pool is retained (ADR 0017).
