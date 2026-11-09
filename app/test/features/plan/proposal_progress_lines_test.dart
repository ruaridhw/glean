import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/plan/widgets/proposal_meal_card.dart';

void main() {
  testWidgets('the spinner on the newest line is a circle, not an oval', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: gleanLightTheme,
        home: const Scaffold(
          body: ProposalProgressLines(
            lines: <String>['Reading your pantry', 'Choosing meals'],
          ),
        ),
      ),
    );

    final Size size = tester.getSize(find.byType(CircularProgressIndicator));
    expect(size.width, size.height);
  });
}
