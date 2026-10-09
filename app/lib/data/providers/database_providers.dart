// The database connection and the current-user-id seam. Every other
// provider in `lib/data/providers/` builds on these two.
import 'package:drift_flutter/drift_flutter.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../database.dart';

/// The single `GleanDatabase` instance for the app's lifetime. Local SQLite
/// is the sole source of truth for user data (FLUTTER_MIGRATION.md §3), so
/// this provider is the root of the whole data layer.
final Provider<GleanDatabase> gleanDatabaseProvider = Provider<GleanDatabase>((
  ref,
) {
  final db = GleanDatabase(driftDatabase(name: 'glean'));
  ref.onDispose(db.close);
  return db;
});

/// Seam for the AUTH module: overridden with the signed-in user's Cognito
/// sub in `lib/main.dart` (real session, via [AuthController]) and
/// `lib/main_e2e.dart` (bypassed session). Every user-scoped read/write in
/// this data layer takes a user id as a parameter rather than reading this
/// provider directly — repositories stay auth-agnostic, and
/// `lib/features/**` providers are the ones expected to `ref.watch` this.
///
/// Deliberately has no fallback default: reading it before AUTH's override
/// applies (in production/e2e) or before a test overrides it (in
/// `ProviderScope`) is a wiring bug, and should fail loudly rather than
/// silently scope every query to a placeholder user id.
final Provider<String> currentUserIdProvider = Provider<String>((ref) {
  throw UnimplementedError(
    'currentUserIdProvider has no default. Override it with the signed-in '
    'user id (lib/main.dart / lib/main_e2e.dart already do) or with a '
    'fixed value in ProviderScope(overrides: ...) for tests/previews.',
  );
});

/// Resolves once the database has successfully opened, or surfaces the
/// `AsyncValue.error` from a failed open. The app shell (router/orchestrator)
/// watches this to show a real error state instead of proceeding with a
/// possibly-unusable database (§6 Settings & auth; AC-DATA-12) — RN's
/// DB-init failure was caught and silently ignored.
final FutureProvider<void> databaseReadyProvider = FutureProvider<void>((
  ref,
) async {
  final db = ref.watch(gleanDatabaseProvider);
  await db.customStatement('SELECT 1');
});
