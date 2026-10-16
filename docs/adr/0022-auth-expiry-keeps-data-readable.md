---
status: accepted
date: 2026-10-06
---

# Auth expiry never locks you out of your own data

Because all user data is local (ADR 0005), an expired or missing token gates **only the AI-backed features**, behind a "signed out" banner. The pantry, plan and shopping list stay readable and editable while signed out — hard-booting the user out of their own data for a network-only concern is the wrong trade.

Two corollaries follow from the same reasoning. **Sign-out does not wipe the database:** every user-data table carries a user-scoping column (keyed by the Cognito `sub`), so a different account signing in on the same phone sees its own empty data, and the previous user's data is intact when they sign back in. And **tokens are cleared explicitly on logout**, because iOS Keychain items survive uninstall — reinstall-as-signout is not an assumption the app makes.

## Considered options

- **Force re-login on expiry.** Rejected: the data isn't the server's to withhold; the app is local-first.
- **Wipe-on-signout for hygiene.** Rejected: it turns a routine sign-out into data loss; per-user scoping provides the isolation instead.

## Consequences

- **User scoping is free now and expensive later** — it landed before launch precisely because no data migration was owed yet.
- **Session races resolve towards safety:** logout wins against late token-refresh or storage completions.
- **The auth test bypass lives in a separate entrypoint** (`main_e2e.dart`) so it cannot compile into a production binary — protection doesn't rest on the backend alone.
