---
status: accepted
date: 2026-10-15
---

# Android version codes are build timestamps

Every Android build, whether a Codemagic tester build or an owner build made on the home server, sets its **versionCode to the number of minutes since 2024-01-01 00:00 UTC** at build time. Android only installs an update with a higher versionCode, and there are now two build pipelines with no shared counter. A timestamp always goes up, whichever pipeline made the build, so neither has to know about the other. The human-facing versionName ("1.0.0") is unaffected, and Codemagic's own build number stays in the release notes.

## Considered options

- **Codemagic's build number for tester builds, and the installed number plus one for owner builds.** The first version collided on the second cycle: the next tester build got the same number. The fix (tester builds × 100, owner builds read the phone and add one) needed adb access and capped owner builds at 99 between tester builds.
- **Bumping versionName.** Android never compares it, so it can't decide install order.

## Consequences

- **This is irreversible.** Android refuses any build with a lower versionCode than the one installed, so going back to small numbers would mean uninstalling.
- **The first timestamped build** (around 1.5 million) installs over today's versionCode 4.
- **There's ample headroom:** at one tick per minute, Android's limit of about 2.1 billion is about 4,000 years away.
