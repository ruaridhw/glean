import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../api/api_client.dart';
import '../api/models/diagnostics.dart';
import '../api/providers/api_providers.dart';
import '../data/providers/database_providers.dart';
import 'database_restore.dart';
import 'diagnostics_exporter.dart';

/// Where the live database file is: `drift_flutter` keeps `glean.sqlite` in the application documents directory.
final Provider<Future<File> Function()> databaseFileProvider =
    Provider<Future<File> Function()>(
      (ref) =>
          () async => File(
            '${(await getApplicationDocumentsDirectory()).path}/glean.sqlite',
          ),
    );

/// The signed-in user's backups, as the server lists them: prepared first, then newest first.
final FutureProvider<List<BackupSummary>>
backupListProvider = FutureProvider.autoDispose<List<BackupSummary>>(
  (ref) => ref.watch(apiClientProvider).listBackups(),
  // A failed listing is shown to the user, who retries by reopening the sheet; no silent backoff loop.
  retry: (int _, Object _) => null,
);

/// Downloads [BackupSummary] and replaces the phone's database with it, then rebuilds everything that reads the
/// database so the app shows the restored state. Throws [BackupTooNewException] or [BackupInvalidException]
/// without touching the current data.
typedef BackupRestore = Future<void> Function(BackupSummary backup);

final Provider<BackupRestore> backupRestoreProvider = Provider<BackupRestore>((
  ref,
) {
  final GleanApiClient api = ref.watch(apiClientProvider);
  final Future<File> Function() liveFile = ref.watch(databaseFileProvider);
  final Future<Directory> Function() tempDir = ref.watch(
    diagnosticsTempDirProvider,
  );
  return (BackupSummary backup) async {
    final Directory workDir = await (await tempDir()).createTemp(
      'glean_restore_',
    );
    try {
      final File downloaded = File('${workDir.path}/backup.sqlite')
        ..writeAsBytesSync(await api.downloadBackup(backup.downloadUrl));
      await restoreDatabase(
        backup: downloaded,
        live: ref.read(gleanDatabaseProvider),
        liveFile: await liveFile(),
      );
      // The old connection is closed; providers rebuild against the restored file.
      ref.invalidate(gleanDatabaseProvider);
    } on RestoreInterruptedException {
      // The previous file is still in place but the connection to it is closed: reopen it.
      ref.invalidate(gleanDatabaseProvider);
      rethrow;
    } finally {
      await workDir.delete(recursive: true);
    }
  };
});
