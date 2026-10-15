import 'dart:async';
import 'dart:io';
import 'dart:ui';

import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/api_client.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/logging/logging.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _ThrowingPlatformLog implements PlatformLogSink {
  int writes = 0;

  @override
  Future<void> write({
    required String level,
    required String tag,
    required String message,
  }) async {
    writes++;
    throw const FileSystemException('platform log unavailable');
  }
}

class _RecordingPlatformLog implements PlatformLogSink {
  final List<String> messages = <String>[];

  @override
  Future<void> write({
    required String level,
    required String tag,
    required String message,
  }) async => messages.add(message);
}

void main() {
  late Directory dir;
  late RotatingLogFile unwritableFile;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('glean_never_throws_test');
    // A regular file where the log directory should be: creating the log file under it always fails.
    File('${dir.path}/blocker').writeAsStringSync('not a directory');
    unwritableFile = RotatingLogFile(
      File('${dir.path}/blocker/logs/glean.log'),
    );
  });

  tearDown(() => dir.deleteSync(recursive: true));

  test(
    'a log file that cannot be written does not throw, and the platform log still gets the line',
    () async {
      final _RecordingPlatformLog platform = _RecordingPlatformLog();
      final GleanLogger logger = GleanLogger(
        file: unwritableFile,
        platform: platform,
      );

      await logger.error('something happened');

      expect(platform.messages, <String>['something happened']);
    },
  );

  test('both sinks failing does not throw', () async {
    final GleanLogger logger = GleanLogger(
      file: unwritableFile,
      platform: _ThrowingPlatformLog(),
    );

    await logger.error('something happened');
  });

  test('an API error keeps its type when the log cannot be written', () async {
    final GleanApiClient client = GleanApiClient(
      baseUrl: 'http://localhost:8000',
      httpClient: MockClient((_) async => http.Response('{}', 500)),
      logger: GleanLogger(
        file: unwritableFile,
        platform: _ThrowingPlatformLog(),
      ),
    );

    await expectLater(
      client.getRecipe('r1'),
      throwsA(isA<ApiServerException>()),
    );
  });

  group('global hooks', () {
    late FlutterExceptionHandler? originalFlutterHandler;
    late ErrorCallback? originalPlatformHandler;

    setUp(() {
      originalFlutterHandler = FlutterError.onError;
      originalPlatformHandler = PlatformDispatcher.instance.onError;
    });

    tearDown(() {
      FlutterError.onError = originalFlutterHandler;
      PlatformDispatcher.instance.onError = originalPlatformHandler;
    });

    test('a failing log sink does not break error reporting', () {
      installErrorHooks(
        GleanLogger(file: unwritableFile, platform: _ThrowingPlatformLog()),
      );

      FlutterError.onError!(FlutterErrorDetails(exception: StateError('boom')));
      final bool handled = PlatformDispatcher.instance.onError!(
        StateError('async boom'),
        StackTrace.current,
      );

      expect(handled, isTrue);
    });

    test('an error raised while logging an error is not logged again', () async {
      final List<String> written = <String>[];
      late final GleanLogger logger;
      logger = GleanLogger(
        file: unwritableFile,
        platform: _ReentrantPlatformLog((String message) {
          written.add(message);
          // The sink itself reports an uncaught error, as a failing native handler might.
          PlatformDispatcher.instance.onError!(
            StateError('sink failed'),
            StackTrace.current,
          );
        }),
      );
      installErrorHooks(logger);

      PlatformDispatcher.instance.onError!(
        StateError('first'),
        StackTrace.current,
      );
      await Future<void>.delayed(Duration.zero);

      expect(written, hasLength(1));
    });

    test(
      'an unrelated error while a platform write is pending is still logged',
      () async {
        final Completer<void> release = Completer<void>();
        final RotatingLogFile file = RotatingLogFile(
          File('${dir.path}/glean.log'),
        );
        installErrorHooks(
          GleanLogger(file: file, platform: _SlowPlatformLog(release.future)),
        );

        PlatformDispatcher.instance.onError!(
          StateError('first failure'),
          StackTrace.current,
        );
        PlatformDispatcher.instance.onError!(
          StateError('unrelated failure'),
          StackTrace.current,
        );
        release.complete();
        await Future<void>.delayed(Duration.zero);

        expect(file.readAll(), contains('first failure'));
        expect(file.readAll(), contains('unrelated failure'));
      },
    );

    test(
      'Flutter errors during a pending platform write are logged too',
      () async {
        final Completer<void> release = Completer<void>();
        final RotatingLogFile file = RotatingLogFile(
          File('${dir.path}/glean.log'),
        );
        installErrorHooks(
          GleanLogger(file: file, platform: _SlowPlatformLog(release.future)),
        );

        PlatformDispatcher.instance.onError!(
          StateError('async failure'),
          StackTrace.current,
        );
        FlutterError.onError!(
          FlutterErrorDetails(exception: StateError('framework failure')),
        );
        release.complete();
        await Future<void>.delayed(Duration.zero);

        expect(file.readAll(), contains('framework failure'));
      },
    );
  });
}

class _ReentrantPlatformLog implements PlatformLogSink {
  _ReentrantPlatformLog(this.onWrite);

  final void Function(String message) onWrite;

  @override
  Future<void> write({
    required String level,
    required String tag,
    required String message,
  }) async => onWrite(message);
}

class _SlowPlatformLog implements PlatformLogSink {
  _SlowPlatformLog(this.until);

  final Future<void> until;

  @override
  Future<void> write({
    required String level,
    required String tag,
    required String message,
  }) => until;
}
