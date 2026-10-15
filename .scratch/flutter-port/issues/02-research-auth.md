Type: research
Status: resolved

## Question

The current app's auth flow uses `expo-auth-session` (OAuth authorization-code flow), `expo-secure-store` for token storage, a sign-in screen, and a deep-link callback route. Research the standard Flutter equivalents as of 2026: `flutter_appauth` vs a manual `url_launcher` + custom-scheme/deep-link approach, and `flutter_secure_storage` for token storage. Cover how each handles the OAuth redirect callback on both iOS and Android, and any known gotchas with app-links/universal-links setup. Write findings to `.scratch/flutter-port/research/auth.md`, citing official docs and package repos.

## Answer

`flutter_appauth` (v12.0.2, wraps native AppAuth-iOS/AppAuth-Android) is recommended over hand-rolling `url_launcher` + `app_links` — it gives the RFC 8252 external-user-agent pattern (`ASWebAuthenticationSession` on iOS / Chrome Custom Tabs on Android) and PKCE automatically, though it carries a nontrivial open-issue backlog (~84), including process-death/swipe-dismiss edge cases during the browser redirect that need designing around regardless of package choice.

`flutter_secure_storage` (v10.3.1) is the direct analogue of `expo-secure-store` — iOS Keychain, Android Keystore-derived AES-GCM/RSA-OAEP (post-v10, replacing the deprecated `EncryptedSharedPreferences` path). Its issue tracker confirms iOS Keychain items **survive app uninstall/reinstall** — Glean must explicitly clear tokens on logout rather than relying on reinstall-as-signout.

`uni_links` is confirmed discontinued in favor of `app_links`; both Apple/Google platform docs and RFC 8252 favor claimed-HTTPS redirect URIs (Universal Links/App Links) over custom URL schemes, since schemes can be claimed by multiple apps.

Flagged gap for manual re-verification before implementation: Apple's Associated Domains page and the `ASWebAuthenticationSession` API reference only returned page titles when fetched during this research session, so those specific claims currently rest on Apple Developer Forum corroboration rather than a directly quoted doc passage — worth a direct check when ticket 07 is resolved.

**Follow-up (during ticket 07):** re-fetched both. `ASWebAuthenticationSession` confirmed directly — it presents a sandboxed browser-based OAuth session, shares cookies/session with system Safari for SSO, and calls a completion handler with the redirect URL once your specified callback URL is hit. Associated Domains' page still only returned its title (JS-rendered), so that claim still rests on general/community knowledge rather than a directly quoted passage — but the mechanics (entitlements + `apple-app-site-association` file mapping URL paths to app capabilities) are uncontroversial and consistent across every secondary source, so this is treated as settled enough to proceed.

Full findings + citations: `.scratch/flutter-port/research/auth.md` on branch `worktree-agent-ad8605867e75b1fd3` (worktree `/home/ruaridh/glean/.claude/worktrees/agent-ad8605867e75b1fd3`, commit `b47df10`) — not yet merged into `flutter-port`.
