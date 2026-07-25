import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  group('AppTokens', () {
    testWidgets('resolves through Theme.of(context), not a global const', (
      WidgetTester tester,
    ) async {
      AppTokens? captured;

      await tester.pumpWidget(
        MaterialApp(
          theme: gleanLightTheme,
          home: Builder(
            builder: (BuildContext context) {
              // The only supported access pattern (AC-DS-03): reading it off
              // the ambient Theme, never a top-level `const`/global.
              captured = context.tokens;
              return const SizedBox.shrink();
            },
          ),
        ),
      );

      expect(captured, isNotNull);
      expect(captured!.ink, AppTokens.standard.ink);
      expect(captured!.primaryLight, AppTokens.standard.primaryLight);
      expect(captured!.warning, AppTokens.standard.warning);
      expect(captured!.warningLight, AppTokens.standard.warningLight);
      expect(captured!.radius.pill, 999);
      expect(captured!.spacing.lg, 16);
    });

    test(
      'is the only ThemeExtension registered on gleanLightTheme (AC-DS-02)',
      () {
        final List<ThemeExtension<dynamic>> extensions = gleanLightTheme
            .extensions
            .values
            .toList();
        expect(extensions, hasLength(1));
        expect(extensions.single, isA<AppTokens>());
      },
    );

    test(
      'lerp interpolates colours and falls back cleanly for a non-AppTokens other',
      () {
        const AppTokens a = AppTokens.standard;
        const AppTokens b = AppTokens(
          ink: Colors.black,
          primaryLight: Colors.white,
          warning: Colors.orange,
          warningLight: Colors.orange,
          success: Colors.green,
          successLight: Colors.green,
          radius: AppRadius.standard,
          spacing: AppSpacing.standard,
          shadow: AppShadow.standard,
        );

        final AppTokens mid = a.lerp(b, 0.5);
        expect(mid.ink, Color.lerp(a.ink, b.ink, 0.5));

        // ThemeExtension.lerp's contract requires tolerating an unrelated
        // extension type by returning `this` unchanged.
        expect(a.lerp(null, 0.5), same(a));
      },
    );
  });
}
