import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import 'redaction.dart';
import 'rotating_log_file.dart';

/// Where log lines go besides the file: the platform log (Android logcat).
abstract interface class PlatformLogSink {
  Future<void> write({
    required String level,
    required String tag,
    required String message,
  });
}

/// Sends lines to the native `glean/log` channel (see `MainActivity.kt`), which exists on Android only. Other
/// platforms keep the file sink alone rather than carrying a native handler nobody reads; a missing handler is
/// swallowed, so this can never throw.
class MethodChannelLogSink implements PlatformLogSink {
  const MethodChannelLogSink();

  static const MethodChannel _channel = MethodChannel('glean/log');

  @override
  Future<void> write({
    required String level,
    required String tag,
    required String message,
  }) async {
    if (defaultTargetPlatform != TargetPlatform.android) return;
    try {
      await _channel.invokeMethod<void>('log', <String, Object?>{
        'tag': tag,
        'level': level,
        'message': message,
      });
    } on MissingPluginException {
      // No native handler registered: the file sink still has the line.
    }
  }
}

/// The platform log tag every Glean line carries, so `adb logcat -s glean` shows exactly the app's own trail.
const String gleanLogTag = 'glean';

class GleanLogger {
  GleanLogger({
    required this.file,
    required this.platform,
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  final RotatingLogFile file;
  final PlatformLogSink platform;
  final DateTime Function() _clock;

  Future<void> error(String message) => _write('error', message);

  /// Logging never throws into callers: each sink is guarded on its own, and a failing sink falls back to
  /// [debugPrint] so a full disk or a missing native handler can't replace the error being logged.
  ///
  /// The whole write runs in a zone marked by [isInsideLogSink], and anything uncaught from it stops there, so
  /// an error raised by the logging path itself can't be reported back into the logger.
  Future<void> _write(String level, String raw) {
    final Completer<void> done = Completer<void>();
    runZonedGuarded(
      () => _writeToSinks(level, raw).whenComplete(done.complete),
      (Object error, StackTrace _) {
        debugPrint('glean: logging failed (${error.runtimeType})');
        if (!done.isCompleted) done.complete();
      },
      zoneValues: <Object, Object?>{_sinkZoneKey: true},
    );
    return done.future;
  }

  Future<void> _writeToSinks(String level, String raw) async {
    final String message = redactSecrets(raw);
    try {
      file.append('${_clock().toUtc().toIso8601String()} $level $message');
    } catch (error) {
      debugPrint(
        'glean: log file write failed (${error.runtimeType}): $message',
      );
    }
    try {
      await platform.write(level: level, tag: gleanLogTag, message: message);
    } catch (error) {
      debugPrint('glean: platform log failed (${error.runtimeType}): $message');
    }
  }
}

const Object _sinkZoneKey = #gleanLogSink;

/// True only inside a logger write. An error reported from here came from the logging path itself, so the
/// global hooks must not log it again; every other error is logged, even while a write is pending.
bool get isInsideLogSink => Zone.current[_sinkZoneKey] == true;
