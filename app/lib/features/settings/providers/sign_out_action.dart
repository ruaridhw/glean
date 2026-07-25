/// Settings' seam onto the AUTH module (`lib/auth/**`).
///
/// FLUTTER_MIGRATION.md §6 is explicit: "Sign-out lives here [Settings],
/// fires a haptic, and clears tokens explicitly (that behaviour belongs to
/// AUTH — call their action, don't reimplement it)." This typedef is the
/// smallest interface Settings needs to call that behaviour without
/// importing an AUTH type directly.
///
/// The default implementation below only flips `lib/router/auth_state.dart`'s
/// [authStatusProvider] to [AuthStatus.signedOut] — real behaviour (it
/// already drives the router's redirect-to-sign-in) but *not*
/// token-clearing. `lib/main.dart` overrides this provider with the real
/// action (revoke + delete tokens via `flutter_secure_storage`, then set
/// [AuthStatus.signedOut]) via [AuthController.signOut] — see that
/// override's call site for the wiring. Settings never needed to change its
/// call site. Deliberately does not touch any drift table — signing out
/// must not wipe local user data (AC-DATA-09).
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
