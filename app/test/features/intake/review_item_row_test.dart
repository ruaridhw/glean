import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';

import '../../support/harness.dart';

void main() {
  for (final scale in [1.0, 2.0]) {
    for (final state in ['filled', 'focused', 'quantity error']) {
      gleanWidgetTest('review labels stay clear of fields: $state at ${scale}x', (
        tester,
      ) async {
        final harness = AppTestHarness();
        addTearDown(harness.dispose);
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        tester.platformDispatcher.textScaleFactorTestValue = scale;
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
        harness.router.goNamed(
          AppRoutes.intakeReview.name,
          extra: const ReviewArgs(
            destination: ReviewDestination.pantry,
            items: [
              ReviewItemDraft(
                reviewId: 'flour',
                name: 'flour',
                quantity: 1,
                unit: 'g',
                confidence: 0.9,
              ),
            ],
          ),
        );
        await tester.pumpWidget(harness.app());
        await tester.pumpAndSettle();
        final quantity = find.byType(TextField).at(1);
        if (state == 'focused') {
          await tester.tap(quantity);
        } else if (state == 'quantity error') {
          await tester.enterText(quantity, '0');
        }
        await tester.pumpAndSettle();

        for (final (label, index) in [('Qty', 1), ('Unit', 2)]) {
          final editable = find.descendant(
            of: find.byType(TextField).at(index),
            matching: find.byType(EditableText),
          );
          final container = InputDecorator.containerOf(
            tester.element(editable),
          )!;
          final top = container.localToGlobal(Offset.zero).dy;
          final labelBounds = tester.getRect(find.text(label));
          expect(labelBounds.bottom, lessThanOrEqualTo(top - 4));
          expect(labelBounds.left, closeTo(tester.getTopLeft(editable).dx, 1));
        }
        final group = find.byType(DropdownButtonFormField<String>);
        final decorator = find.descendant(
          of: group,
          matching: find.byType(InputDecorator),
        );
        final groupContainer = InputDecorator.containerOf(
          tester.element(
            find.text(
              "Optional: we couldn't identify an ingredient group for this item.",
            ),
          ),
        )!;
        expect(
          tester.getBottomLeft(find.text('Ingredient group')).dy,
          lessThanOrEqualTo(groupContainer.localToGlobal(Offset.zero).dy - 4),
        );
        expect(decorator, findsOneWidget);
        if (state == 'quantity error') {
          final error = find.text('Enter a quantity greater than 0');
          final paragraph = tester.renderObject<RenderParagraph>(error);
          expect(paragraph.overflow, isNot(TextOverflow.ellipsis));
          expect(paragraph.didExceedMaxLines, isFalse);
          // The message uses the card's available width, not the narrow
          // quantity field, and sits below both quantity and unit inputs.
          final nameBounds = tester.getRect(find.byType(TextField).first);
          final errorBounds = tester.getRect(error);
          expect(errorBounds.width, greaterThanOrEqualTo(nameBounds.width));
          expect(
            errorBounds.top,
            greaterThan(tester.getBottomRight(find.byType(TextField).at(2)).dy),
          );
          expect(
            tester.getTopLeft(error).dy,
            greaterThan(
              tester
                  .getBottomLeft(
                    find.descendant(
                      of: quantity,
                      matching: find.byType(EditableText),
                    ),
                  )
                  .dy,
            ),
          );
        }
        expect(tester.takeException(), isNull);
      });
    }
  }
}
