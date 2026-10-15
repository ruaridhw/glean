import 'dart:async';

import 'package:flutter/foundation.dart';

import 'describe_error.dart';
import 'glean_logger.dart';

const int _maxStackLines = 12;

/// What the framework's own reporter gets in place of an error: only [description], which has already been
/// through [describeError], so a response body or token inside the original exception never reaches the console.
class RedactedError implements Exception {
  const RedactedError(this.description);

  final String description;

  @override
  String toString() => description;
}

/// Routes uncaught Flutter framework errors and uncaught async errors into [logger]. The framework's own
/// reporting (console, red screen in debug) still runs first, but on a redacted copy of the error.
void installErrorHooks(GleanLogger logger) {
  // Errors raised by the logging path itself are not logged again, so a failing sink can't loop. Anything else
  // is logged, even while a write is pending.
  void report(String line) {
    if (isInsideLogSink) {
      debugPrint('glean: error inside the log sink was not logged again');
      return;
    }
    unawaited(logger.error(line));
  }

  final FlutterExceptionHandler? previous = FlutterError.onError;
  FlutterError.onError = (FlutterErrorDetails details) {
    final FlutterErrorDetails redacted = FlutterErrorDetails(
      exception: RedactedError(describeError(details.exception)),
      stack: details.stack,
      library: details.library,
      context: details.context,
      silent: details.silent,
    );
    if (previous != null) {
      previous(redacted);
    } else {
      FlutterError.presentError(redacted);
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
