// User-config persistence. `id` is the Cognito user sub, so this table is user-scoped by construction.
import 'dart:convert';

import 'package:drift/drift.dart';

import '../database.dart';
import '../models/user_config_view.dart';

class UserConfigRepository {
  UserConfigRepository(this._db);

  final GleanDatabase _db;

  /// Emits [UserConfigView.defaults] until [userId] has saved settings, then the saved row; a stream, so the
  /// settings screen never needs a manual reload.
  Stream<UserConfigView> watch(String userId) {
    final query = _db.select(_db.userConfig)..where((t) => t.id.equals(userId));
    return query.watchSingleOrNull().map(
      (row) => row == null ? UserConfigView.defaults(userId) : _map(row),
    );
  }

  Future<UserConfigView> get(String userId) async {
    final row = await (_db.select(
      _db.userConfig,
    )..where((t) => t.id.equals(userId))).getSingleOrNull();
    return row == null ? UserConfigView.defaults(userId) : _map(row);
  }

  /// First-run completion for [userId]. `false` for a user with no row at
  /// all — the same "no row yet" fallback [get]/[watch] apply to every other
  /// column.
  Stream<bool> watchOnboardingCompleted(String userId) {
    final query = _db.select(_db.userConfig)..where((t) => t.id.equals(userId));
    return query.watchSingleOrNull().map(
      (row) => row?.onboardingCompleted ?? false,
    );
  }

  /// Flips [userId]'s `onboardingCompleted` to true, leaving every other
  /// column untouched on conflict (mirrors [save]'s upsert shape, but
  /// scoped to just this one column so a settings save that happens to
  /// race it can never clobber the other).
  Future<void> markOnboardingCompleted(String userId) {
    return _db
        .into(_db.userConfig)
        .insertOnConflictUpdate(
          UserConfigCompanion.insert(
            id: userId,
            onboardingCompleted: const Value(true),
          ),
        );
  }

  Future<void> save(UserConfigView config) {
    return _db
        .into(_db.userConfig)
        .insertOnConflictUpdate(
          UserConfigCompanion.insert(
            id: config.id,
            purchaseTolerance: Value(config.purchaseTolerance),
            preferredServings: Value(config.preferredServings),
            mealsPerWeek: Value(config.mealsPerWeek),
            dietaryFlags: Value(jsonEncode(config.dietaryFlags)),
            maxActiveTimeMins: Value(config.maxActiveTimeMins),
          ),
        );
  }

  UserConfigView _map(UserConfigData row) => UserConfigView(
    id: row.id,
    purchaseTolerance: row.purchaseTolerance,
    preferredServings: row.preferredServings,
    mealsPerWeek: row.mealsPerWeek,
    dietaryFlags: (jsonDecode(row.dietaryFlags) as List).cast<String>(),
    maxActiveTimeMins: row.maxActiveTimeMins,
  );
}
