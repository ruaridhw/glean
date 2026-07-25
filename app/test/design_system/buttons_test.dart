import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

/// Renders the built-in button widgets with *no* local style overrides —
/// every visual comes from `gleanLightTheme`'s `*ButtonTheme`s (AC-DS-04,
/// AC-DS-05). If a screen ever needed to pass its own `style:`/radius to get
/// the brand look, that would be exactly the "hand-rolled pill button"
/// AC-DS-05 rules out.
void main() {
  group('Themed buttons', () {
    testWidgets('FilledButton is pill-shaped and brand-coloured from the theme', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: gleanLightTheme,
          home: Scaffold(
            body: FilledButton(onPressed: () {}, child: const Text('Confirm')),
          ),
        ),
      );

      final ThemeData theme = Theme.of(tester.element(find.text('Confirm')));
      final ButtonStyle themed = theme.filledButtonTheme.style!;

      expect(
        themed.shape?.resolve(<WidgetState>{}),
        isA<StadiumBorder>(),
        reason:
            'pill shape must come from FilledButtonThemeData, not a local BorderRadius',
      );
      expect(
        themed.backgroundColor?.resolve(<WidgetState>{}),
        theme.colorScheme.primary,
      );
      expect(themed.foregroundColor?.resolve(<WidgetState>{}), Colors.white);
    });

    testWidgets('OutlinedButton is pill-shaped with the brand primary border', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: gleanLightTheme,
          home: Scaffold(
            body: OutlinedButton(
              onPressed: () {},
              child: const Text('Cooked?'),
            ),
          ),
        ),
      );

      final ThemeData theme = Theme.of(tester.element(find.text('Cooked?')));
      final ButtonStyle themed = theme.outlinedButtonTheme.style!;

      expect(themed.shape?.resolve(<WidgetState>{}), isA<StadiumBorder>());
      expect(
        themed.side?.resolve(<WidgetState>{})?.color,
        theme.colorScheme.primary,
      );
    });

    testWidgets(
      'the pill-chip variant (FilterChip) is stadium-shaped from ChipThemeData',
      (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            theme: gleanLightTheme,
            home: Scaffold(
              body: FilterChip(
                label: const Text('Vegetarian'),
                selected: false,
                onSelected: (_) {},
              ),
            ),
          ),
        );

        final ThemeData theme = Theme.of(
          tester.element(find.text('Vegetarian')),
        );
        expect(theme.chipTheme.shape, isA<StadiumBorder>());
      },
    );

    testWidgets('IconButton is a 40x40 pill from IconButtonThemeData', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: gleanLightTheme,
          home: Scaffold(
            body: IconButton(
              onPressed: () {},
              icon: const Icon(Icons.close_rounded),
            ),
          ),
        ),
      );

      final ThemeData theme = Theme.of(
        tester.element(find.byIcon(Icons.close_rounded)),
      );
      final ButtonStyle themed = theme.iconButtonTheme.style!;
      expect(themed.fixedSize?.resolve(<WidgetState>{}), const Size.square(40));
    });
  });
}
