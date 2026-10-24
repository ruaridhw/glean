import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:drift/drift.dart' show driftRuntimeOptions;
import 'package:drift/native.dart';

import '../data/database.dart';
import 'restore_failures.dart';

const int _sqliteHeaderBytes = 100;
const int _userVersionOffset = 60;
final Uint8List _sqliteMagic = Uint8List.fromList(
  'SQLite format 3\x00'.codeUnits,
);

/// The schema version drift records in a database file's `user_version` header field.
int _schemaVersionOf(File backup) {
  final RandomAccessFile file = backup.openSync();
  try {
    final Uint8List header = file.readSync(_sqliteHeaderBytes);
    if (header.length < _sqliteHeaderBytes) {
      throw const BackupInvalidException('the file is too short');
    }
    for (var i = 0; i < _sqliteMagic.length; i++) {
      if (header[i] != _sqliteMagic[i]) {
        throw const BackupInvalidException('the file is not a SQLite database');
      }
    }
    return ByteData.sublistView(header).getUint32(_userVersionOffset);
  } finally {
    file.closeSync();
  }
}

/// Replaces [live]'s database file, [liveFile], with the backup at [backup].
///
/// Everything that can fail happens on a copy beside the live file: the schema version is checked, then the copy
/// is opened, which runs the app's normal migrations so an older backup arrives at the current schema, and its
/// integrity is verified. Only then is [live] closed and the copy renamed over it in one step, so a refused,
/// damaged or interrupted restore leaves the previous database exactly as it was. The previous database is kept
/// beside it as `<live>.pre-restore`. [live] is closed on success; the caller opens the restored file.
///
/// Throws [BackupTooNewException] or [BackupInvalidException] without touching [live].
Future<void> restoreDatabase({
  required File backup,
  required GleanDatabase live,
  required File liveFile,
}) async {
  final int backupVersion = _schemaVersionOf(backup);
  if (backupVersion < 1) {
    // Version 0 means "never created by Glean"; opening it would build a fresh empty database in its place.
    throw const BackupInvalidException('it has no Glean schema version');
  }
  if (backupVersion > live.schemaVersion) {
    throw BackupTooNewException(
      backupVersion: backupVersion,
      appVersion: live.schemaVersion,
    );
  }

  _deleteAbandonedStaging(liveFile);
  // A path no earlier attempt has used, so SQLite sidecars an interrupted attempt left behind can never be
  // associated with this backup.
  final File staged = File(
    '${liveFile.path}$_stagingMarker${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(1 << 32)}',
  );
  try {
    if (_sidecarsOf(staged).any((File f) => f.existsSync())) {
      throw StateError('Staging file ${staged.path} has leftover sidecars');
    }
    backup.copySync(staged.path);
    await _migrateAndVerify(staged);

    await live.customStatement('PRAGMA wal_checkpoint(TRUNCATE)');
    // Only the connection is closed, not the database object: screens may hold stream subscriptions that
    // Riverpod has paused, and drift's full close waits for those to finish, which would never happen. The
    // caller rebuilds the database, which disposes the subscribers and closes it properly.
    await live.executor.close();
    try {
      // A leftover write-ahead log from the old file must never be replayed onto the restored one.
      for (final String suffix in <String>['-wal', '-shm', '-journal']) {
        final File sidecar = File('${liveFile.path}$suffix');
        if (sidecar.existsSync()) sidecar.deleteSync();
      }
      liveFile.copySync('${liveFile.path}.pre-restore');
      staged.renameSync(liveFile.path);
    } on Object catch (error) {
      throw RestoreInterruptedException(error);
    }
  } on Object {
    _deleteStaging(staged);
    rethrow;
  }
}

const String _stagingMarker = '.restore-staging-';

List<File> _sidecarsOf(File db) => <File>[
  for (final String suffix in <String>['-wal', '-shm', '-journal'])
    File('${db.path}$suffix'),
];

void _deleteStaging(File staged) {
  for (final File f in <File>[staged, ..._sidecarsOf(staged)]) {
    if (f.existsSync()) f.deleteSync();
  }
}

/// Removes staging files (and their SQLite sidecars) an earlier, interrupted restore left beside [liveFile].
/// Only names carrying the staging marker are touched, never the live database or its own sidecars.
void _deleteAbandonedStaging(File liveFile) {
  final String prefix =
      '${liveFile.uri.pathSegments.last}${_stagingMarker.substring(0, _stagingMarker.length - 1)}';
  for (final FileSystemEntity e in liveFile.parent.listSync()) {
    if (e is File && e.uri.pathSegments.last.startsWith(prefix)) e.deleteSync();
  }
}

Future<void> _migrateAndVerify(File staged) async {
  // The live database is open at the same time, on a different file, so drift's same-file warning is moot.
  final bool warned = driftRuntimeOptions.dontWarnAboutMultipleDatabases;
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
  final GleanDatabase candidate = GleanDatabase(NativeDatabase(staged));
  try {
    final Object? verdict =
        (await candidate.customSelect('PRAGMA integrity_check').getSingle())
            .data
            .values
            .single;
    if (verdict != 'ok') throw BackupInvalidException('$verdict');
    final String? mismatch = await _schemaMismatch(candidate);
    if (mismatch != null) throw BackupInvalidException(mismatch);
  } on BackupInvalidException {
    rethrow;
  } on Object catch (error) {
    throw BackupInvalidException('it could not be opened: $error');
  } finally {
    await candidate.close();
    driftRuntimeOptions.dontWarnAboutMultipleDatabases = warned;
  }
}

/// Every table and column of the schema this build creates, read from a fresh database.
Future<Map<String, Set<String>>> _columnsByTable(GleanDatabase db) async {
  final tables = await db
      .customSelect(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%'",
      )
      .get();
  return <String, Set<String>>{
    for (final table in tables)
      table.read<String>('name'): {
        for (final column
            in await db
                .customSelect(
                  'PRAGMA table_info("${table.read<String>('name')}")',
                )
                .get())
          column.read<String>('name'),
      },
  };
}

/// Why the migrated [candidate] is not a usable Glean database, or `null` when every table and column this
/// build expects is present. A file can be valid SQLite, even carry the right version number, and still be
/// someone else's database.
Future<String?> _schemaMismatch(GleanDatabase candidate) async {
  final GleanDatabase reference = GleanDatabase(NativeDatabase.memory());
  try {
    final Map<String, Set<String>> expected = await _columnsByTable(reference);
    final Map<String, Set<String>> actual = await _columnsByTable(candidate);
    for (final MapEntry<String, Set<String>> table in expected.entries) {
      final Set<String>? columns = actual[table.key];
      if (columns == null) return 'table ${table.key} is missing';
      final Set<String> missing = table.value.difference(columns);
      if (missing.isNotEmpty) {
        return 'table ${table.key} lacks ${missing.join(', ')}';
      }
    }
    return null;
  } finally {
    await reference.close();
  }
}
