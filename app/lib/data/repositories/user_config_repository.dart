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

  /// Whether [userId] groups the Shopping tab by store section on this device. `false` until first turned on.
  Stream<bool> watchGroupShoppingBySection(String userId) {
    final query = _db.select(_db.userConfig)..where((t) => t.id.equals(userId));
    return query.watchSingleOrNull().map(
      (row) => row?.groupShoppingBySection ?? false,
    );
  }

  /// Writes only this column, so it neither clobbers nor is clobbered by [save].
  Future<void> setGroupShoppingBySection(String userId, bool grouped) {
    return _db
        .into(_db.userConfig)
        .insertOnConflictUpdate(
          UserConfigCompanion.insert(
            id: userId,
            groupShoppingBySection: Value(grouped),
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
    dietaryFlags: _withLegacyNutFreeSplit(
      (jsonDecode(row.dietaryFlags) as List).cast<String>(),
    ),
    maxActiveTimeMins: row.maxActiveTimeMins,
  );
}

const String _treeNutFreeFlag = 'Tree-nut-free';
const String _peanutFreeFlag = 'Peanut-free';

/// Older builds stored one "Nut-Free" flag. It stands for both allergies, so a
/// household that chose it keeps both and nothing becomes less strict. The
/// stored list is only rewritten on the next save, so no schema step is needed.
List<String> _withLegacyNutFreeSplit(List<String> stored) {
  final flags = <String>[];
  for (final flag in stored) {
    final replacement = flag.trim().toLowerCase() == 'nut-free'
        ? const [_treeNutFreeFlag, _peanutFreeFlag]
        : [flag];
    for (final next in replacement) {
      if (!flags.contains(next)) flags.add(next);
    }
  }
  return flags;
}
