// The database connection and the current-user-id seam. Every other
// provider in `lib/data/providers/` builds on these two.
import 'package:drift_flutter/drift_flutter.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/auth_controller.dart';
import '../database.dart';

/// The single `GleanDatabase` instance for the app's lifetime; the root of the data layer.
final Provider<GleanDatabase> gleanDatabaseProvider = Provider<GleanDatabase>((
  ref,
) {
  final db = GleanDatabase(driftDatabase(name: 'glean'));
  ref.onDispose(db.close);
  return db;
});

/// The signed-in user's stable Cognito sub, from [authControllerProvider].
/// Every user-scoped read/write in this data layer takes a user id as a
/// parameter rather than reading this provider directly — repositories stay
/// auth-agnostic, and `lib/features/**` providers are the ones expected to
/// `ref.watch` this.
///
/// An expired session still resolves its id, so local reads keep working.
/// Signed out, it throws rather than silently scoping every query to a
/// placeholder id — the router keeps a signed-out user on the sign-in
/// screen, which reads no user data.
final Provider<String> currentUserIdProvider = Provider<String>((ref) {
  final String? id = ref.watch(
    authControllerProvider.select((AuthSessionSnapshot s) => s.userId),
  );
  if (id == null) {
    throw StateError('currentUserIdProvider read while signed out');
  }
  return id;
});

/// Resolves once the database has opened, or surfaces the `AsyncValue.error` from a failed open, so the app
/// shows a real error state instead of proceeding with an unusable database.
final FutureProvider<void> databaseReadyProvider = FutureProvider<void>((
  ref,
) async {
  final db = ref.watch(gleanDatabaseProvider);
  await db.customStatement('SELECT 1');
});
