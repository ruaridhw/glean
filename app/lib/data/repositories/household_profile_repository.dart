// Household profile persistence. `user_id` is the Cognito user sub, so the table is user-scoped by
// construction and one user can only ever have one profile.
import '../database.dart';
import '../models/household_profile.dart';

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
