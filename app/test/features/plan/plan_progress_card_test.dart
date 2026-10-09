import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/plan/widgets/plan_progress_card.dart';
import '../../support/visual.dart';

void main() {
  setUpAll(loadBrandFonts);
  testWidgets('an empty plan renders an empty ring and its readable count', (
    tester,
  ) async {
    await tester.pumpWidget(
      visual(const PlanProgressCard(planned: 0, target: 2, remaining: 2)),
    );
    await tester.pumpAndSettle();
    expect(find.text('0/2'), findsOneWidget);
    await golden(tester, 'progress-empty');
  });
  testWidgets(
    'the rendered ring sweeps through an intermediate frame before settling',
    (tester) async {
      await tester.pumpWidget(
        visual(const PlanProgressCard(planned: 0, target: 2, remaining: 2)),
      );
      await tester.pumpAndSettle();
      await tester.pumpWidget(
        visual(const PlanProgressCard(planned: 1, target: 2, remaining: 1)),
      );
      await tester.pump(const Duration(milliseconds: 150));
      await golden(tester, 'progress-sweeping');
      await tester.pumpAndSettle();
      expect(find.text('1/2'), findsOneWidget);
      await golden(tester, 'progress-half');
    },
  );
}
