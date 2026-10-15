import 'package:flutter/foundation.dart';

import 'describe_error.dart';
import 'glean_logger.dart';

const int _maxStackLines = 12;

/// Routes uncaught Flutter framework errors and uncaught async errors into [logger]. The framework's own
/// reporting (console, red screen in debug) still runs first.
void installErrorHooks(GleanLogger logger) {
  final FlutterExceptionHandler? previous = FlutterError.onError;
  FlutterError.onError = (FlutterErrorDetails details) {
    if (previous != null) {
      previous(details);
    } else {
      FlutterError.presentError(details);
    }
    final String where = details.library == null ? '' : ' (${details.library})';
    logger.error(
      'uncaught Flutter error$where: ${_describe(details.exception, details.stack)}',
    );
  };
  PlatformDispatcher.instance.onError = (Object error, StackTrace stack) {
    logger.error('uncaught async error: ${_describe(error, stack)}');
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
