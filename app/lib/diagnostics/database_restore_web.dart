import 'dart:io';

import '../data/database.dart';

/// Refuses a restore: the web build's database lives in the browser, so there is no file to replace. Settings
/// disables the action in this build; this is the guard for any other caller.
Future<void> restoreDatabase({
  required File backup,
  required GleanDatabase live,
  required File liveFile,
}) => throw UnsupportedError(
  'Restoring a database backup is not available in the web build.',
);
