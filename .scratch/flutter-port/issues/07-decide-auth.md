Type: grilling
Status: resolved
Blocked by: 02

## Question

Given the research in ticket 02 (`.scratch/flutter-port/research/auth.md`), decide the Flutter auth architecture: which OAuth package/approach, how the redirect callback is handled on iOS/Android, and which secure-storage package holds tokens. Confirm it preserves the current login UX (same OAuth provider/flow shape) unless the review surfaces a reason to change it — check that against the current `mobile/app/sign-in.tsx` and `mobile/src/auth/` behavior.

## Answer

- **Identity provider**: unchanged — AWS Cognito Hosted UI, federating to Google (`identity_provider: "Google"`), PKCE. Straight port, no reason to reconsider.
- **Packages**: `flutter_appauth` (talks to Cognito's Hosted UI the same way `expo-auth-session` does today) + `flutter_secure_storage` for tokens (replacing `expo-secure-store`).
- **Redirect callback**: keep the custom URL scheme (`glean://auth/callback`) for now — universal links/app links would be more RFC-8252-aligned but require hosting domain-verification files, which isn't proportionate to add to this port's critical path. Deferred as [ticket 19](issues/19-later-migrate-to-universal-links.md) for once a production domain exists.
- **Token clearing on logout**: iOS Keychain survives app uninstall/reinstall (per ticket 02's research), so `signOut()` must explicitly clear stored tokens rather than relying on reinstall-as-signout — this already matches the current app's `authStorage.clearTokens()` behavior, just needs to carry forward.
- **Dev/test auth bypass**: carry forward the current `EXPO_PUBLIC_AUTH_BYPASS`/`EXPO_PUBLIC_AUTH_BYPASS_USER_SUB` pattern as Dart `--dart-define` compile-time flags, injecting a fake authenticated session — needed so widget tests and the `integration_test` suite can exercise authenticated screens without a real OAuth round-trip. Feeds directly into ticket 16.
