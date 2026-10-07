import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../support/visual.dart';

void main() {
  setUpAll(loadBrandFonts);
  testWidgets(
    'filled confirmation has branded output and becomes inert when disabled',
    (tester) async {
      var taps = 0;
      await tester.pumpWidget(
        visual(
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
      await golden(tester, 'button-filled');
      await tester.tap(find.text('Confirm'));
      expect(taps, 1);
      await tester.pumpWidget(
        visual(
          const Center(
            child: FilledButton(onPressed: null, child: Text('Confirm')),
          ),
        ),
      );
      await tester.tap(find.text('Confirm'));
      expect(taps, 1);
    },
  );
  testWidgets('outlined cooking action renders and dispatches one activation', (
    tester,
  ) async {
    var taps = 0;
    await tester.pumpWidget(
      visual(
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
    await golden(tester, 'button-outlined');
    await tester.tap(find.text('Cooked?'));
    expect(taps, 1);
  });
  testWidgets('dietary chip toggles its visible selection and announces it', (
    tester,
  ) async {
    var selected = false;
    await tester.pumpWidget(
      visual(
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
    await golden(tester, 'chip-selected');
  });
  testWidgets('remove icon has a discoverable action and one activation', (
    tester,
  ) async {
    var taps = 0;
    await tester.pumpWidget(
      visual(
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
    await golden(tester, 'button-icon');
    await tester.tap(find.byTooltip('Remove recipe'));
    expect(taps, 1);
  });
}
