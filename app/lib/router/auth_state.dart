/// The router's auth-state seam.
///
/// **Follow-up required**: the AUTH module (`lib/auth/**`, a later wave)
/// owns real auth state (Cognito tokens via `flutter_appauth` +
/// `flutter_secure_storage`). This file is the smallest interface the router
/// needs in the meantime — a single provider it can watch to decide whether
/// to redirect to sign-in. AUTH should replace [authStatusProvider]'s
/// definition (or override it at the `ProviderScope` root) with one backed
/// by real token state; the router only depends on the provider's type and
/// name, not on how it's produced.
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
/// (and every other module under development in parallel) is navigable
/// before the AUTH module exists.
class AuthStatusNotifier extends Notifier<AuthStatus> {
  @override
  AuthStatus build() => AuthStatus.active;

  /// AUTH will call the real equivalent of this after sign-in/out/refresh.
  /// Exposed as a plain setter (rather than e.g. only via `overrideWith`) so
  /// tests can flip status on a live provider to exercise the redirect.
  void setStatus(AuthStatus status) => state = status;
}

/// Tests override this via `authStatusProvider.overrideWith(...)`, or drive
/// it live through `ref.read(authStatusProvider.notifier).setStatus(...)`.
final NotifierProvider<AuthStatusNotifier, AuthStatus> authStatusProvider =
    NotifierProvider<AuthStatusNotifier, AuthStatus>(AuthStatusNotifier.new);
