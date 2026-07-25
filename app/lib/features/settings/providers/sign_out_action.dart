/// Settings' seam onto the AUTH module (`lib/auth/**`, not yet built — see
/// IMPLEMENTATION.md's module contract).
///
/// FLUTTER_MIGRATION.md §6 is explicit: "Sign-out lives here [Settings],
/// fires a haptic, and clears tokens explicitly (that behaviour belongs to
/// AUTH — call their action, don't reimplement it)." Settings has no way to
/// clear a Cognito token today because nothing has written that code yet, so
/// this is the smallest interface Settings needs in the meantime: something
/// callable that ends the session.
///
/// The default implementation only flips `lib/router/auth_state.dart`'s
/// [authStatusProvider] to [AuthStatus.signedOut] — which is real behaviour
/// (it already drives the router's redirect-to-sign-in, per that file's own
/// "AUTH should replace this" doc comment) but is *not* token-clearing.
/// **Required follow-up for AUTH**: override this provider with the real
/// action (revoke + delete tokens via `flutter_secure_storage`, then set
/// [AuthStatus.signedOut]) once `lib/auth/**` lands, so Settings never needs
/// to change its call site. Deliberately does not touch any drift table —
/// signing out must not wipe local user data (AC-DATA-09).
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../router/auth_state.dart';

/// A no-argument, no-return async action. Kept as a plain function type
/// (rather than a class with one method) because that's all Settings needs
/// to call — AUTH can swap the implementation freely without Settings ever
/// importing an AUTH type.
typedef SignOutAction = Future<void> Function();

final Provider<SignOutAction> signOutActionProvider = Provider<SignOutAction>((
  Ref ref,
) {
  return () async {
    ref.read(authStatusProvider.notifier).setStatus(AuthStatus.signedOut);
  };
});
