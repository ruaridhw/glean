import 'dart:io';

import '../data/database.dart';

/// Replaces [live]'s database file, [liveFile], with the backup at [backup].
///
/// [live] is closed; the caller opens the restored file afterwards.
Future<void> restoreDatabase({
  required File backup,
  required GleanDatabase live,
  required File liveFile,
}) async {
  final File staged = File('${liveFile.path}.restore-staging');
  backup.copySync(staged.path);
  await live.close();
  staged.renameSync(liveFile.path);
}
