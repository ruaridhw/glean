# Flutter Web as a Headless CI Stand-In for Mobile Widget/Integration Tests

## Executive summary

Running Flutter widget/integration tests against a Flutter **web** build in headless Chrome on Linux CI is a real, officially-supported mechanism (`flutter drive -d web-server` + `chromedriver`, or plain `flutter test` for pure widget tests), and viewport size *can* be pinned to a phone-sized resolution via `--web-browser-flag=--window-size=W,H`, overriding Flutter tooling's own hardcoded `1024x1024` default. However, official sources make clear that web is treated by Flutter's own tooling and documentation as the *more complex, secondary* path relative to native/desktop (`flutter test integration_test/...` works directly on Android/iOS/desktop; web requires a separate ChromeDriver process and `flutter drive`), and there are multiple **structural, sourced-from-Flutter's-own-code** divergences between web and native mobile: platform-adaptive widgets and scroll physics resolve against the *host OS running the browser* (e.g. `TargetPlatform.linux` on a Linux CI runner) rather than the app's real iOS/Android target; default drag-to-scroll only fires for touch-like pointer kinds, and headless Chrome delivers **mouse**, not touch, input; CanvasKit text rendering is documented (via Flutter's own issue tracker) to diverge visibly from native/device Skia text rendering; and several plugins (`local_auth`, `path_provider`, camera without `camera_web`) are unsupported or behaviorally different on web. No official Flutter document explicitly blesses or forbids "Flutter web as a CI stand-in for a mobile app's widget/integration tests" — that specific pattern is not addressed by primary sources one way or the other; the assessment in Q4 is therefore partly this research's own synthesis, clearly labeled.

---

## 1. Can `flutter test` + `integration_test` run against web/Chrome headlessly in CI? What's the actual invocation and requirements?

**Two distinct, non-interchangeable commands exist, and the official docs draw the boundary at "web vs everything else":**

- For Android, iOS, and desktop (Windows/macOS/Linux), the `integration_test` package can be run directly with:
  ```
  flutter test integration_test/app_test.dart
  ```
- For **web (Chrome)**, the official docs state you must use `flutter drive` with a driver script instead — `flutter test` does not support running `integration_test` suites against a browser:
  ```
  flutter drive \
    --driver=test_driver/integration_test.dart \
    --target=integration_test/app_test.dart \
    -d chrome        # visible Chrome
  # or, headless:
  flutter drive \
    --driver=test_driver/integration_test.dart \
    --target=integration_test/app_test.dart \
    -d web-server
  ```
  Source: [Check app functionality with an integration test — docs.flutter.dev/testing/integration-tests](https://docs.flutter.dev/testing/integration-tests). The page explicitly separates "Desktop, Android, iOS" (single `flutter test` command) from "Web" (ChromeDriver install + `flutter drive` + separate driver file), i.e. web is documented as the more complex, secondary path.

- The `integration_test` package README itself (`flutter/flutter` repo) confirms the same web invocation and mechanism under its own "Web" subsection:
  ```
  flutter drive \
    --driver=test_driver/integration_test.dart \
    --target=integration_test/foo_test.dart \
    -d web-server
  ```
  and notes "Make sure you have [enabled web support] then [download and run] the web driver in another process."
  Source: [flutter/flutter — packages/integration_test/README.md](https://github.com/flutter/flutter/blob/main/packages/integration_test/README.md) (lines ~86–106 as of the current `master` HEAD).

- **`--browser-name=chrome`** and **`--web-port`** are supported flags on `flutter drive -d web-server`; the migrated wiki page ("Running Flutter Driver tests with Web") gives the fuller form:
  ```
  flutter drive --target=test_driver/[driver_test].dart -d web-server --release --browser-name=chrome --web-port=8080
  ```
  Source: [flutter/flutter — docs/contributing/testing/Running-Flutter-Driver-tests-with-Web.md](https://github.com/flutter/flutter/blob/master/docs/contributing/testing/Running-Flutter-Driver-tests-with-Web.md). This page also states debug-mode support for web driver tests is not yet complete ("`--release` or `--profile`... debug mode support is forthcoming" at time of writing) and that `--browser-name` accepts `chrome, safari, ios-safari, android-chrome, firefox, edge`, with Firefox/Edge marked **experimental** with no automated test infrastructure.

- **`flutter test --platform chrome` is explicitly NOT the supported path for app developers.** Flutter's own tooling source marks it deprecated and developer-facing use as out of scope:
  > "`--platform` is not supported to be used by Flutter developers. It only exists to test the Flutter framework itself and may be removed entirely in the future. Developers should either use plain `flutter test`, or `package:integration_test` instead."
  > `'chrome': '(deprecated) Run tests using the Google Chrome web browser. This value is intended for testing the Flutter framework itself and may be removed at any time.'`
  Source: [flutter/flutter — packages/flutter_tools/lib/src/commands/test.dart](https://github.com/flutter/flutter/blob/master/packages/flutter_tools/lib/src/commands/test.dart) (lines ~200–217, blob sha `78f4cd5a...` as fetched). This directly answers the "is it `flutter test --platform chrome`?" question in the prompt: **no**, that flag is reserved for Flutter's own framework CI and is documented as unsupported/removable for app authors.

**ChromeDriver setup / version matching:**
- Install: `npx @puppeteer/browsers install chromedriver@stable`, verify with `chromedriver --version`, add to `$PATH`. Start it as a separate process before `flutter drive`: `chromedriver --port=4444`.
  Source: [docs.flutter.dev/testing/integration-tests](https://docs.flutter.dev/testing/integration-tests).
- ChromeDriver **major version must match the installed Chrome major version** — the older wiki instructions say explicitly: "Check the version of Chrome. Download the Chrome driver for that version from [driver downloads]."
  Source: [Running-Flutter-Driver-tests-with-Web.md](https://github.com/flutter/flutter/blob/master/docs/contributing/testing/Running-Flutter-Driver-tests-with-Web.md).
- `flutter drive -d web-server` currently requires the developer to manually start `chromedriver` themselves first; there is an open, unresolved Flutter issue about this being awkward for CI ("Unable to start a WebDriver session for web testing" if chromedriver isn't already running), with no built-in auto-launch:
  Source: [flutter/flutter#146464 — `flutter drive -d web-server` requires the user to manually run `chromedriver`](https://github.com/flutter/flutter/issues/146464) (open, P2, untriaged owner as of fetch).

**Headless-mode caveats found in the issue tracker (primary-source, not blog):**
- `--web-run-headless` was, for a period, silently ignored by `flutter drive` for web integration tests because `DebuggingOptions` were reconstructed internally without forwarding the flag — filed as a concrete Flutter tooling bug:
  Source: [flutter/flutter#95085 — `--web-run-headless` does not take effect when using flutter drive for flutter web integration_test](https://github.com/flutter/flutter/issues/95085).
- Chrome's headless mode itself changed (`--headless` → `--headless=old` / `--headless=new`), which broke some of Flutter's own web-driven test infra starting around chromedriver 128; the Flutter team's own remediation is a manual browser-flag workaround (`--headless=old`, plus `--disable-search-engine-choice-screen`), not a first-class tool fix — issue is **still open**, P2:
  Source: [flutter/flutter#154727 — Support new chrome headless mode from flutter driver](https://github.com/flutter/flutter/issues/154727).
- Separately, `flutter_tools` itself launches Chrome headlessly with a fixed, hardcoded flag set including `--headless`, `--no-sandbox`, and Linux-specific software-rendering flags (`--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader --disable-gpu-sandbox`) whenever `headless: true` is passed internally — this is the actual mechanism `flutter run -d web-server`/`flutter drive` uses under the hood, confirmed directly in source (see Q2 below for full excerpt).
  Source: [flutter/flutter — packages/flutter_tools/lib/src/web/chrome.dart, lines 263–279](https://github.com/flutter/flutter/blob/master/packages/flutter_tools/lib/src/web/chrome.dart).

**Bottom line for Q1:** the correct, currently-supported invocation for headless CI is `flutter drive --driver=test_driver/integration_test.dart --target=integration_test/app_test.dart -d web-server [--browser-name=chrome] [--web-port=...]`, with a separately-launched, version-matched `chromedriver` process. `flutter test --platform chrome` is explicitly out of scope for this use case per Flutter's own source comments.

---

## 2. Can the viewport/window size be fixed to a phone-sized resolution (e.g. 390×844)?

**Yes — via the browser-launch mechanism, not via `TestWidgetsFlutterBinding`, and it must override a hardcoded default:**

- `flutter_tools`'s Chrome launcher (used by both `flutter run -d chrome` and `flutter drive -d web-server`/`-d chrome`) hardcodes `--window-size=1024,1024` whenever it launches Chrome headlessly:
  ```dart
  if (headless) ...<String>[
    '--no-sandbox',
    '--headless',
    '--window-size=1024,1024',
    '--disable-background-networking',
    ...
  ],
  ...webBrowserFlags,
  url,
  ```
  Source: [flutter/flutter — packages/flutter_tools/lib/src/web/chrome.dart, lines 263–279](https://github.com/flutter/flutter/blob/master/packages/flutter_tools/lib/src/web/chrome.dart) (fetched at blob sha `e2d090741829cc23a36cf55bc2988ffee7210e84`).
- Critically, **`...webBrowserFlags` is spread in *after* the hardcoded headless flag block** (line 279, immediately before `url`). Chromium's command-line parser resolves duplicate switches by last-occurrence-wins, so a user-supplied `--window-size` flag passed through Flutter's own `--web-browser-flag` CLI option will land after, and override, the tool's default `1024,1024`.
- `--web-browser-flag` is a real, repeatable, documented `flutter_tools` CLI option:
  ```dart
  static const kWebBrowserFlag = 'web-browser-flag';
  ...
  argParser.addMultiOption(
    FlutterOptions.kWebBrowserFlag,
    help: 'Additional flag to pass to a browser instance at startup.\n'
        'Chrome: https://www.chromium.org/developers/how-tos/run-chromium-with-flags/\n'
        'Firefox: https://wiki.mozilla.org/Firefox/CommandLineOptions\n'
        'Multiple flags can be passed by repeating "--web-browser-flag" multiple times.',
    valueHelp: '--foo=bar',
    hide: !verboseHelp,
  );
  ```
  Source: [flutter/flutter — packages/flutter_tools/lib/src/runner/flutter_command.dart, lines 148, 375–390](https://github.com/flutter/flutter/blob/master/packages/flutter_tools/lib/src/runner/flutter_command.dart).
- So the concrete, sourced mechanism for a 390×844 phone viewport in headless CI is:
  ```
  flutter drive \
    --driver=test_driver/integration_test.dart \
    --target=integration_test/app_test.dart \
    -d web-server \
    --browser-name=chrome \
    --web-browser-flag="--window-size=390,844"
  ```
  (This is inference from combining the two sourced facts above — the append-order and the flag's documented purpose — not a single doc page that spells out this exact recipe; see Caveats.)

- **What it is *not*:** `TestWidgetsFlutterBinding.setSurfaceSize()` / `TestFlutterView.physicalSize` is a *`flutter_test`-level* mechanism for plain widget tests running inside the VM/browser test harness (e.g. `flutter test`), not the real Chrome window opened by `flutter drive`'s WebDriver session. The API docs state `setSurfaceSize` "only affects the size of the `WidgetTester.view`" and recommend `TestFlutterView.physicalSize` for other views; it operates on Flutter's internal notion of window size inside the test binding, independent of the actual host window/viewport.
  Source: [api.flutter.dev — `TestWidgetsFlutterBinding.setSurfaceSize`](https://api.flutter.dev/flutter/flutter_test/TestWidgetsFlutterBinding/setSurfaceSize.html), [api.flutter.dev — `TestWindow.physicalSize`](https://api.flutter.dev/flutter/flutter_test/TestWindow/physicalSize.html).
  There is also an open, confirmed regression where setting `tester.view.physicalSize` inside an `integration_test` (as opposed to a plain widget test) can break rendering entirely — the app under test shows only a "Test starting..." placeholder instead of the real UI:
  Source: [flutter/flutter#149209 — integration_test doesn't show UI under test with a non-default view physicalSize](https://github.com/flutter/flutter/issues/149209) (regression from Flutter 3.19, affects macOS/Linux per the reporter). This is a concrete reason to prefer the browser/ChromeDriver-level `--window-size` mechanism over the in-Dart `physicalSize` override for `integration_test`-driven web runs.

- **Feature gap on customizing WebDriver desired capabilities directly:** there is an open Flutter feature request asking for a `--web-desired-capabilities`-style flag to customize ChromeDriver desired capabilities (motivated there by `--use-fake-device-for-media-stream`, not window size) — confirming that today the *only* supported lever for browser launch flags from `flutter drive` is `--web-browser-flag`, not desired-capabilities JSON:
  Source: [flutter/flutter#109451 — Add ability to customize web driver desired capabilities when tests running by `flutter drive` command](https://github.com/flutter/flutter/issues/109451) (open, P3).

**Bottom line for Q2:** yes, fixable, via `--web-browser-flag=--window-size=390,844` passed to `flutter drive`, which overrides flutter_tools' own hardcoded `1024,1024` headless default because user flags are appended last in the Chrome launch-args list. `TestWidgetsFlutterBinding`/`physicalSize` overrides are a different, in-Dart mechanism intended for plain widget tests, and are documented to actively break `integration_test` UI rendering when used that way.

---

## 3. Rendering/behavior gaps between Flutter web and native mobile

### a. CanvasKit vs HTML renderer — current status and text-rendering fidelity

- **The HTML renderer is deprecated and has been actively removed from the tool surface.** The official removal PR states: "Removes the `--web-renderer` option... Flutter tool users won't be able to select their web renderer" (merged Dec 2, 2024; the framework/engine kept the code temporarily for internal test coverage only, pending full removal).
  Source: [flutter/flutter#159314 — [tool] Removes deprecated --web-renderer parameter](https://github.com/flutter/flutter/pull/159314).
- The intent-to-deprecate tracking issue frames the HTML renderer as "complex, underperforming, and limited in graphical expressivity" relative to the WebGL/Wasm-based CanvasKit/Skwasm renderers, and lists prerequisites (image codec work, app-loading improvements, CORS handling, user-facing deprecation warnings) that had to land first.
  Source: [flutter/flutter#145954 — ☂️ Intent to deprecate and remove the HTML renderer in Flutter Web](https://github.com/flutter/flutter/issues/145954).
- **Current renderer model (per official platform docs):** Flutter web now renders via CanvasKit (Skia compiled to WebAssembly, ~1.5MB, all modern browsers) or Skwasm (a leaner Skia/Wasm build, only available in `--wasm` builds, used automatically when the browser supports the needed WasmGC features, with CanvasKit as fallback).
  Source: [docs.flutter.dev/platform-integration/web/renderers](https://docs.flutter.dev/platform-integration/web/renderers) (general architecture text) — note this specific page's fetched content was thin on renderer-selection detail; the CanvasKit/Skwasm mechanics above are corroborated by the PR/issue text cited above, which is the authoritative source for the *current* (as of the PR) renderer story.
- **Text-layout/rendering fidelity gap is real and documented in Flutter's own issue tracker, not just blogs:**
  - "Fonts are too thin compared to the same fonts on Windows Desktop, Android, iOS and compared to the previous WEB DomCanvas [HTML renderer] example as well" — filed against CanvasKit, labeled `a: typography`, `c: rendering`, `e: web_canvaskit`.
    Source: [flutter/flutter#56319 — Flutter WEB: CanvasKit font rendering does not match DomCanvas or Desktop or device SKIA font rendering](https://github.com/flutter/flutter/issues/56319) (closed; no maintainer comment in the fetched excerpt asserting this is "by design," so treat as a known-but-not-formally-blessed divergence).
  - A 2024/2025-era issue (post Flutter 3.29) reports CanvasKit-specific Hangul character misalignment/fragmentation and emoji rendering differences relative to the (now-removed) HTML renderer, closed as `r: solved`.
    Source: [flutter/flutter#163453 — Issues After Flutter Upgrade(3.29): CORS, Font Rendering, and Emoji Differences on Web (CanvasKit)](https://github.com/flutter/flutter/issues/163453).
  - Because CanvasKit does not use the browser's/OS's native text-shaping stack, custom fonts (including an emoji font) must be shipped and rendered by Skia-on-Wasm rather than the platform's native font renderer — a structural reason text can look subtly different from native iOS/Android rendering even absent bugs. (This is stated across the issues above; there isn't a single authoritative "known limitations" doc page enumerating it, so treat the general claim as inferred-but-well-evidenced from the linked primary issues rather than a single blessed doc.)

### b. Plugins that no-op / differ / are unavailable on web

Checked directly on pub.dev (official package listings):

| Plugin | Web support | Notes |
|---|---|---|
| `flutter_secure_storage` | **Supported**, with caveats | Web implementation is explicitly called out as experimental, uses WebCrypto + `localStorage`, requires HTTPS or `localhost`, and its own docs say values are "not portable to other browsers or other machines" and to "use at your own risk." Source: [pub.dev/packages/flutter_secure_storage](https://pub.dev/packages/flutter_secure_storage). |
| `local_auth` | **Not supported** on Web | Supported platform list is Android, iOS, macOS, Windows only. Source: [pub.dev/packages/local_auth](https://pub.dev/packages/local_auth). |
| `camera` | **Supported** on Web via companion `camera_web` package | Root `camera` package readme: "A Flutter plugin for iOS, Android and Web allowing access to the device cameras," with web specifics deferred to `camera_web`. In a headless CI browser there is no real camera device, so this would need mocking/fake-media-stream flags regardless of platform. Source: [pub.dev/packages/camera](https://pub.dev/packages/camera). |
| `path_provider` | **Not supported** on Web | Official listing: "Supports Android, iOS, Linux, macOS and Windows... Not all methods are supported on all platforms" — Web is absent from the list. Source: [pub.dev/packages/path_provider](https://pub.dev/packages/path_provider). |
| `vibration` (community package for `HapticFeedback`-style effects) | **Supported** on Web, iOS, Android, OpenHarmony (per listing) | Source: [pub.dev/packages/vibration](https://pub.dev/packages/vibration). |
| `HapticFeedback` (Flutter SDK, `dart:ui`/`flutter/services`) | Routed on web, but functionally inert in headless CI | On web, `HapticFeedback.vibrate()` (and the impact/selection variants) are handled by the Flutter web engine's platform-message dispatcher, which calls a `vibrate(durationMs)` helper mapped to specific millisecond durations per feedback type (`vibrateLongPress = 50ms`, `vibrateLightImpact = 10ms`, etc.) — i.e., it attempts to call the browser's Vibration API rather than silently no-op'ing at the Dart layer. Source: [flutter/flutter — engine/src/flutter/lib/web_ui/lib/src/engine/platform_dispatcher.dart, lines ~515–691](https://github.com/flutter/flutter/blob/master/engine/src/flutter/lib/web_ui/lib/src/engine/platform_dispatcher.dart). In practice the browser Vibration API is unsupported in desktop/headless Chrome (no vibration hardware), so the call is a functional no-op in this CI context even though the code path differs from native iOS/Android (`HapticFeedback.vibrate` dart source: [packages/flutter/lib/src/services/haptic_feedback.dart](https://github.com/flutter/flutter/blob/master/packages/flutter/lib/src/services/haptic_feedback.dart)). |

### c. Gesture/scroll-physics differences (sourced directly from `flutter/flutter` framework source)

- **Scroll physics (bounce vs clamp) is chosen per `TargetPlatform`, and `TargetPlatform` on web is derived from the *browser/host OS*, not a fixed "web" value:**
  ```dart
  ScrollPhysics getScrollPhysics(BuildContext context) {
    switch (getPlatform(context)) {
      case TargetPlatform.iOS:
        return _bouncingPhysics;
      case TargetPlatform.macOS:
        return _bouncingDesktopPhysics;
      case TargetPlatform.android:
      case TargetPlatform.fuchsia:
      case TargetPlatform.linux:
      case TargetPlatform.windows:
        return _clampingPhysics;
    }
  }
  ```
  Source: [flutter/flutter — packages/flutter/lib/src/widgets/scroll_configuration.dart, lines 227–257](https://github.com/flutter/flutter/blob/master/packages/flutter/lib/src/widgets/scroll_configuration.dart).
- **`defaultTargetPlatform` on web resolves from the browser's reported operating system, not from the mobile OS you're trying to emulate:**
  ```dart
  // The web implementation of platform.defaultTargetPlatform.
  platform.TargetPlatform get defaultTargetPlatform {
    return platform.debugDefaultTargetPlatformOverride ?? _testPlatform ?? _browserPlatform;
  }
  ...
  platform.TargetPlatform _operatingSystemToTargetPlatform(ui_web.OperatingSystem os) {
    return switch (os) {
      ui_web.OperatingSystem.android => platform.TargetPlatform.android,
      ui_web.OperatingSystem.iOs => platform.TargetPlatform.iOS,
      ui_web.OperatingSystem.linux => platform.TargetPlatform.linux,
      ui_web.OperatingSystem.macOs => platform.TargetPlatform.macOS,
      ui_web.OperatingSystem.windows => platform.TargetPlatform.windows,
      ui_web.OperatingSystem.unknown => platform.TargetPlatform.android,
    };
  }
  ```
  Source: [flutter/flutter — packages/flutter/lib/src/foundation/_platform_web.dart](https://github.com/flutter/flutter/blob/master/packages/flutter/lib/src/foundation/_platform_web.dart), corroborated by the doc comment on the shared `defaultTargetPlatform` getter: "a boolean which is true if the application is running on the web, where `defaultTargetPlatform` returns which platform the browser is running on" — [packages/flutter/lib/src/foundation/platform.dart](https://github.com/flutter/flutter/blob/master/packages/flutter/lib/src/foundation/platform.dart).
  **Concrete implication:** headless Chrome on a **Linux CI runner** resolves `defaultTargetPlatform` to `TargetPlatform.linux` — which shares `_clampingPhysics` with Android, but is neither of the two real mobile targets (iOS's bouncing physics would never trigger by default on this web run, even if the shipped app is an iOS app). Any test relying on default Material/Cupertino platform-adaptive behavior (scroll physics, overscroll indicators, `MultitouchDragStrategy`, `Scrollbar` construction) diverges from the real iOS or Android target unless the app or test explicitly forces `debugDefaultTargetPlatformOverride` / `ThemeData.platform`.
- **Drag-to-scroll device kinds default to touch-like pointers only, excluding mouse — and WebDriver-driven browser automation sends mouse events, not touch events, by default:**
  ```dart
  const _kTouchLikeDeviceTypes = <PointerDeviceKind>{
    PointerDeviceKind.touch, PointerDeviceKind.stylus,
    PointerDeviceKind.invertedStylus, PointerDeviceKind.trackpad,
    PointerDeviceKind.unknown,
  };
  ...
  Set<PointerDeviceKind> get dragDevices => _kTouchLikeDeviceTypes;
  ```
  Source: [flutter/flutter — packages/flutter/lib/src/widgets/scroll_configuration.dart, lines 29–37, 113–120](https://github.com/flutter/flutter/blob/master/packages/flutter/lib/src/widgets/scroll_configuration.dart). The official breaking-change note for this default (landed 2.3.0, stable in 2.5) states: "`ScrollBehavior.dragDevices`, by default, allows scrolling widgets to be dragged by all `PointerDeviceKind`s except for `PointerDeviceKind.mouse`," specifically to avoid interfering with mouse text-selection gestures — and gives the fix as overriding `dragDevices` in a custom `ScrollBehavior`.
  Source: [docs.flutter.dev/release/breaking-changes/default-scroll-behavior-drag](https://docs.flutter.dev/release/breaking-changes/default-scroll-behavior-drag).
  **Implication for this CI pattern:** ChromeDriver/WebDriver-issued pointer actions to a headless Chrome instance are standard W3C WebDriver "pointer" actions, which Flutter's web engine surfaces to the framework as mouse-type pointer events unless the test harness specifically simulates touch. If the app doesn't already customize `dragDevices` to include `mouse` (many apps don't need to, since real mobile users only use touch), drag-to-scroll interactions that work by touch on a real device may not register the same way — or may need to be driven through Flutter's semantics/finder taps and `dragFrom`/`fling` test APIs rather than relying on default gesture recognition — in a web/WebDriver-automated run.

**Bottom line for Q3:** the HTML-vs-CanvasKit renderer question is largely resolved (HTML renderer is gone; CanvasKit/Skwasm is current), but CanvasKit's own text rendering is documented (via Flutter's own issue tracker) to visibly differ from native/device Skia rendering. Plugin support is uneven and package-specific (secure storage web-supported-but-weaker; biometrics/`local_auth` and `path_provider` unsupported on web outright; camera needs a web-specific companion package). Scroll physics and platform-adaptive widget behavior are governed by `defaultTargetPlatform`, which on a web build resolves to the **browser's host OS** (e.g., Linux on a Linux CI runner), not to the real shipped iOS/Android target — a first-party-sourced, structural fidelity gap independent of any bug.

---

## 4. Given the gaps above, and given this is test-infrastructure-only: how much should the native-vs-web gap matter?

**What official sources directly say (sourced):**

- `docs.flutter.dev/testing/integration-tests` documents Android/iOS/desktop as able to run integration tests with the single command `flutter test integration_test/app_test.dart`, and treats web as a separate, more heavily-instrumented path requiring ChromeDriver and `flutter drive` — an explicit asymmetry in how "first-class" each target is treated by the tooling itself, though the page does not editorialize about *fidelity*, only about *setup complexity*.
  Source: [docs.flutter.dev/testing/integration-tests](https://docs.flutter.dev/testing/integration-tests).
- The `integration_test` package's own scope statement, from Flutter's integration-testing concepts page, is a hard functional limitation that applies on *every* platform including web: "`integration_test` can't interact with native platform UI" — specifically permission dialogs, notifications, and platform-view contents — and the docs point to the third-party `patrol` package as the tool that can. This is *not* a web-specific caveat, but it does mean `integration_test` was never positioned as full end-to-end fidelity even on real devices; using it via a web target doesn't introduce this gap so much as compound a pre-existing one.
  Source: [docs.flutter.dev/cookbook/testing/integration/introduction](https://docs.flutter.dev/cookbook/testing/integration/introduction).
- The same page's framing — "If you run your app in a web browser or as a desktop application, the host machine and the target device are the same" — groups web with desktop as a same-machine execution model, distinct from a real mobile device/emulator, which is consistent with (but doesn't explicitly state) treating web as architecturally closer to "another desktop-like host" than to "a mobile device."
- `flutter test --platform chrome` being marked, in Flutter's own tooling source, as unsupported for app developers and reserved for testing the framework itself is a strong first-party signal that Flutter does **not** consider a Chrome-based test run a general-purpose substitute for testing an app on its real target platform — though note this specific statement is about the `flutter test` browser backend, not about `flutter drive`-driven `integration_test` web runs, which the same team documents and supports for actual web *deployment* verification.
  Source: [flutter/flutter — packages/flutter_tools/lib/src/commands/test.dart](https://github.com/flutter/flutter/blob/master/packages/flutter_tools/lib/src/commands/test.dart).
- No official Flutter document found in this research explicitly discusses, endorses, or warns against the specific pattern this repo is considering: **using a Flutter web build purely as CI test infrastructure to validate a mobile (iOS/Android) app's UI**, as opposed to testing an app that is *itself* shipped on web. All Flutter web testing documentation is written from the premise that the web build under test is also a real deployment target. This asymmetry (web-as-test-double for mobile) appears to be outside the scope of what any primary source directly addresses.

**Reasoned synthesis (own analysis, not sourced from Flutter docs — labeled as such):**

Given the sourced facts above, the pattern is plausible as a *fast, cheap smoke/regression layer* for widget-level logic and simple interaction flows, but has a real, non-hypothetical fidelity ceiling for anything touching:
- platform-adaptive visuals/physics (scroll bounce vs clamp, overscroll indicators, `Theme.platform`-driven Material/Cupertino choices) — since `defaultTargetPlatform` on a Linux CI runner is `TargetPlatform.linux`, not iOS or Android, unless the app/tests force an override;
- gesture fidelity for drag/scroll/fling, since WebDriver-issued input is mouse-shaped, not touch-shaped, and Flutter's default `dragDevices` set is touch-oriented;
- any plugin-backed behavior (secure storage semantics, biometrics, camera, filesystem paths, haptics) where the web implementation is either absent, weaker, or routes through a different code path than the native platform channel;
- pixel-level text rendering, where CanvasKit's Skia-on-Wasm text shaping is documented to visibly diverge from native/device Skia in some scripts and font-weight cases.

For pure logic/state/navigation assertions (does tapping X show Y, does the right widget tree render, does state update correctly) the gap is unlikely to matter much, because those tests exercise the widget tree and app logic, which is renderer- and platform-detection-agnostic. For anything that depends on platform-adaptive scroll/gesture behavior, plugin-backed native capabilities, or exact visual/text output, this pattern should be expected to diverge from real-device behavior, and a human should decide *up front* which categories of tests are safe to keep on this web-CI lane vs. which need to stay on (or move to) a real-device/emulator-backed lane (e.g., a smaller, slower matrix on macOS runners with real simulators, or cloud device farms) — because Flutter's own source and docs confirm the divergence mechanisms exist; they simply don't tell you how much it will matter for *your* app's specific test suite, since that depends on which widgets/physics/plugins that suite actually exercises.

---

## References (primary sources cited above)

- https://docs.flutter.dev/testing/integration-tests
- https://docs.flutter.dev/cookbook/testing/integration/introduction
- https://docs.flutter.dev/platform-integration/web/renderers
- https://docs.flutter.dev/release/breaking-changes/default-scroll-behavior-drag
- https://docs.flutter.dev/reference/supported-platforms
- https://github.com/flutter/flutter/blob/main/packages/integration_test/README.md
- https://github.com/flutter/flutter/blob/master/docs/contributing/testing/Running-Flutter-Driver-tests-with-Web.md
- https://github.com/flutter/flutter/blob/master/packages/flutter_tools/lib/src/commands/test.dart
- https://github.com/flutter/flutter/blob/master/packages/flutter_tools/lib/src/web/chrome.dart
- https://github.com/flutter/flutter/blob/master/packages/flutter_tools/lib/src/runner/flutter_command.dart
- https://github.com/flutter/flutter/blob/master/packages/flutter/lib/src/widgets/scroll_configuration.dart
- https://github.com/flutter/flutter/blob/master/packages/flutter/lib/src/foundation/platform.dart
- https://github.com/flutter/flutter/blob/master/packages/flutter/lib/src/foundation/_platform_web.dart
- https://github.com/flutter/flutter/blob/master/packages/flutter/lib/src/services/haptic_feedback.dart
- https://github.com/flutter/flutter/blob/master/engine/src/flutter/lib/web_ui/lib/src/engine/platform_dispatcher.dart
- https://github.com/flutter/flutter/issues/95085
- https://github.com/flutter/flutter/issues/154727
- https://github.com/flutter/flutter/issues/146464
- https://github.com/flutter/flutter/issues/109451
- https://github.com/flutter/flutter/issues/149209
- https://github.com/flutter/flutter/issues/56319
- https://github.com/flutter/flutter/issues/163453
- https://github.com/flutter/flutter/issues/145954
- https://github.com/flutter/flutter/pull/159314
- https://api.flutter.dev/flutter/flutter_test/TestWidgetsFlutterBinding/setSurfaceSize.html
- https://api.flutter.dev/flutter/flutter_test/TestWindow/physicalSize.html
- https://pub.dev/packages/flutter_secure_storage
- https://pub.dev/packages/local_auth
- https://pub.dev/packages/camera
- https://pub.dev/packages/path_provider
- https://pub.dev/packages/vibration

---

## Caveats and open questions

- **The exact "phone-sized viewport" recipe in Q2 (`--web-browser-flag="--window-size=390,844"`) is a sourced inference, not a single doc page's worked example.** It is built from two independently-verified facts (the hardcoded `1024,1024` default and its position in the args list relative to `webBrowserFlags`, plus Chromium's documented last-flag-wins behavior for duplicate switches) rather than an official "here's how to set a custom viewport" tutorial. No official Flutter doc was found that shows this exact recipe end-to-end; it should be smoke-tested against the actual Flutter/Chrome/ChromeDriver versions in use before relying on it in CI.
- **`docs.flutter.dev/platform-integration/web/renderers` did not, on fetch, contain a clear current statement distinguishing CanvasKit vs Skwasm selection logic or explicitly discussing text-rendering fidelity vs native.** The renderer-selection mechanics and deprecation timeline used above are reconstructed primarily from the PR/issue tracker (`#159314`, `#145954`), which are still first-party (flutter/flutter repo) but are process/tracking documents rather than a canonical "current renderer behavior" reference page. If a definitive, up-to-date renderer-selection reference page exists elsewhere on flutter.dev, it wasn't located in this pass.
- **No official Flutter source was found that discusses using Flutter web specifically as a *mobile-app* CI test double.** All official web-testing documentation assumes the web build itself is a real, shipped target. This report's Q4 assessment of risk/tradeoffs beyond the directly-sourced facts is explicitly the author's own reasoning, not an official Flutter position — flagged inline above.
- **Chrome headless-mode churn (`--headless` → `--headless=old`/`--headless=new`) is an active, moving target** (flutter/flutter#154727 open as of this research), meaning the exact headless flags that work today may need revisiting as Chrome/ChromeDriver versions advance in CI images.
- **Gesture/pointer-kind behavior (mouse vs touch from WebDriver) was reasoned from framework source (`dragDevices` defaults) and general WebDriver/W3C pointer-action semantics, not from a Flutter doc that explicitly states "WebDriver-driven Flutter web tests deliver mouse events."** This is a reasonable, sourced inference but was not found stated in so many words by Flutter's own docs.
- **`camera` web behavior in a real headless-CI context** (no physical camera, `getUserMedia` typically unavailable/fake-required) was only lightly explored — the `-use-fake-device-for-media-stream`/`-use-fake-ui-for-media-stream` Chrome flags referenced in flutter/flutter#109451 are the relevant lever if camera-adjacent flows need to be exercised, but flutter drive does not yet have a first-class way to pass them (open issue).
