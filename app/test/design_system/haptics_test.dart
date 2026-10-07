import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'the default production haptics provider emits the three platform effects',
    () async {
      final messages = <MethodCall>[];
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, (call) async {
            messages.add(call);
            return null;
          });
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final haptics = container.read(hapticsProvider);
      haptics.selectionClick();
      haptics.lightImpact();
      haptics.mediumImpact();
      await Future<void>.delayed(Duration.zero);
      expect(
        messages.map((call) => call.method),
        everyElement('HapticFeedback.vibrate'),
      );
      expect(messages.map((call) => call.arguments), [
        'HapticFeedbackType.selectionClick',
        'HapticFeedbackType.lightImpact',
        'HapticFeedbackType.mediumImpact',
      ]);
    },
  );
}
