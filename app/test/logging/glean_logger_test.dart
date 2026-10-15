import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/logging/logging.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory dir;
  late RotatingLogFile file;
  late List<MethodCall> platformCalls;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('glean_log_test');
    file = RotatingLogFile(File('${dir.path}/glean.log'), maxBytes: 400);
    platformCalls = <MethodCall>[];
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('glean/log'), (
          call,
        ) async {
          platformCalls.add(call);
          return null;
        });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('glean/log'), null);
    dir.deleteSync(recursive: true);
  });

  GleanLogger newLogger() => GleanLogger(
    file: file,
    platform: const MethodChannelLogSink(),
    clock: () => DateTime.utc(2026, 10, 15, 12, 30, 45),
  );

  test(
    'an error is written to the log file and the platform log under the glean tag',
    () async {
      await newLogger().error('GET /recipes/search failed: 500');

      expect(file.readAll(), contains('2026-10-15T12:30:45.000Z'));
      expect(file.readAll(), contains('GET /recipes/search failed: 500'));
      expect(platformCalls, hasLength(1));
      expect(platformCalls.single.method, 'log');
      expect(platformCalls.single.arguments, <String, Object?>{
        'tag': 'glean',
        'level': 'error',
        'message': 'GET /recipes/search failed: 500',
      });
    },
  );

  test(
    'auth tokens in a message never reach the file or the platform log',
    () async {
      const jwt =
          'eyJhbGciOiJSUzI1NiIsImtpZCI6ImsxIn0.eyJzdWIiOiJ1c2VyLTEifQ.c2lnbmF0dXJl';

      await newLogger().error(
        'refresh failed Authorization: Bearer opaque-secret-123 and id_token=$jwt',
      );

      final String logged = file.readAll();
      expect(logged, isNot(contains('opaque-secret-123')));
      expect(logged, isNot(contains(jwt)));
      expect(logged, contains('refresh failed'));
      final String sent = platformCalls.single.arguments['message'] as String;
      expect(sent, isNot(contains('opaque-secret-123')));
      expect(sent, isNot(contains(jwt)));
    },
  );

  test('the log stays bounded and keeps the newest lines in order', () async {
    final GleanLogger logger = newLogger();
    for (var i = 0; i < 40; i++) {
      await logger.error('line-${i.toString().padLeft(2, '0')} ${'x' * 30}');
    }

    final String retained = file.readAll();
    final List<String> lines = retained.trim().split('\n');
    expect(retained.length, lessThanOrEqualTo(2 * 400 + 100));
    expect(lines.last, contains('line-39'));
    expect(lines.first, isNot(contains('line-00')));
    final List<int> numbers = lines
        .map((l) => int.parse(RegExp(r'line-(\d+)').firstMatch(l)!.group(1)!))
        .toList();
    expect(
      numbers,
      orderedEquals(<int>[for (var n = numbers.first; n <= 39; n++) n]),
    );
  });
}
