import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/router/intake_params.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

import '../../support/harness.dart';

class MockAnswersHttp extends Mock implements http.Client {}

void main() {
  setUpAll(() => registerFallbackValue(Uri.parse('http://localhost/')));
  late MockAnswersHttp client;
  late AppTestHarness harness;
  setUp(() {
    client = MockAnswersHttp();
    harness = AppTestHarness(httpClient: client);
  });
  tearDown(() => harness.dispose());

  Future<void> review(WidgetTester tester) async {
    unawaited(
      harness.router.pushNamed(
        AppRoutes.intakeReview.name,
        extra: const ReviewArgs(
          destination: ReviewDestination.shop,
          originalDescription: 'tacos',
          clarifyingQuestions: ['Meat or beans?'],
          items: [
            ReviewItemDraft(
              reviewId: 'a',
              name: 'beans',
              quantity: 1,
              unit: 'tin',
              confidence: 0.6,
            ),
            ReviewItemDraft(
              reviewId: 'b',
              name: 'onion',
              quantity: 1,
              unit: 'units',
              confidence: 0.6,
            ),
          ],
        ),
      ),
    );
    await tester.pumpWidget(harness.app());
    await tester.pumpAndSettle();
  }

  gleanWidgetTest(
    'answers append original description, retain renamed row edits and unchecked matches, and add new proposals',
    (tester) async {
      Map<String, dynamic>? body;
      when(
        () => client.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer((call) async {
        body =
            jsonDecode(call.namedArguments[#body] as String)
                as Map<String, dynamic>;
        return http.Response(
          jsonEncode({
            'items': [
              {
                'name': 'Beans',
                'food_group': 'protein',
                'category': 'legumes',
                'quantity': 2,
                'unit': 'tin',
                'confidence': 0.9,
              },
              {
                'name': 'onion',
                'food_group': 'vegetables',
                'category': 'alliums',
                'quantity': 2,
                'unit': 'units',
                'confidence': 0.9,
              },
              {
                'name': 'taco shells',
                'food_group': 'carbohydrates',
                'category': 'grains',
                'quantity': 8,
                'unit': 'units',
                'confidence': 0.9,
              },
            ],
            'clarifying_questions': [],
          }),
          200,
        );
      });
      await review(tester);
      await tester.enterText(
        find.widgetWithText(TextField, 'beans'),
        'black beans',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Qty').first,
        '1.5',
      );
      await tester.tap(find.byType(Checkbox).at(1));
      await tester.enterText(
        find.widgetWithText(TextField, 'Answer').first,
        'Beans please',
      );
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Update suggestions'));
      await pumpUntil(
        tester,
        () => find.text('taco shells').evaluate().isNotEmpty,
        description: 'refined suggestions',
      );
      expect(body!['text'], 'tacos\n\nAnswers: Meat or beans?: Beans please');
      expect(find.text('black beans'), findsOneWidget);
      expect(find.text('1.5'), findsOneWidget);
      expect(
        find.text('2'),
        findsOneWidget,
        reason: 'unedited onion quantity must adopt the refined proposal',
      );
      expect(
        tester.widget<Checkbox>(find.byType(Checkbox).at(1)).value,
        isFalse,
      );
      expect(find.text('Add 2 items'), findsOneWidget);
      await tester.tap(find.text('Add 2 items'));
      await tester.pumpAndSettle();
      final saved = await tester.runAsync(
        () => harness.container
            .read(shoppingRepositoryProvider)
            .watchAll(harness.userId)
            .first,
      );
      expect(
        saved!.map((row) => (row.name, row.quantity, row.unit)),
        unorderedEquals([
          ('black beans', 1.5, 'tin'),
          ('taco shells', 8.0, 'units'),
        ]),
      );
    },
  );

  gleanWidgetTest(
    'multiple answer rounds preserve units, removals and selections through final persistence',
    (tester) async {
      final bodies = <String>[];
      when(
        () => client.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer((call) async {
        bodies.add(
          (jsonDecode(call.namedArguments[#body] as String)
                  as Map<String, dynamic>)['text']
              as String,
        );
        return http.Response(
          jsonEncode({
            'items': [
              {
                'name': 'beans',
                'food_group': 'protein',
                'category': 'legumes',
                'quantity': 3,
                'unit': 'g',
                'confidence': 1,
              },
              {
                'name': 'onion',
                'food_group': 'vegetables',
                'category': 'alliums',
                'quantity': 2,
                'unit': 'units',
                'confidence': 1,
              },
              {
                'name': 'peppers',
                'food_group': 'vegetables',
                'category': 'nightshades',
                'quantity': 2,
                'unit': 'units',
                'confidence': 1,
              },
              {
                'name': 'taco shells',
                'food_group': 'carbohydrates',
                'category': 'grains',
                'quantity': 12,
                'unit': 'units',
                'confidence': 1,
              },
            ],
            'clarifying_questions': bodies.length == 1 ? ['Soft or hard?'] : [],
          }),
          200,
        );
      });
      await review(tester);
      await tester.enterText(
        find.widgetWithText(TextField, 'Qty').first,
        '1.5',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Unit').first,
        'kg',
      );
      await tester.tap(find.byTooltip('Remove').at(1));
      await tester.pump();
      await tester.enterText(
        find.widgetWithText(TextField, 'Answer').first,
        'Beans please',
      );
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Update suggestions'));
      await pumpUntil(
        tester,
        () => find.text('Soft or hard?').evaluate().isNotEmpty,
        description: 'second answer round',
      );
      expect(find.text('onion'), findsNothing);
      await tester.tap(find.byType(Checkbox).at(1));
      await tester.enterText(
        find.widgetWithText(TextField, 'Answer').first,
        'Hard shells',
      );
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Update suggestions'));
      await pumpUntil(
        tester,
        () => find.text('Add 2 items').evaluate().isNotEmpty,
        description: 'second refined result',
      );
      expect(bodies.last, contains('Meat or beans?: Beans please'));
      expect(bodies.last, contains('Soft or hard?: Hard shells'));
      await tester.tap(find.text('Add 2 items'));
      await tester.pumpAndSettle();
      final saved = await tester.runAsync(
        () => harness.container
            .read(shoppingRepositoryProvider)
            .watchAll(harness.userId)
            .first,
      );
      expect(
        saved!.map((row) => (row.name, row.quantity, row.unit)),
        unorderedEquals([('beans', 1.5, 'kg'), ('taco shells', 12.0, 'units')]),
      );
    },
  );

  gleanWidgetTest('a failed reparse keeps edits and offers retry', (
    tester,
  ) async {
    when(
      () => client.post(
        any(),
        headers: any(named: 'headers'),
        body: any(named: 'body'),
      ),
    ).thenAnswer((_) async => http.Response('{}', 500));
    await review(tester);
    await tester.enterText(
      find.widgetWithText(TextField, 'Answer').first,
      'Beans',
    );
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Update suggestions'));
    await pumpUntil(
      tester,
      () => find
          .text('Could not update suggestions. Try again.')
          .evaluate()
          .isNotEmpty,
      description: 'reparse error',
    );
    expect(find.text('beans'), findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Update suggestions'),
          )
          .onPressed,
      isNotNull,
    );
  });
}
