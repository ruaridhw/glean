// AC-PLAN-12: the progress ring must animate a change rather than
// teleporting straight to the new value — RN's SVG ring was fully static,
// jumping from 0/5 to 5/5 the instant a generation completed. Pumps the
// widget in isolation (no DB/router) so the ring's own `TweenAnimationBuilder`
// timing is the only thing under test, not stream-propagation latency.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/plan/widgets/plan_progress_card.dart';

Widget _wrap(Widget child) {
  return MaterialApp(
    theme: gleanLightTheme,
    home: Scaffold(body: Center(child: child)),
  );
}

CustomPaint _ringPaint(WidgetTester tester) {
  return tester.widget<CustomPaint>(
    find.byKey(const ValueKey<String>('plan-progress-ring-paint')),
  );
}

double _ringFraction(WidgetTester tester) {
  final painter = _ringPaint(tester).painter! as PlanProgressRingPainter;
  return painter.fraction;
}

void main() {
  testWidgets('settles at 0 fraction when nothing is planned yet', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      _wrap(const PlanProgressCard(planned: 0, target: 2, remaining: 2)),
    );
    await tester.pumpAndSettle();

    expect(_ringFraction(tester), 0.0);
    expect(find.text('0/2'), findsOneWidget);
  });

  testWidgets(
    'sweeps through an intermediate value on the way to the new fraction, '
    'rather than snapping straight to it',
    (WidgetTester tester) async {
      await tester.pumpWidget(
        _wrap(const PlanProgressCard(planned: 0, target: 2, remaining: 2)),
      );
      await tester.pumpAndSettle();
      expect(_ringFraction(tester), 0.0);

      // Same widget, new props — the direct analogue of a generation
      // completing and `entries.length` jumping from 0 to 1.
      await tester.pumpWidget(
        _wrap(const PlanProgressCard(planned: 1, target: 2, remaining: 1)),
      );
      // Partway through the ring's 600ms sweep.
      await tester.pump(const Duration(milliseconds: 150));

      final double midFraction = _ringFraction(tester);
      expect(
        midFraction,
        allOf(greaterThan(0.0), lessThan(0.5)),
        reason:
            'a teleporting ring would already read 0.5 here; a genuinely '
            'static one would still read 0.0',
      );

      await tester.pumpAndSettle();
      expect(_ringFraction(tester), closeTo(0.5, 0.0001));
      expect(find.text('1/2'), findsOneWidget);
    },
  );
}
