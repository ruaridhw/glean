Type: grilling
Status: resolved

## Question

Given ticket 05's finding that GitHub-hosted macOS runners can't run the Android emulator (nested-virtualization limit, confirmed unresolved, no fix planned), decide the CI job topology for the manually-triggered cross-platform `integration_test` run: how many jobs, which runners, which platform each covers.

## Answer

Two separate jobs under one `workflow_dispatch`-gated GitHub Actions workflow, not one combined macOS job:

1. A **macOS runner** job running the `integration_test` suite against the **iOS Simulator**.
2. A **Linux runner** job running the `integration_test` suite against the **Android emulator** via KVM (per ticket 05's finding that Linux/KVM is faster and cheaper than macOS for Android emulation anyway, and doesn't hit the nested-virtualization limitation).

Neither job runs automatically on push — both are manual-trigger only, and both are separate from the Linux runner used for the rest of CI (lint/typecheck/unit/widget tests).

Both platforms must also be runnable **locally from a single Mac laptop** — real Apple Silicon hardware isn't subject to GitHub's nested-virtualization limitation, so one Mac can run both an iOS Simulator and an Android emulator directly for pre-release verification without needing CI at all.
