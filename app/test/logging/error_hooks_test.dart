import 'dart:io';
import 'dart:ui';

import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/logging/logging.dart';

class _NoPlatformLog implements PlatformLogSink {
  @override
  Future<void> write({
    required String level,
    required String tag,
    required String message,
  }) async {}
}

void main() {
  late Directory dir;
  late RotatingLogFile file;
  late FlutterExceptionHandler? originalFlutterHandler;
  late ErrorCallback? originalPlatformHandler;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('glean_hooks_test');
    file = RotatingLogFile(File('${dir.path}/glean.log'));
    originalFlutterHandler = FlutterError.onError;
    originalPlatformHandler = PlatformDispatcher.instance.onError;
    installErrorHooks(GleanLogger(file: file, platform: _NoPlatformLog()));
  });

  tearDown(() {
    FlutterError.onError = originalFlutterHandler;
    PlatformDispatcher.instance.onError = originalPlatformHandler;
    dir.deleteSync(recursive: true);
  });

  test('an uncaught Flutter framework error is logged', () {
    FlutterError.onError!(
      FlutterErrorDetails(
        exception: StateError('widget exploded'),
        stack: StackTrace.current,
        library: 'widgets library',
      ),
    );

    expect(file.readAll(), contains('widget exploded'));
    expect(file.readAll(), contains('widgets library'));
  });

  test('an uncaught async error is logged and reported as handled', () {
    final bool handled = PlatformDispatcher.instance.onError!(
      StateError('future exploded'),
      StackTrace.current,
    );

    expect(handled, isTrue);
    expect(file.readAll(), contains('future exploded'));
  });

  group('the framework reporter that runs before logging', () {
    const String body =
        '<html>refresh_token=opaque-secret-123 private-receipt-note</html>';

    late List<FlutterErrorDetails> seen;

    setUp(() {
      seen = <FlutterErrorDetails>[];
      FlutterError.onError = seen.add; // stands in for the console reporter
      installErrorHooks(GleanLogger(file: file, platform: _NoPlatformLog()));
    });

    void expectClean(FlutterErrorDetails details, {bool body = true}) {
      final String everything =
          '${details.exception} ${details.toDiagnosticsNode().toStringDeep()} ${details.summary}';
      expect(everything, isNot(contains('opaque-secret-123')));
      // An ordinary exception's free text can't be told from a body, so only quoted-source errors are held to it.
      if (body) expect(everything, isNot(contains('private-receipt-note')));
    }

    test('never sees a response body or token quoted by a FormatException', () {
      FlutterError.onError!(
        const FlutterErrorDetails(exception: FormatException('bad', body, 0)),
      );

      expect(seen, hasLength(1));
      expectClean(seen.single);
    });

    test('never sees a token inside an ordinary exception message', () {
      FlutterError.onError!(
        FlutterErrorDetails(exception: StateError('failed: $body')),
      );

      expectClean(seen.single, body: false);
      expect(seen.single.exception.toString(), contains('StateError'));
    });

    test(
      'still gets the stack and library so the console report stays useful',
      () {
        final StackTrace stack = StackTrace.current;
        FlutterError.onError!(
          FlutterErrorDetails(
            exception: StateError('x'),
            stack: stack,
            library: 'widgets library',
          ),
        );

        expect(seen.single.stack, stack);
        expect(seen.single.library, 'widgets library');
      },
    );
  });
}
