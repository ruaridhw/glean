import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import '../support/visual.dart';

void main() {
  setUpAll(loadBrandFonts);
  testWidgets('a rendered warning badge follows alternate ambient tokens', (
    tester,
  ) async {
    final alternate = AppTokens.standard.copyWith(
      warning: Colors.white,
      warningLight: Colors.deepPurple,
    );
    await tester.pumpWidget(
      visual(
        const Center(
          child: GleanBadge(label: '3 expiring', tone: GleanBadgeTone.warning),
        ),
        theme: gleanLightTheme.copyWith(extensions: [alternate]),
      ),
    );
    await golden(tester, 'tokens-alternate');
  });
  test('lerp interpolates colours and tolerates an unrelated extension', () {
    const a = AppTokens.standard;
    final b = a.copyWith(ink: Colors.black);
    expect(a.lerp(b, 0.5).ink, Color.lerp(a.ink, b.ink, 0.5));
    expect(a.lerp(null, 0.5), same(a));
  });
}
