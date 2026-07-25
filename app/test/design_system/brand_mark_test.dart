import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  group('GleanMark', () {
    testWidgets('renders each vendored brand SVG via flutter_svg (AC-DS-07)', (
      WidgetTester tester,
    ) async {
      for (final GleanMarkAsset asset in GleanMarkAsset.values) {
        await tester.pumpWidget(
          // `theme` is required here (not a bare `MaterialApp`) —
          // `GleanMark` reads `context.tokens` for its F-01 drop shadow,
          // which asserts if no `AppTokens` extension is registered.
          MaterialApp(
            theme: gleanLightTheme,
            home: GleanMark(asset: asset, size: 32),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.byType(SvgPicture), findsOneWidget);
      }
    });

    testWidgets(
      'reapplies the shadow the stripped SVG filter used to draw (F-01)',
      (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(theme: gleanLightTheme, home: const GleanMark(size: 32)),
        );
        await tester.pumpAndSettle();

        final DecoratedBox box = tester.widget<DecoratedBox>(
          find.ancestor(
            of: find.byType(SvgPicture),
            matching: find.byType(DecoratedBox),
          ),
        );
        final BoxDecoration decoration = box.decoration as BoxDecoration;
        expect(decoration.boxShadow, isNotEmpty);
      },
    );
  });
}
