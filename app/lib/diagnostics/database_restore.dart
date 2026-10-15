import 'dart:io';

import 'package:drift/native.dart';

import '../data/database.dart';

/// Replaces [live]'s database file, [liveFile], with the backup at [backup].
///
/// The backup is copied beside the live file and opened there first, which runs the app's normal migrations on
/// the copy, so an older backup arrives at the current schema. [live] is closed; the caller opens the restored
/// file afterwards.
Future<void> restoreDatabase({
  required File backup,
  required GleanDatabase live,
  required File liveFile,
}) async {
  final File staged = File('${liveFile.path}.restore-staging');
  backup.copySync(staged.path);
  final GleanDatabase candidate = GleanDatabase(NativeDatabase(staged));
  try {
    await candidate.customSelect('PRAGMA integrity_check').get();
  } finally {
    await candidate.close();
  }
  await live.close();
  staged.renameSync(liveFile.path);
}
