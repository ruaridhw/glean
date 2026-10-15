import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/router/app_routes.dart';
import '../support/harness.dart';

void main() {
  gleanWidgetTest(
    'connectivity loss shows the Expo message across tabs while local data remains usable, and reconnect clears it',
    (tester) async {
      final messenger = tester.binding.defaultBinaryMessenger;
      messenger.setMockMethodCallHandler(
        const MethodChannel('dev.fluttercommunity.plus/connectivity'),
        (_) async => ['wifi'],
      );
      MockStreamHandlerEventSink? events;
      messenger.setMockStreamHandler(
        const EventChannel('dev.fluttercommunity.plus/connectivity_status'),
        MockStreamHandler.inline(
          onListen: (_, sink) {
            events = sink;
          },
        ),
      );
      final h = AppTestHarness();
      addTearDown(h.dispose);
      await h.container
          .read(pantryRepositoryProvider)
          .addItem(
            userId: h.userId,
            name: 'Chicken breast',
            quantity: 200,
            unit: 'g',
            category: 'poultry',
          );
      await h.pumpAt(tester, AppRoutes.pantry.path);
      await tester.pumpAndSettle();
      const message = "You're offline. Some features need internet.";
      expect(find.text(message), findsNothing);
      events?.success(['none']);
      await tester.pumpAndSettle();
      expect(find.text(message), findsOneWidget);
      expect(find.text('chicken breast'), findsOneWidget);
      await tester.tap(find.text('Settings'));
      await tester.pumpAndSettle();
      expect(find.text(message), findsOneWidget);
      await tester.tap(find.text('Pantry'));
      await tester.pumpAndSettle();
      expect(find.text('chicken breast'), findsOneWidget);
      events?.success(['wifi']);
      await tester.pumpAndSettle();
      expect(find.text(message), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
}
