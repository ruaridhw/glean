// Ported from `mobile/src/db/config.ts`. `id` is the Cognito user sub, so
// this table was already user-scoped in RN — no schema change needed here,
// unlike the other four tables (FLUTTER_MIGRATION.md §3).
import 'dart:convert';

import 'package:drift/drift.dart';

import '../database.dart';
import '../models/user_config_view.dart';

class UserConfigRepository {
  UserConfigRepository(this._db);

  final GleanDatabase _db;

  /// Emits [UserConfigView.defaults] until [userId] has ever saved
  /// settings, then the saved row — mirrors RN's "no row yet" fallback in
  /// `getUserConfig`, but as a stream so the settings screen never needs a
  /// manual reload.
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
