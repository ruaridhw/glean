Type: research
Status: resolved

## Question

Research two related things for the eventual iOS/Android build pipeline decision (ticket 09):

1. **Signing/release pipeline** options for Flutter: manual certs vs Fastlane (+ `match` for cert sync) vs Codemagic vs other CI-native Flutter release tooling, as of 2026.
2. **GitHub Actions macOS runner capabilities**: can a `macos-*`-labeled hosted runner boot an Android emulator *and* an iOS Simulator in the same job, run a Flutter `integration_test` suite against both, and be gated behind `workflow_dispatch` (manual trigger only, not on every push, and not the Linux runner used for the rest of CI)? Note available Xcode/Android SDK versions and any known limitations (e.g. nested virtualization for the Android emulator on macOS runners).

Write findings to `.scratch/flutter-port/research/build-release-macos-ci.md`, citing GitHub's runner-image docs and official Flutter CI guidance.

## Answer

**Signing/release pipeline**: Flutter's official CI/CD cookbook treats manual signing as local-only, not CI-viable. For a solo dev/small team: Codemagic has the lowest setup friction (signing managed in its UI, no Ruby toolchain) but adds vendor lock-in and cost; Fastlane + `match` is free and portable to any CI but requires learning the Fastlane/Ruby stack; pure manual signing only works until a second person or CI machine needs to sign.

**macOS runner capabilities — a real blocker was found**: the Android-emulator-on-macOS nested-virtualization limitation is confirmed still unresolved as of 2026. GitHub's runner docs state nested virtualization isn't supported on current arm64 macOS runners (`macos-latest`/`macos-26`) due to Apple's Virtualization Framework, and a January 2026 feature request to lift this was explicitly closed "not planned" (`actions/runner-images#13505`). `ReactiveCircus/android-emulator-runner` now recommends avoiding macOS runners for Android emulation entirely (Ubuntu/KVM is 2-3x faster and cheaper anyway). **This blocker applies specifically to GitHub-*hosted* macOS runners** — it's a limitation of GitHub's own virtualized macOS VMs, not of Apple Silicon hardware itself. A **self-hosted runner on a physical Mac** (e.g. the "Mac laptop" mentioned when this ticket's scope was set — see ticket 09 / the map's Q7 destination decision) would run the Android emulator directly on real hardware, not nested inside another VM, and should not hit this limitation. Ticket 09 needs to pin down whether "manual macOS CI job" means a GitHub-hosted macOS runner (in which case: two separate jobs, macOS for iOS Simulator + Linux/KVM for Android emulator) or a self-hosted runner on an actual Mac (in which case one combined job may work as originally envisioned) — this wasn't disambiguated when the destination was scoped and materially changes the design.

Full findings + citations: `.scratch/flutter-port/research/build-release-macos-ci.md` on branch `worktree-agent-abad924a39233df46` (worktree `/home/ruaridh/glean/.claude/worktrees/agent-abad924a39233df46`, commit `73541f2`) — not yet merged into `flutter-port`.
