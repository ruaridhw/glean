import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  group('GleanBadge', () {
    testWidgets(
      'renders a pill using the theme radius and colour roles, per tone',
      (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            theme: gleanLightTheme,
            home: const Scaffold(
              body: Column(
                children: <Widget>[
                  GleanBadge(label: '3 expiring', tone: GleanBadgeTone.warning),
                  GleanBadge(label: 'In plan', tone: GleanBadgeTone.primary),
                ],
              ),
            ),
          ),
        );

        final BuildContext context = tester.element(find.text('3 expiring'));
        final AppTokens tokens = context.tokens;
        final ColorScheme colorScheme = Theme.of(context).colorScheme;

        final Container warningContainer = tester.widget<Container>(
          find
              .ancestor(
                of: find.text('3 expiring'),
                matching: find.byType(Container),
              )
              .first,
        );
        final BoxDecoration warningDecoration =
            warningContainer.decoration! as BoxDecoration;
        expect(warningDecoration.color, tokens.warningLight);
        expect(
          warningDecoration.borderRadius,
          BorderRadius.circular(tokens.radius.pill),
          reason:
              'GleanBadge must read its pill radius off AppTokens, not a local constant',
        );

        final Container primaryContainer = tester.widget<Container>(
          find
              .ancestor(
                of: find.text('In plan'),
                matching: find.byType(Container),
              )
              .first,
        );
        final BoxDecoration primaryDecoration =
            primaryContainer.decoration! as BoxDecoration;
        expect(primaryDecoration.color, colorScheme.primaryContainer);
      },
    );
  });
}
