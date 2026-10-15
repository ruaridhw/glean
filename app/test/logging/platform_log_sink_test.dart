import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/logging/logging.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late List<MethodCall> calls;

  setUp(() {
    calls = <MethodCall>[];
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('glean/log'), (
          call,
        ) async {
          calls.add(call);
          return null;
        });
  });

  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('glean/log'), null);
  });

  test('on Android a line goes to the native log channel', () async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;

    await const MethodChannelLogSink().write(
      level: 'error',
      tag: 'glean',
      message: 'x',
    );

    expect(calls, hasLength(1));
  });

  test(
    'on iOS, which has no native log handler, the channel is not called',
    () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.iOS;

      await const MethodChannelLogSink().write(
        level: 'error',
        tag: 'glean',
        message: 'x',
      );

      expect(calls, isEmpty);
    },
  );

  test('a missing native handler does not throw', () async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('glean/log'), null);

    await const MethodChannelLogSink().write(
      level: 'error',
      tag: 'glean',
      message: 'x',
    );
  });
}
