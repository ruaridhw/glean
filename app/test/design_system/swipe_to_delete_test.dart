import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  group('SwipeToDeleteRow', () {
    testWidgets(
      'a single swipe-to-delete fires exactly one haptic (AC-HAP-03)',
      (WidgetTester tester) async {
        final RecordingHaptics haptics = RecordingHaptics();
        bool deleted = false;

        await tester.pumpWidget(
          ProviderScope(
            // Note: the list's element type (`Override`, from
            // package:riverpod) isn't part of that package's resolvable
            // public API surface in this version — spelling it explicitly
            // fails to resolve even though `overrideWithValue` returns it,
            // so the literal is left untyped and inferred contextually.
            overrides: [hapticsProvider.overrideWithValue(haptics)],
            child: MaterialApp(
              theme: gleanLightTheme,
              home: Scaffold(
                body: SwipeToDeleteRow(
                  dismissibleKey: const ValueKey<String>('row-1'),
                  onDelete: () => deleted = true,
                  child: const ListTile(title: Text('Milk')),
                ),
              ),
            ),
          ),
        );

        await tester.drag(find.text('Milk'), const Offset(-600, 0));
        await tester.pumpAndSettle();

        expect(deleted, isTrue);
        expect(haptics.calls, <HapticWeight>[HapticWeight.medium]);
      },
    );

    testWidgets(
      'a swipe that does not cross the dismiss threshold fires no haptic',
      (WidgetTester tester) async {
        final RecordingHaptics haptics = RecordingHaptics();
        bool deleted = false;

        await tester.pumpWidget(
          ProviderScope(
            overrides: [hapticsProvider.overrideWithValue(haptics)],
            child: MaterialApp(
              theme: gleanLightTheme,
              home: Scaffold(
                body: SwipeToDeleteRow(
                  dismissibleKey: const ValueKey<String>('row-2'),
                  onDelete: () => deleted = true,
                  child: const ListTile(title: Text('Eggs')),
                ),
              ),
            ),
          ),
        );

        // A short drag well under Dismissible's ~40% default threshold,
        // released rather than flung.
        await tester.drag(find.text('Eggs'), const Offset(-20, 0));
        await tester.pumpAndSettle();

        expect(deleted, isFalse);
        expect(haptics.calls, isEmpty);
      },
    );
  });
}
