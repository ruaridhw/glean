/// Replacing the live database with a backup. Native builds swap the app's SQLite file; the web build has no such
/// file — its database lives in the browser — so there it is a stub that refuses. `database_restore_io.dart` is
/// the implementation; this file is only the seam, chosen at compile time so no web build ever reaches
/// `package:drift/native.dart` (and so `dart:ffi`, which the web compiler rejects).
library;

export 'restore_failures.dart';

export 'database_restore_io.dart'
    if (dart.library.js_interop) 'database_restore_web.dart';
