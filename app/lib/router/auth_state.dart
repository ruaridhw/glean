/// The router's view of the session.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_controller.dart';

/// Coarse auth state the router gates navigation on.
///
/// `expired` is deliberately distinct from `signedOut`: a token expiry must
/// not evict the user from their (fully local) data — it only gates
/// AI-backed features behind the signed-out banner, a feature-level concern.
/// The router's redirect therefore only fires for `signedOut`.
enum AuthStatus { signedOut, active, expired }

/// Derived from [authControllerProvider], the only place session state is
/// held. To change it, drive the controller (`signIn`/`signOut`, or
/// `debugSetSnapshot` in a test).
final Provider<AuthStatus> authStatusProvider = Provider<AuthStatus>(
  (Ref ref) => ref.watch(
    authControllerProvider.select((AuthSessionSnapshot s) => s.status),
  ),
);
