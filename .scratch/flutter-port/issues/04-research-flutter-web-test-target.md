Type: research
Status: resolved

## Question

This effort wants a Flutter **web** build used only to drive widget/integration-style tests in CI on a Linux runner, at a fixed phone-sized viewport — never a shipped target. Research: can `flutter test` (with the `integration_test` package) or `flutter drive --platform chrome` run headlessly against Chrome with a fixed viewport size in CI? What plugin/rendering gaps exist between Flutter web and native (text layout differences via CanvasKit/HTML renderer, plugins that no-op or aren't available on web) that could make a web-run test diverge from real device behavior — and how much that matters for test fidelity given this is explicitly test-infrastructure-only, not a shipped surface. Write findings to `.scratch/flutter-port/research/flutter-web-test-target.md`, citing official Flutter docs.

## Answer

`flutter drive -d web-server` + a version-matched `chromedriver` running `integration_test` in headless Chrome is a real, officially supported CI pattern. `flutter test --platform chrome` is explicitly **not** the right tool — Flutter's own tooling source marks it deprecated/internal, reserved for testing the framework itself. A phone-sized viewport is achievable via `--web-browser-flag="--window-size=390,844"` (overriding flutter_tools' hardcoded 1024×1024 default).

**Significant caveat**: Flutter resolves `defaultTargetPlatform` on web to the **browser's host OS** — `TargetPlatform.linux` on a Linux CI runner, not iOS or Android. Platform-adaptive scroll physics, overscroll indicators, and Material/Cupertino theming won't match the real shipped app's platform by default. Also: drag-to-scroll defaults to touch-only pointer kinds while WebDriver sends mouse events; CanvasKit text rendering diverges from native Skia rendering; plugins like `local_auth` and `path_provider` are unsupported on web.

Net read (the research agent's own synthesis, not an official verdict — no source directly blesses or warns against this exact use case): sound for logic/state/navigation-level widget tests, genuinely risky as a stand-in for anything touching platform-adaptive gestures, visuals, or native-plugin behavior. Ticket 09 should scope the web target's *test suite* narrowly (state/nav/logic) and lean on the real-device `integration_test` run (ticket 09/16) for anything platform-adaptive, rather than treating the web target as a full substitute.

Full findings + citations: `.scratch/flutter-port/research/flutter-web-test-target.md` on branch `worktree-agent-a3260c305f9577122` (worktree `/home/ruaridh/glean/.claude/worktrees/agent-a3260c305f9577122`, commit `3fcbbfe8b1`) — not yet merged into `flutter-port`.
