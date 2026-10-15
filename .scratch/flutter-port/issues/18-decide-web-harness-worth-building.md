Type: task
Status: resolved

## Question

Ticket 04 researched how to set up a Flutter web build (`flutter drive -d web-server` + chromedriver, phone-sized viewport via browser flag) but found a real fidelity gap: `TargetPlatform` resolves to the CI host OS, not iOS/Android, so platform-adaptive gestures/theming/native-plugin behavior aren't faithfully exercised. Decide whether it's actually worth building at all.

## Answer

Reframed: this was never meant to be CI infrastructure, and it isn't committed infrastructure — it's a potential **local** dev-loop convenience harness, worth building only if driving Chrome turns out to be meaningfully faster than driving a real iOS/Android emulator for an *agent's* local test-and-iterate loop. That's an empirical question that can't be answered now — there's no Flutter app yet to benchmark against — so it's deferred by design, not decided blind.

**Decided policy**: don't build the web harness as committed infrastructure now. Once early implementation has a minimal running Flutter app, do a quick timing comparison — agent-driven Chrome vs. agent-driven iOS/Android emulator, for a representative test interaction (e.g. navigate a tab, tap a button, assert on-screen state). Build out the web harness (using ticket 04's setup research) only if Chrome is meaningfully faster; otherwise skip it entirely and rely on real-device/emulator testing throughout local development. Carry this conditional policy — not a committed deliverable — into `FLUTTER_MIGRATION.md`.
