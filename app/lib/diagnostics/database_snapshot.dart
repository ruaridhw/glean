import 'dart:io';

import '../data/database.dart';

/// Writes a consistent, standalone copy of [db] to `glean-export.sqlite` in [into] and returns it.
///
/// `VACUUM INTO` copies from one read transaction, so the result is a valid database even while the app is
/// writing; copying the live file would not be (it can miss pages still in the write-ahead log). The live
/// database is only read.
Future<File> snapshotDatabase(GleanDatabase db, Directory into) async {
  final File target = File('${into.path}/glean-export.sqlite');
  if (target.existsSync()) target.deleteSync();
  await db.customStatement('VACUUM INTO ?', <Object?>[target.path]);
  return target;
}
