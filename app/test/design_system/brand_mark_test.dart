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
          MaterialApp(home: GleanMark(asset: asset, size: 32)),
        );
        await tester.pumpAndSettle();

        expect(find.byType(SvgPicture), findsOneWidget);
      }
    });
  });
}
