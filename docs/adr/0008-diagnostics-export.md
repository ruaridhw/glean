---
status: accepted
date: 2026-10-14
---

# The app exports diagnostics to S3, readable without touching the phone

Debugging the owner's phone must not require adb or physical access. A hidden **Settings → Export diagnostics** action uploads a snapshot of the database plus the app's log file into a per-user, timestamped S3 folder, kept for about 30 days, in the same AWS account the developer already reads with the `glean` profile. An agent on the home server can therefore diagnose a report of "it's broken" from the export alone.

## Considered options

- **adb pull from the phone.** Rejected as the primary path: it needs the phone present, paired and awake; the export works from anywhere.
- **A diagnostics backend endpoint.** Unnecessary: the owner is the only user, and a per-user S3 prefix with lifecycle expiry is enough.

## Consequences

- **Logs are redacted before they leave the phone.** Settings validation errors and framework error reporters must not echo secrets or raw response bodies into the log that gets uploaded (#148, #152).
- **The export is also the escape hatch behind ADR 0007:** a snapshot that can be read off the phone can be verified and restored.
- **Retention is deliberately short** (~30 days): diagnostics are for current bugs, not an audit trail.
