/// Why a restore was refused. Shared by both database_restore implementations, so the Settings screen catches the
/// same types whichever platform it was built for.
library;

/// The backup was written by a newer build of the app than this one, so this build cannot migrate it.
class BackupTooNewException implements Exception {
  const BackupTooNewException({
    required this.backupVersion,
    required this.appVersion,
  });

  final int backupVersion;
  final int appVersion;

  @override
  String toString() =>
      'This backup is from a newer version of Glean (database v$backupVersion; '
      'this build reads up to v$appVersion). Update the app to restore it. '
      'Your current data has not been changed.';
}

/// The restore failed after the live connection was closed. The previous database file is still in place (the
/// swap is a single rename), but the closed connection is unusable: the caller must open the file again.
class RestoreInterruptedException implements Exception {
  const RestoreInterruptedException(this.cause);

  final Object cause;

  @override
  String toString() =>
      'The restore was interrupted ($cause). '
      'Your current data has not been changed.';
}

/// The backup is not a usable Glean database (not SQLite, cut short, or failing its integrity check).
class BackupInvalidException implements Exception {
  const BackupInvalidException(this.reason);

  final String reason;

  @override
  String toString() =>
      'This backup is not a usable Glean database ($reason). '
      'Your current data has not been changed.';
}
