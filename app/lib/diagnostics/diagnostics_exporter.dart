import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../api/providers/api_providers.dart';
import '../data/providers/database_providers.dart';
import '../logging/logger_providers.dart';
import 'database_snapshot.dart';

/// Uploads a database snapshot and the app log; resolves to the S3 prefix the export landed under.
typedef DiagnosticsExport = Future<String> Function();

/// Where the export's temporary snapshot is written: `path_provider`'s temp directory in the app.
final Provider<Future<Directory> Function()> diagnosticsTempDirProvider =
    Provider<Future<Directory> Function()>((ref) => getTemporaryDirectory);

final Provider<DiagnosticsExport>
diagnosticsExportProvider = Provider<DiagnosticsExport>((ref) {
  final db = ref.watch(gleanDatabaseProvider);
  final api = ref.watch(apiClientProvider);
  final logger = ref.watch(gleanLoggerProvider);
  final tempDir = ref.watch(diagnosticsTempDirProvider);
  return () async {
    final Directory workDir = await (await tempDir()).createTemp(
      'glean_export_',
    );
    try {
      final File snapshot = await snapshotDatabase(db, workDir);
      final response = await api.exportDiagnostics(
        database: await snapshot.readAsBytes(),
        log: utf8.encode(logger?.file.readAll() ?? ''),
      );
      return response.prefix;
    } finally {
      // The snapshot is a full copy of the user's data; never leave it behind.
      await workDir.delete(recursive: true);
    }
  };
});
