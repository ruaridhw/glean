import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  group('SkeletonBox', () {
    testWidgets(
      'pulses opacity over time without a caller-managed controller',
      (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            theme: gleanLightTheme,
            home: const Scaffold(body: SkeletonBox(width: 120, height: 16)),
          ),
        );

        double opacityAt(Duration elapsed) {
          return tester.widget<Opacity>(find.byType(Opacity)).opacity;
        }

        final double start = opacityAt(Duration.zero);
        await tester.pump(const Duration(milliseconds: 500));
        final double mid = opacityAt(const Duration(milliseconds: 500));
        await tester.pump(const Duration(milliseconds: 600));
        final double afterFirstLeg = opacityAt(
          const Duration(milliseconds: 1100),
        );

        // It must actually be animating (not static), and must keep going past
        // the first leg's completion (proving the loop re-triggers itself).
        expect(mid, isNot(equals(start)));
        expect(afterFirstLeg, isNot(equals(mid)));
      },
    );
  });
}
