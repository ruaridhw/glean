// flutter_native_splash's `fullscreen: true` writes `UIStatusBarHidden` into
// ios/Runner/Info.plist, which keeps the iOS status bar hidden for the whole
// app, not just the splash. Startup must ask the platform to show it again.
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/bootstrap.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late List<MethodCall> calls;

  setUp(() {
    calls = <MethodCall>[];
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (
          MethodCall call,
        ) async {
          calls.add(call);
          return null;
        });
  });

  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, null);
  });

  test('shows the iOS status bar again after the fullscreen splash', () async {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;

    await showStatusBarAfterSplash();

    final MethodCall call = calls.singleWhere(
      (MethodCall c) => c.method == 'SystemChrome.setEnabledSystemUIOverlays',
    );
    expect(call.arguments, contains('SystemUiOverlay.top'));
  });

  test('leaves Android system UI alone, where the splash hid it only on the '
      'launch theme', () async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;

    await showStatusBarAfterSplash();

    expect(calls, isEmpty);
  });
}
