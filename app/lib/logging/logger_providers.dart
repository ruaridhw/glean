import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import 'glean_logger.dart';
import 'rotating_log_file.dart';

/// The app's logger, or `null` where none was set up (tests, previews). The entrypoints override it with the
/// logger they built before `runApp`; consumers log through `?.` so a missing logger is never an error.
final Provider<GleanLogger?> gleanLoggerProvider = Provider<GleanLogger?>(
  (ref) => null,
);

/// Builds the logger writing to `logs/glean.log` in the app's support storage (private to the app, kept across
/// updates, and readable over `adb` on an owner build).
Future<GleanLogger> createGleanLogger() async {
  final Directory support = await getApplicationSupportDirectory();
  return GleanLogger(
    file: RotatingLogFile(File('${support.path}/logs/glean.log')),
    platform: const MethodChannelLogSink(),
  );
}
