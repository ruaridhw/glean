import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import '../support/visual.dart';

void main() {
  setUpAll(loadBrandFonts);
  testWidgets('vendored mark variants render their real artwork at app sizes', (
    tester,
  ) async {
    await tester.pumpWidget(
      visual(
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            for (final asset in GleanMarkAsset.values)
              GleanMark(asset: asset, size: 72),
          ],
        ),
      ),
    );
    await tester.pumpAndSettle();
    await golden(tester, 'brand-variants');
  });
  testWidgets('large mark retains its visible stem, outline and shadow', (
    tester,
  ) async {
    await tester.pumpWidget(visual(const Center(child: GleanMark(size: 180))));
    await tester.pumpAndSettle();
    await golden(tester, 'brand-large');
  });
}
