// Household profile persistence. `user_id` is the Cognito user sub, so the table is user-scoped by
// construction and one user can only ever have one profile.
import 'dart:convert';

import '../database.dart';
import '../models/household_profile.dart';

class ProfileInterviewConflict implements Exception {
  const ProfileInterviewConflict();
}

class HouseholdProfileRepository {
  HouseholdProfileRepository(this._db);

  final GleanDatabase _db;

  /// The profile [userId] confirmed in the interview, or `null` before they have one. A row this build cannot
  /// decode reads as `null` rather than failing the screens that ask.
  Future<HouseholdProfile?> get(String userId) async {
    final HouseholdProfileRow? row = await (_db.select(
      _db.householdProfiles,
    )..where((t) => t.userId.equals(userId))).getSingleOrNull();
    return row == null ? null : HouseholdProfile.decode(row.profileJson);
  }

  /// Emits the stored profile and re-emits whenever it changes, so Settings can read it without a reload.
  Stream<HouseholdProfile?> watch(String userId) {
    final query = _db.select(_db.householdProfiles)
      ..where((t) => t.userId.equals(userId));
    return query.watchSingleOrNull().map(
      (HouseholdProfileRow? row) =>
          row == null ? null : HouseholdProfile.decode(row.profileJson),
    );
  }

  /// Reads [userId]'s profile (an empty one before they have any), applies [change] and stores the result, in
  /// one transaction so two edits in quick succession never write over each other. Returns what was stored.
  Future<HouseholdProfile> update({
    required String userId,
    required HouseholdProfile Function(HouseholdProfile current) change,
  }) {
    return _db.transaction(() async {
      final HouseholdProfile next = change(
        await get(userId) ?? const HouseholdProfile(),
      );
      await save(userId: userId, profile: next);
      return next;
    });
  }

  /// Confirms only the fields the interview accepted, preserving the latest independent memory.
  /// A newer answer to any of these fields requires another review, never a silent overwrite.
  Future<void> confirmInterview({
    required String userId,
    required HouseholdProfile baseline,
    required HouseholdProfile candidate,
    required Set<String> fields,
  }) async {
    const Set<String> protected = <String>{
      'version',
      'notes',
      'dismissed_notes',
      'interviewed_at',
    };
    final Map<String, dynamic> before = baseline.toJson();
    final Map<String, dynamic> revised = candidate.toJson();
    if (fields.any(
      (String field) => !before.containsKey(field) || protected.contains(field),
    )) {
      throw ArgumentError('The interview cannot change these fields');
    }
    await _db.transaction(() async {
      final HouseholdProfile current =
          await get(userId) ?? const HouseholdProfile();
      final Map<String, dynamic> latest = current.toJson();
      for (final String field in fields) {
        if (jsonEncode(latest[field]) != jsonEncode(before[field])) {
          throw const ProfileInterviewConflict();
        }
      }
      for (final String field in fields) {
        latest[field] = revised[field];
      }
      latest['interviewed_at'] = revised['interviewed_at'];
      await save(userId: userId, profile: HouseholdProfile.fromJson(latest));
    });
  }

  /// Stores [profile] as [userId]'s one profile, replacing whatever was there. [now] is for tests; production
  /// passes nothing and the row is stamped with the current time.
  Future<void> save({
    required String userId,
    required HouseholdProfile profile,
    DateTime? now,
  }) {
    return _db
        .into(_db.householdProfiles)
        .insertOnConflictUpdate(
          HouseholdProfilesCompanion.insert(
            userId: userId,
            profileJson: profile.encode(),
            updatedAt: (now ?? DateTime.now()).toUtc().toIso8601String(),
          ),
        );
  }
}
