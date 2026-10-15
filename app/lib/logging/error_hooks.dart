import 'dart:async';

import 'package:flutter/foundation.dart';

import 'describe_error.dart';
import 'glean_logger.dart';

const int _maxStackLines = 12;

/// Routes uncaught Flutter framework errors and uncaught async errors into [logger]. The framework's own
/// reporting (console, red screen in debug) still runs first.
void installErrorHooks(GleanLogger logger) {
  // An error raised while an error is being logged is not logged again, so a failing sink can't loop.
  var logging = false;
  void report(String line) {
    if (logging) return;
    logging = true;
    unawaited(logger.error(line).whenComplete(() => logging = false));
  }

  final FlutterExceptionHandler? previous = FlutterError.onError;
  FlutterError.onError = (FlutterErrorDetails details) {
    if (previous != null) {
      previous(details);
    } else {
      FlutterError.presentError(details);
    }
    final String where = details.library == null ? '' : ' (${details.library})';
    report(
      'uncaught Flutter error$where: ${_describe(details.exception, details.stack)}',
    );
  };
  PlatformDispatcher.instance.onError = (Object error, StackTrace stack) {
    report('uncaught async error: ${_describe(error, stack)}');
    return true;
  };
}

String _describe(Object error, StackTrace? stack) {
  final String top = (stack?.toString() ?? '')
      .split('\n')
      .take(_maxStackLines)
      .join('\n');
  return '${describeError(error)}\n$top'.trimRight();
}
