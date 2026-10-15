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

/// Sends lines to the native `glean/log` channel (see `MainActivity.kt`).
class MethodChannelLogSink implements PlatformLogSink {
  const MethodChannelLogSink();

  static const MethodChannel _channel = MethodChannel('glean/log');

  @override
  Future<void> write({
    required String level,
    required String tag,
    required String message,
  }) {
    return _channel.invokeMethod<void>('log', <String, Object?>{
      'tag': tag,
      'level': level,
      'message': message,
    });
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

  Future<void> _write(String level, String raw) async {
    final String message = redactSecrets(raw);
    file.append('${_clock().toUtc().toIso8601String()} $level $message');
    try {
      await platform.write(level: level, tag: gleanLogTag, message: message);
    } catch (_) {
      // The file already has the line; a platform-log failure must never become an error of its own.
    }
  }
}
