import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/intake/widgets/review_item_row.dart';

void main() {
  for (final scale in [1.0, 2.0]) {
    testWidgets('quantity validation wraps without truncation at ${scale}x', (
      tester,
    ) async {
      final name = TextEditingController(text: 'flour');
      final quantity = TextEditingController(text: '0');
      final unit = TextEditingController(text: 'g');
      addTearDown(name.dispose);
      addTearDown(quantity.dispose);
      addTearDown(unit.dispose);
      const error = 'Enter a quantity greater than 0';
      await tester.pumpWidget(
        MaterialApp(
          theme: gleanLightTheme,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: TextScaler.linear(scale)),
            child: child!,
          ),
          home: Scaffold(
            body: Center(
              child: SizedBox(
                width: 390,
                child: SingleChildScrollView(
                  child: ReviewItemRow(
                    nameController: name,
                    quantityController: quantity,
                    unitController: unit,
                    confidence: 0.9,
                    quantityErrorText: error,
                    onRemove: () {},
                  ),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final paragraph = tester.renderObject<RenderParagraph>(find.text(error));
      expect(paragraph.overflow, isNot(TextOverflow.ellipsis));
      expect(paragraph.didExceedMaxLines, isFalse);
      expect(tester.takeException(), isNull);
    });
  }
}
