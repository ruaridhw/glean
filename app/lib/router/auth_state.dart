/// The router's auth-state seam.
///
/// Deliberately just an interface, not the real state: `lib/auth/**` owns
/// real auth state (Cognito tokens via `flutter_appauth` +
/// `flutter_secure_storage`) and overrides [authStatusProvider] at the
/// `ProviderScope` root (`lib/main.dart`, `lib/main_e2e.dart`) with a
/// notifier backed by [AuthController] — see `lib/auth/auth_controller.dart`.
/// The router only depends on this provider's type and name, not on how it's
/// produced, which is what keeps this file a stable seam rather than a
/// dependency on `lib/auth/**` itself.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Coarse auth state the router gates navigation on.
///
/// `expired` is deliberately distinct from `signedOut`: per
/// FLUTTER_MIGRATION.md §5 / AC-AUTH-04, a token expiry must not evict the
/// user from their (fully local) data — it should only gate AI-backed
/// features behind a "signed out" banner, which is a feature-level concern.
/// The router's redirect therefore only fires for `signedOut`.
enum AuthStatus { signedOut, active, expired }

/// Notifier backing [authStatusProvider]. Defaults to `active` so the app
/// stays navigable wherever this provider is used unoverridden (widget
/// tests/previews); the production and e2e entrypoints both override it
/// with a notifier seeded from real (or bypassed) session state instead.
class AuthStatusNotifier extends Notifier<AuthStatus> {
  @override
  AuthStatus build() => AuthStatus.active;

  /// [AuthController] calls the real equivalent of this after
  /// sign-in/out/refresh. Exposed as a plain setter (rather than e.g. only
  /// via `overrideWith`) so tests can flip status on a live provider to
  /// exercise the redirect.
  void setStatus(AuthStatus status) => state = status;
}

/// Tests override this via `authStatusProvider.overrideWith(...)`, or drive
/// it live through `ref.read(authStatusProvider.notifier).setStatus(...)`.
final NotifierProvider<AuthStatusNotifier, AuthStatus> authStatusProvider =
    NotifierProvider<AuthStatusNotifier, AuthStatus>(AuthStatusNotifier.new);
