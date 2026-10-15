import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import '../support/visual.dart';

void main() {
  setUpAll(loadBrandFonts);
  testWidgets('brand typography renders distinct heading and body roles', (
    tester,
  ) async {
    await tester.pumpWidget(
      visual(
        Builder(
          builder: (context) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'A little less waste.',
                style: Theme.of(context).textTheme.headlineLarge,
              ),
              const SizedBox(height: 20),
              Text(
                'Cook with what you have.',
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              Text('PANTRY', style: Theme.of(context).textTheme.labelSmall),
            ],
          ),
        ),
      ),
    );
    await golden(tester, 'theme-typography');
  });
  testWidgets(
    'brand palette renders actual primary, warning and error states',
    (tester) async {
      await tester.pumpWidget(
        visual(
          Column(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              FilledButton(onPressed: () {}, child: const Text('Add to plan')),
              const GleanBadge(
                label: '3 expiring',
                tone: GleanBadgeTone.warning,
              ),
              const GleanBadge(
                label: 'Could not save',
                tone: GleanBadgeTone.danger,
              ),
            ],
          ),
        ),
      );
      await golden(tester, 'theme-palette');
    },
  );
}
