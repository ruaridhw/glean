# Flutter Auth Port — Research Notes

Research date: 2026-07-25. Scope: find the standard Flutter equivalents for Glean's current
Expo/React Native auth stack (`expo-auth-session` OAuth authorization-code flow,
`expo-secure-store`, sign-in screen, deep-link OAuth callback route), ahead of a big-bang
Flutter rewrite. Primary sources only — pub.dev package pages, GitHub repos (README /
CHANGELOG / issues), official Apple/Google platform docs, and IETF RFCs. Secondary sources
(blogs, Medium, aggregator sites) are avoided as evidence; where a search surfaced one, it was
used only to locate the primary source, which is what's cited below.

## Top-line summary / recommendation

- **Use `flutter_appauth`** (wraps the official AppAuth-iOS / AppAuth-Android SDKs) for the
  authorization-code + PKCE flow rather than hand-rolling `url_launcher` + a deep-link package.
  It is actively maintained (v12.0.2, published 28 days before this research
  ([pub.dev](https://pub.dev/packages/flutter_appauth))), generates and verifies the PKCE
  verifier/challenge for you, and — critically — uses the platform-native external user agent
  (`ASWebAuthenticationSession` / Custom Tabs via AppAuth's own implementation) rather than a
  webview you'd have to secure yourself. This is exactly the pattern RFC 8252 recommends for
  native apps ([RFC 8252 §5](https://datatracker.ietf.org/doc/html/rfc8252)). The manual
  `url_launcher` + `app_links` route is viable but pushes PKCE, `state`, native security
  properties, and redirect-URI plumbing entirely onto Glean's own code with no material benefit
  over `flutter_appauth` for a standard authorization-code flow.
- **Use `flutter_secure_storage`** for token storage — it is the direct analogue of
  `expo-secure-store`, backed by iOS/macOS Keychain and Android Keystore-derived encryption
  ([pub.dev](https://pub.dev/packages/flutter_secure_storage)), and is actively maintained
  (v10.3.1, published 58 days before this research). Be aware of two gotchas documented below:
  iOS Keychain items can survive an uninstall/reinstall unless explicitly cleared, and Android's
  storage backend changed in v10.0.0 (moved off the deprecated Jetpack `encryptedSharedPreferences`
  wrapper).
- **Prefer HTTPS-verified redirect URIs** (iOS Universal Links / Android App Links) over a
  custom URL scheme where Glean's own backend/auth provider setup allows it, per Apple's and
  Google's own guidance that custom schemes can be claimed by more than one app
  ([Apple](https://developer.apple.com/forums/thread/776365), [Android App Links
  docs](https://developer.android.com/training/app-links)) and per RFC 8252's explicit
  preference for "claimed HTTPS" redirect URIs over private-use URI schemes
  ([RFC 8252 §7.1](https://datatracker.ietf.org/doc/html/rfc8252)). `flutter_appauth` and
  `app_links` both support either redirect-URI style, so this is an auth-provider/backend
  configuration decision, not a package-choice constraint.

---

## 1. `flutter_appauth` vs. manual `url_launcher` + deep-link approach

### What `flutter_appauth` provides

- pub.dev describes it as "an abstraction around the Android and iOS AppAuth SDKs so it can be
  used to communicate with OAuth 2.0 and OpenID Connect providers"
  ([pub.dev/packages/flutter_appauth](https://pub.dev/packages/flutter_appauth)). The GitHub
  README/repo confirms the same framing: "a wrapper for native AppAuth SDKs," organized as a
  monorepo with the plugin and a platform-interface package
  ([github.com/MaikuB/flutter_appauth](https://github.com/MaikuB/flutter_appauth)).
- It therefore genuinely wraps the official native libraries — [AppAuth-iOS and
  AppAuth-Android](https://appauth.io) — rather than reimplementing OAuth logic in Dart. Both of
  those native libraries are themselves the reference implementations of RFC 8252's
  recommendation to use the platform's external user agent
  (`ASWebAuthenticationSession`/`SFSafariViewController` on iOS, Chrome Custom Tabs on Android)
  instead of an embedded webview.
- **PKCE**: pub.dev's own package description states "AppAuth also supports the PKCE extension
  that is required [by] some providers so this plugin should work with them," and the plugin
  generates and reuses a `code_verifier` for the authorization request automatically
  ([pub.dev/packages/flutter_appauth](https://pub.dev/packages/flutter_appauth)). This matches
  AppAuth's own design goal of being an RFC 8252/PKCE-conformant client library — PKCE is not
  something the app author needs to implement by hand when using this package.
- Current version 12.0.2 (checked on pub.dev, published 28 days prior to this research; supports
  Android, iOS, macOS) ([pub.dev/packages/flutter_appauth](https://pub.dev/packages/flutter_appauth)).

### Maintenance status

- CHANGELOG on GitHub shows active recent releases: 12.0.2 (Swift Package Manager compatibility
  fix), 12.0.1 (removed an over-strict assertion on optional `EndSessionRequest` params), and
  12.0.0, which raised the **minimum supported SDK to Flutter 3.38.1 / Dart 3.10**, Android API
  24 (7.0), iOS 13, macOS 10.15, and adopted `UISceneDelegate`
  ([github.com/MaikuB/flutter_appauth/blob/master/flutter_appauth/CHANGELOG.md](https://github.com/MaikuB/flutter_appauth/blob/master/flutter_appauth/CHANGELOG.md)).
  Flutter's own release notes show the current stable channel is Flutter 3.44
  ([docs.flutter.dev/release/release-notes](https://docs.flutter.dev/release/release-notes)), so
  flutter_appauth's SDK floor is comfortably behind current stable — no SDK-support gap for a
  new Glean Flutter app.
- The repo has **84 open issues** as of this research, with issue activity as recent as July
  2026, which indicates an actively-used but not fully triaged project
  ([github.com/MaikuB/flutter_appauth/issues](https://github.com/MaikuB/flutter_appauth/issues)).
  Notable open issues found in that list:
  - #668 (Jul 2026) — feature request for Android `AuthTabIntent` to remove the Custom Tab
    minimize/PiP affordance (an Android 15-era Custom Tabs API, not itself a bug report).
  - #649 (Apr 2026) — `authorizeAndExchangeCode` never completes if the user swipe-dismisses
    `SFSafariViewController` on iOS (a UX/edge-case bug, not a platform-support blocker).
  - #640 (Feb 2026) — an ASP.NET-server-side CSRF/antiforgery issue reported specifically on
    Android but not iOS with v11.0.0.
  - #635 (Nov 2025) — app killed by aggressive Android memory management mid-flow leaves
    `authorizeAndExchangeCode` incomplete (a process-death recovery gap — see §3 below).
  - #667 (Jul 2026) — a Swift Package Manager build error.
  - I did **not** find open issues specifically about "Sign in with Apple" or "Sign in with
    Google" support, or an iOS-18-specific regression, in the portion of the issue list surfaced;
    this should be treated as "not found in this pass," not as confirmed absence, since the
    tracker has 84 open issues and only a subset was visible in the fetch.
- Net assessment: actively maintained, tracks current Flutter/Dart, but — like most community
  OAuth wrapper packages — has a nontrivial open-issue backlog around edge cases (swipe-dismiss,
  process death, Custom Tabs API churn) that Glean should budget QA time against rather than
  assume are solved.

### Manual `url_launcher` + deep-link approach

- The rollout would be: `url_launcher` opens the system browser (via `LaunchMode.externalApplication`,
  which pub.dev's own docs describe as one of the supported launch modes alongside
  `inAppWebView`/`inAppBrowserView`, with automatic fallback if a mode isn't supported on a given
  platform) ([pub.dev/packages/url_launcher](https://pub.dev/packages/url_launcher)) pointed at a
  hand-built authorization URL; a deep-link package catches the redirect back into the app; the
  app manually generates a PKCE `code_verifier`/`code_challenge` pair, tracks `state` (and `nonce`
  if using OIDC), and performs the authorization-code→token exchange itself via `http` or `dio`.
- **`app_links` vs. `uni_links`**: `uni_links`'s own pub.dev listing carries an explicit
  discontinuation notice — "This package is discontinued, but author has suggested
  package:app_links as a replacement" — its last published version (0.5.1) is five years old
  ([pub.dev/packages/uni_links](https://pub.dev/packages/uni_links)). `app_links`, by contrast,
  is at v7.2.1, published 15 days before this research, verified-publisher, and describes itself
  as an "Android App Links, Deep Links, iOs Universal Links and Custom URL schemes handler for
  Flutter (desktop included)," supporting Android/iOS/Linux/macOS/Windows/Web
  ([pub.dev/packages/app_links](https://pub.dev/packages/app_links)). Its GitHub README shows the
  redirect-catching API is a `uriLinkStream` subscription on a singleton `AppLinks` instance, and
  explicitly requires per-platform native setup (documented separately per platform: Android,
  iOS, Linux, macOS, Windows) — i.e. you still have to wire up `AndroidManifest.xml`
  intent-filters and iOS associated domains/URL schemes yourself
  ([github.com/llfbandit/app_links](https://github.com/llfbandit/app_links)). `uni_links` is
  correctly characterized as superseded/unmaintained; `app_links` is the current standard choice
  if you need a deep-link package independent of any OAuth library.
- PKCE itself is a small, well-specified amount of Dart (SHA-256 challenge over a random
  high-entropy verifier per [RFC 7636](https://datatracker.ietf.org/doc/html/rfc8252), which
  RFC 8252 mandates for public native clients — see §3), so "manual PKCE" is not the risky part of
  the DIY approach.

### Trade-offs

| | `flutter_appauth` | `url_launcher` + `app_links` (DIY) |
|---|---|---|
| Dev effort | Low — call `authorizeAndExchangeCode` (or `authorize` + `token`), configure redirect URI per platform | Higher — build auth URL, manage `state`/`nonce`/PKCE by hand, write the token-exchange HTTP call, handle error/cancel paths |
| Spec correctness (PKCE/state) | Handled by AppAuth natively; verified by pub.dev's own package description | Correct only if you implement it correctly — no library holds you to the spec |
| External user agent | Uses `ASWebAuthenticationSession`/Custom Tabs via native AppAuth-iOS/AppAuth-Android — this is RFC 8252's recommended pattern, "in-app browser tabs," retaining full browser security/cookie state | You get this too, *if* you use `LaunchMode.externalApplication` in `url_launcher` (opens the system browser/Custom Tab) rather than an embedded `WebView` — but nothing forces that choice; a developer could accidentally build the RFC-8252-prohibited embedded-webview pattern |
| Maintenance burden | Outsourced to `flutter_appauth`/AppAuth upstream (84 open issues to track, but no OAuth protocol code of your own) | You own the OAuth protocol code indefinitely |
| Redirect-URI flexibility | Supports custom scheme or HTTPS/Universal Links/App Links redirect URIs | Same, via `app_links`, but you assemble it yourself |

**Conclusion**: `flutter_appauth` gets Glean the RFC-8252-conformant pattern (external
user-agent, PKCE, native AppAuth security properties) essentially for free, at the cost of
depending on a community package with an active but nontrivial issue backlog. The DIY path is
only clearly better if there's a concrete provider requirement `flutter_appauth`/AppAuth can't
express — nothing found in this research suggests that's the case for a typical OAuth 2.0/OIDC
provider.

---

## 2. `flutter_secure_storage`: capabilities and platform backing

### Platform backing

- pub.dev's own package description: "A Flutter plugin enabling securely storing sensitive data
  in a key-value pair format using platform-specific secure storage solutions," current version
  **10.3.1**, published 58 days before this research
  ([pub.dev/packages/flutter_secure_storage](https://pub.dev/packages/flutter_secure_storage)).
- **iOS/macOS**: backed by the platform Keychain. The GitHub README explicitly notes that a
  "Keychain Sharing" capability must be added to the app's Debug and Release entitlements for the
  plugin to work, and documents an optional Secure Enclave mode (`useSecureEnclave: true`) that
  encrypts values with a hardware-backed EC key that never leaves the device
  ([github.com/juliansteenbakker/flutter_secure_storage](https://github.com/juliansteenbakker/flutter_secure_storage)).
- **Android**: as of **v10.0.0+**, the plugin moved to a custom cipher implementation — "RSA OAEP
  (key cipher) + AES-GCM (storage cipher)" — backed by the Android Keystore, replacing its
  previous reliance on Jetpack Security's `EncryptedSharedPreferences` wrapper, which the package
  itself flags as deprecated upstream; a `migrateOnAlgorithmChange` option (on by default) handles
  migrating existing values from the old cipher automatically
  ([github.com/juliansteenbakker/flutter_secure_storage](https://github.com/juliansteenbakker/flutter_secure_storage)).
  This is a first-party confirmation (the package's own README) that the underlying
  `EncryptedSharedPreferences` API it used to depend on is considered deprecated by its Android
  maintainers, and that flutter_secure_storage has already migrated away from it — relevant to
  the "Android EncryptedSharedPreferences deprecation status" question.
- Other platforms: Windows (C++ ATL-based secure storage), Linux (requires `libsecret` and a
  running keyring service), Web (works only over HTTPS or `localhost`)
  ([github.com/juliansteenbakker/flutter_secure_storage](https://github.com/juliansteenbakker/flutter_secure_storage)).
  Minimum Android SDK is API 23 (Android 6.0); biometric-gated access needs API 23+, with
  *enforced* biometric requiring API 28+.

### Configuration options (iOS `KeychainAccessibility`)

- The package exposes iOS/macOS accessibility options mirroring Apple's own Keychain protection
  classes, including `first_unlock` (accessible after the first unlock following a reboot) and
  `unlocked` (the package's default — accessible only while the device is unlocked)
  ([github.com/juliansteenbakker/flutter_secure_storage](https://github.com/juliansteenbakker/flutter_secure_storage)).
  Apple's own Keychain data-protection documentation defines the underlying primitives these map
  to — e.g. `kSecAttrAccessibleWhenUnlocked`, `kSecAttrAccessibleAfterFirstUnlock`, and (legacy)
  `kSecAttrAccessibleAlways`
  ([support.apple.com/guide/security/keychain-data-protection](https://support.apple.com/guide/security/keychain-data-protection-secb0694df1a/web)).
  A `first_unlock_this_device`-style "this device only" variant (non-migratory / excluded from
  backup) is also part of Apple's protection-class family, per the same Apple document, which
  notes device-only items are "protected with the UID when being copied from the device during a
  backup, rendering it useless if it's restored to a different device."
- **Uninstall/reinstall persistence gotcha — confirmed via the package's own issue tracker**: the
  flutter_secure_storage GitHub issues include multiple reports of exactly this behavior on iOS —
  #371 "Secure Storage data persists when uninstalling an app on iOS," #82 "data is restored
  after reinstalling the application in IOS," and #156 "How to delete keychain data once the app
  is uninstalled?"
  ([github.com/juliansteenbakker/flutter_secure_storage/issues](https://github.com/juliansteenbakker/flutter_secure_storage/issues)).
  This is a long-known iOS platform characteristic, not a plugin bug: Apple's own developer
  forums confirm it's an implementation detail of the Keychain rather than a documented, guaranteed
  behavior — "the persistence of keychain data across app reinstalls is a side-effect of the
  implementation rather than a feature, and... the behavior should not be relied upon," per an
  Apple staff reply on the forums, and access to a re-deleted/reinstalled app's keychain items
  remains gated by the app's provisioning-profile identity, not by a fresh-install guarantee
  ([developer.apple.com/forums/thread/72271](https://developer.apple.com/forums/thread/72271),
  [developer.apple.com/forums/thread/36442](https://developer.apple.com/forums/thread/36442)).
  **Caveat**: Apple's official Keychain Services / Keychain-data-protection reference pages that
  I could load did not themselves state this persistence behavior explicitly — the only
  confirmation found was in Apple's own developer forums (a semi-official but not strictly
  "documentation" source) and in flutter_secure_storage's issue tracker. Practically for Glean:
  **do not assume sign-out-by-uninstall** for tokens stored in `flutter_secure_storage` on iOS;
  the app must explicitly delete its Keychain items on logout, and should consider deleting them
  again defensively on first launch after a fresh install if "logged out after reinstall" is a
  product requirement.

### Maintenance status

- Actively maintained: v10.3.1 published 58 days before this research
  ([pub.dev/packages/flutter_secure_storage](https://pub.dev/packages/flutter_secure_storage)).
  The v10.0.0 Android cipher rewrite (RSA-OAEP + AES-GCM, replacing the deprecated
  `EncryptedSharedPreferences` wrapper) is itself evidence of active maintenance in response to
  upstream Android platform changes
  ([github.com/juliansteenbakker/flutter_secure_storage](https://github.com/juliansteenbakker/flutter_secure_storage)).
  Platform parity is broad (Android, iOS, macOS, Windows, Linux, Web) but Linux/Web have
  documented extra prerequisites (`libsecret`+keyring daemon; HTTPS/localhost only) that iOS/
  Android don't — worth flagging if Glean ever ships a Linux/web build, though out of scope for
  the initial mobile port.

---

## 3. OAuth redirect callback handling: iOS vs. Android

### Custom URL schemes vs. Universal Links vs. App Links

- **Apple** explicitly discourages custom URL schemes for this purpose: "Custom URL schemes are
  inherently insecure and can be abused by malicious developers, and new uses of custom URL
  schemes are highly discouraged... anyone can provide an app that implements them, so if your
  banking app relies on `bankofme:` URLs opening its app, some free app with billions of installs
  could have a handler for `bankofme:` and scam the users." Universal Links "can't be claimed by
  other apps, because they use standard HTTP or HTTPS links to your website," verified via a file
  uploaded to the developer's own web server, and Apple's explicit recommendation is "where you
  are currently using custom URL schemes, begin migrating to universal links today"
  ([Apple Developer Forums thread citing Apple's own guidance](https://developer.apple.com/forums/thread/776365)).
  Universal Links configuration requires the `com.apple.developer.associated-domains`
  entitlement (`applinks:<domain>`) plus an `apple-app-site-association` file served over HTTPS
  from the domain (general shape confirmed via Apple's Associated Domains documentation page,
  though the exact page body could not be fully retrieved in this pass — flagged as
  lower-confidence and worth a direct re-check against
  [developer.apple.com/documentation/xcode/supporting-associated-domains](https://developer.apple.com/documentation/xcode/supporting-associated-domains)
  before implementation).
- **Google** frames Android App Links the same way: "Android App Links is an enhanced deep
  linking capability that verifies deep links to your own website by establishing a trusted
  association between your app and your website," in contrast to ordinary (unverified) deep
  links, which are "subject to system disambiguation dialog" and don't guarantee a trusted
  app-website relationship ([developer.android.com/training/app-links](https://developer.android.com/training/app-links)).
  Configuration requires `android:autoVerify="true"` on an intent-filter with
  `action=android.intent.action.VIEW`, `category=BROWSABLE`, `category=DEFAULT`, and an
  `https`/`http` `<data>` scheme+host, plus a Digital Asset Links file hosted at
  `https://<host>/.well-known/assetlinks.json`
  ([developer.android.com/training/app-links/verify-android-applinks](https://developer.android.com/training/app-links/verify-android-applinks)).
  Note the documented verification-latency gotcha: "Android 15+: changes can take up to 7 days to
  propagate due to periodic background re-verification," versus "Android 14 and lower: updates
  are only picked up when the app is installed or updated" — relevant if Glean ever needs to
  change its App Links domain post-launch
  ([developer.android.com/training/app-links/verify-android-applinks](https://developer.android.com/training/app-links/verify-android-applinks)).

### Backgrounding / process death during the external-browser redirect

- Because RFC 8252 mandates the *external* user agent (system browser / in-app browser tab) for
  the authorization step ([RFC 8252 §5](https://datatracker.ietf.org/doc/html/rfc8252) — see
  below), the app is necessarily backgrounded for the duration of the sign-in, and on Android in
  particular the OS may kill the app process under memory pressure before the redirect returns.
  This is a live, documented failure mode for the AppAuth-based approach: flutter_appauth issue
  **#635** — "app killed during aggressive memory preservation on Android;
  `authorizeAndExchangeCode` incomplete" (Nov 2025) — and issue **#649** — iOS
  `authorizeAndExchangeCode` never completes if `SFSafariViewController`/`ASWebAuthenticationSession`
  is dismissed by a swipe rather than a normal completion (Apr 2026) — both confirm this is a real
  gap to design around, not a theoretical concern
  ([github.com/MaikuB/flutter_appauth/issues](https://github.com/MaikuB/flutter_appauth/issues)).
  A DIY `url_launcher`+`app_links` implementation faces the identical class of problem (the
  Dart-side `Future` awaiting the browser round-trip is just as vulnerable to process death) and
  gets no additional help recovering from it — Glean's app-state design needs to treat "cold
  start with a pending OAuth redirect URI" as a first-class case regardless of which package is
  chosen, e.g. by re-deriving/reissuing the authorization request rather than assuming continuity
  of in-memory `state`/PKCE-verifier data.

### App Store review posture: WebView vs. `ASWebAuthenticationSession`/Custom Tabs

- Apple's published App Review Guidelines section most directly on point is **4.8, "Login
  Services"**: apps that use a third-party/social login (Facebook Login, Google Sign-In, Log in
  with X, etc.) to set up or authenticate a user's primary account must also offer an equivalent
  login option meeting privacy bars (name+email-only data collection, private-email option, no
  non-consensual ad-tracking use) — with listed exceptions (own-account systems, marketplace apps,
  education/enterprise/government ID systems, or apps that are just a client to one specific
  third-party service) ([developer.apple.com/app-store/review/guidelines](https://developer.apple.com/app-store/review/guidelines/)).
  This guideline is about *which login providers* you must also offer, not about *whether you may
  use a WebView* — I did not find explicit App Store Review Guidelines text mandating
  `ASWebAuthenticationSession` specifically over a WebView for OAuth in the section fetched; that
  requirement, to the extent Apple enforces it in review practice, is not textually present in the
  guidelines page as retrieved, so treat "Apple requires ASWebAuthenticationSession for OAuth" as
  **not directly confirmed** from this pass over the primary source, even though it is
  widely reported in developer community discussion. Related guideline **5.1.1** does separately
  require: apps must let people use the app without login where the core functionality doesn't
  need it; apps offering account creation must offer in-app account deletion; and apps must
  provide a way to revoke a linked social network's credentials from within the app and must not
  store social-network credentials/tokens off-device ([same source](https://developer.apple.com/app-store/review/guidelines/)).
  Independent of the exact review-guideline text, Apple's own API documentation and behavior
  strongly favor `ASWebAuthenticationSession`: it is Apple's purpose-built API for "authenticating
  a user through a web service" and, unlike an app-embedded `WKWebView`, is documented (via
  Apple's `ASWebAuthenticationSessionWebBrowserSessionManager` API and confirmed in Apple
  Developer Forums discussion) to share Safari's persistent cookie jar by default — letting a user
  already signed into an IdP in Safari skip re-entering credentials — unless the app opts into
  `prefersEphemeralWebBrowserSession`
  ([developer.apple.com/documentation/authenticationservices/aswebauthenticationsessionwebbrowsersessionmanager](https://developer.apple.com/documentation/authenticationservices/aswebauthenticationsessionwebbrowsersessionmanager);
  cookie-sharing default behavior corroborated via Apple Developer Forums threads such as
  [developer.apple.com/forums/thread/785421](https://developer.apple.com/forums/thread/785421) and
  [developer.apple.com/forums/thread/663533](https://developer.apple.com/forums/thread/663533) —
  flagged here as forum corroboration rather than a fetched official doc paragraph, since the
  primary API reference page returned only its title in this pass and its full body text could
  not be retrieved).
- **Android / Chrome Custom Tabs**: Google's Custom Tabs documentation states plainly that a
  WebView-based approach has drawbacks Custom Tabs solve — WebViews "don't support all features
  of the web platform, don't share state with the browser and add maintenance overhead" — whereas
  Custom Tabs bring "a shared cookie jar and permissions model so users don't have to sign in to
  sites they are already connected to, or re-grant permissions they've already granted," and
  Google documents a dedicated guide ("Simplify authentication using Auth Tab") for authentication
  workflows specifically ([developer.chrome.com/docs/android/custom-tabs](https://developer.chrome.com/docs/android/custom-tabs)).
  This is the Android analogue of the iOS Safari-cookie-sharing property, and is exactly the
  mechanism AppAuth-Android uses under the hood for `flutter_appauth`.

### PKCE requirement (RFC 8252 / RFC 7636)

- RFC 8252, the IETF "Best Current Practice" document for OAuth 2.0 in native apps, is explicit
  and normative: **"Public native app clients MUST implement the Proof Key for Code Exchange
  (PKCE [RFC7636]) extension to OAuth, and authorization servers MUST support PKCE for such
  clients"** ([datatracker.ietf.org/doc/html/rfc8252](https://datatracker.ietf.org/doc/html/rfc8252)).
  It also states the *external user agent* requirement directly: **"native apps MUST use an
  external user-agent to perform OAuth authorization requests... native apps MUST NOT use
  embedded user-agents to perform authorization requests,"** because an embedded webview lets the
  host app access authentication credentials, cookies, and user input — violating least privilege
  — while noting it **"is RECOMMENDED, for usability reasons, that apps use in-app browser tabs
  for the authorization request"** on platforms that support them (i.e. exactly the
  `ASWebAuthenticationSession`/Custom Tabs pattern), provided those tabs retain full browser
  security/cookie state ([same RFC](https://datatracker.ietf.org/doc/html/rfc8252)).
- On redirect URIs specifically, RFC 8252 §7 lays out three supported types and a preference
  order: **"claimed HTTPS" URIs** (Universal Links/App Links) "SHOULD [be used]... over the other
  options where possible" because the OS itself guarantees the redirect goes only to the
  legitimate app; **private-use URI schemes** (custom schemes, in reverse-domain form, e.g.
  `com.example.app:/oauth2redirect`) are supported but weaker, exactly because (per RFC 7636's
  motivating threat model, which RFC 8252 cites) multiple apps can register the same scheme and
  intercept the code — this is the concrete mechanism behind Apple's/Google's "custom schemes can
  be claimed by other apps" warnings cited above; and **loopback interface redirects**
  (`http://127.0.0.1:{port}/...`) for desktop use cases
  ([datatracker.ietf.org/doc/html/rfc8252](https://datatracker.ietf.org/doc/html/rfc8252)).

### Redirect URI configuration: iOS vs. Android

| | iOS | Android |
|---|---|---|
| Custom scheme | Declared via `CFBundleURLTypes` in `Info.plist` | Declared via an intent-filter `<data android:scheme="...">` in `AndroidManifest.xml` (no `autoVerify`, no web association) |
| Claimed-HTTPS (Universal Links / App Links) | `com.apple.developer.associated-domains` entitlement (`applinks:<domain>`) + `apple-app-site-association` JSON served over HTTPS from the domain ([developer.apple.com/documentation/xcode/supporting-associated-domains](https://developer.apple.com/documentation/xcode/supporting-associated-domains) — page title confirmed, full body not retrieved in this pass, re-verify before implementation) | Intent-filter with `android:autoVerify="true"`, `action.VIEW` + categories `BROWSABLE`+`DEFAULT`, `https` `<data>` host, plus `assetlinks.json` served at `https://<host>/.well-known/assetlinks.json` ([developer.android.com/training/app-links/verify-android-applinks](https://developer.android.com/training/app-links/verify-android-applinks)) |
| Verification latency / risk if misconfigured | Not directly documented in the pages retrieved in this pass | Android 15+: up to 7 days for changes to fully propagate via periodic re-verification; Android 14 and earlier only re-verify on install/update ([developer.android.com/training/app-links/verify-android-applinks](https://developer.android.com/training/app-links/verify-android-applinks)) |

For a Flutter app using `flutter_appauth` or `app_links`, both custom-scheme and claimed-HTTPS
redirect URIs are supported by the packages themselves — the choice between them is a matter of
what Glean's auth provider/backend can register as a redirect URI, weighed against RFC 8252's and
Apple's/Google's stated preference for the claimed-HTTPS form.

---

## Sources consulted

- [pub.dev/packages/flutter_appauth](https://pub.dev/packages/flutter_appauth)
- [github.com/MaikuB/flutter_appauth](https://github.com/MaikuB/flutter_appauth) (README, CHANGELOG, issues)
- [pub.dev/packages/app_links](https://pub.dev/packages/app_links)
- [github.com/llfbandit/app_links](https://github.com/llfbandit/app_links)
- [pub.dev/packages/uni_links](https://pub.dev/packages/uni_links)
- [pub.dev/packages/url_launcher](https://pub.dev/packages/url_launcher)
- [pub.dev/packages/flutter_secure_storage](https://pub.dev/packages/flutter_secure_storage)
- [github.com/juliansteenbakker/flutter_secure_storage](https://github.com/juliansteenbakker/flutter_secure_storage) (README, issues)
- [RFC 8252 — OAuth 2.0 for Native Apps](https://datatracker.ietf.org/doc/html/rfc8252)
- [developer.apple.com/documentation/authenticationservices/aswebauthenticationsession](https://developer.apple.com/documentation/authenticationservices/aswebauthenticationsession)
- [developer.apple.com/documentation/authenticationservices/aswebauthenticationsessionwebbrowsersessionmanager](https://developer.apple.com/documentation/authenticationservices/aswebauthenticationsessionwebbrowsersessionmanager)
- Apple Developer Forums: [thread/776365](https://developer.apple.com/forums/thread/776365) (Universal Links vs. custom schemes), [thread/72271](https://developer.apple.com/forums/thread/72271) and [thread/36442](https://developer.apple.com/forums/thread/36442) (Keychain persistence across uninstall), [thread/785421](https://developer.apple.com/forums/thread/785421) and [thread/663533](https://developer.apple.com/forums/thread/663533) (ASWebAuthenticationSession cookie sharing)
- [developer.apple.com/documentation/xcode/supporting-associated-domains](https://developer.apple.com/documentation/xcode/supporting-associated-domains)
- [support.apple.com/guide/security/keychain-data-protection](https://support.apple.com/guide/security/keychain-data-protection-secb0694df1a/web)
- [developer.apple.com/app-store/review/guidelines](https://developer.apple.com/app-store/review/guidelines/)
- [developer.android.com/training/app-links](https://developer.android.com/training/app-links)
- [developer.android.com/training/app-links/verify-android-applinks](https://developer.android.com/training/app-links/verify-android-applinks)
- [developer.chrome.com/docs/android/custom-tabs](https://developer.chrome.com/docs/android/custom-tabs)
- [docs.flutter.dev/release/release-notes](https://docs.flutter.dev/release/release-notes)

**Known gaps in this pass** (recommend re-verifying directly before implementation):
Apple's Associated Domains documentation page and the ASWebAuthenticationSession API reference
page both returned only their titles to the fetch tool used here, so the associated-domains
setup steps and the cookie-sharing default are corroborated via Apple Developer Forums and
secondary confirmation rather than a fully-quoted primary doc paragraph. No definitive statement
was found in the fetched App Store Review Guidelines text that Apple *requires*
`ASWebAuthenticationSession` (as opposed to it being the de facto safe/well-supported choice) for
OAuth flows specifically.
