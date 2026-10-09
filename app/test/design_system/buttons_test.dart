import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

Widget host(Widget child, {ThemeData? theme, double scale = 1}) => MaterialApp(
  theme: theme ?? gleanLightTheme,
  home: Scaffold(
    body: Center(
      child: MediaQuery(
        data: MediaQueryData(textScaler: TextScaler.linear(scale)),
        child: child,
      ),
    ),
  ),
);

void main() {
  testWidgets(
    'filled confirmation dispatches one activation and becomes inert when disabled',
    (tester) async {
      var taps = 0;
      await tester.pumpWidget(
        host(
          Center(
            child: FilledButton(
              onPressed: () {
                taps++;
              },
              child: const Text('Confirm'),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Confirm'));
      expect(taps, 1);
      await tester.pumpWidget(
        host(
          const Center(
            child: FilledButton(onPressed: null, child: Text('Confirm')),
          ),
        ),
      );
      await tester.tap(find.text('Confirm'));
      expect(taps, 1);
    },
  );
  testWidgets('outlined cooking action dispatches one activation', (
    tester,
  ) async {
    var taps = 0;
    await tester.pumpWidget(
      host(
        Center(
          child: OutlinedButton(
            onPressed: () {
              taps++;
            },
            child: const Text('Cooked?'),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Cooked?'));
    expect(taps, 1);
  });
  testWidgets('dietary chip toggles its visible selection and announces it', (
    tester,
  ) async {
    var selected = false;
    await tester.pumpWidget(
      host(
        StatefulBuilder(
          builder: (context, setState) => Center(
            child: FilterChip(
              label: const Text('Vegetarian'),
              selected: selected,
              onSelected: (value) => setState(() => selected = value),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Vegetarian'));
    await tester.pumpAndSettle();
    expect(selected, isTrue);
    expect(
      tester.getSemantics(find.byType(FilterChip)).label,
      contains('Vegetarian'),
    );
  });
  testWidgets('remove icon has a discoverable action and one activation', (
    tester,
  ) async {
    var taps = 0;
    await tester.pumpWidget(
      host(
        Center(
          child: IconButton(
            tooltip: 'Remove recipe',
            onPressed: () {
              taps++;
            },
            icon: const Icon(Icons.close_rounded),
          ),
        ),
      ),
    );
    await tester.tap(find.byTooltip('Remove recipe'));
    expect(taps, 1);
  });
}
