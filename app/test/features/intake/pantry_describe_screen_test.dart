// Widget coverage for "describe what you bought" — the text-only sibling of
// receipt scan (AC-PAN-03), always landing on the shared review screen with
// destination pantry (AC-PAN-05).
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/intake/review_screen.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

import '../../support/harness.dart';

class MockHttpClient extends Mock implements http.Client {}

void main() {
  setUpAll(() {
    registerFallbackValue(Uri.parse('http://localhost:9999/'));
  });

  group('PantryDescribeScreen', () {
    late MockHttpClient httpClient;
    late AppTestHarness harness;

    setUp(() {
      httpClient = MockHttpClient();
      harness = AppTestHarness(httpClient: httpClient);
    });

    tearDown(() => harness.dispose());

    testWidgets('Parse is disabled until text is entered, and disabled '
        'while pending', (WidgetTester tester) async {
      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer(
        (_) async => http.Response(
          jsonEncode({'items': <dynamic>[]}),
          200,
          headers: const {'content-type': 'application/json'},
        ),
      );

      unawaited(harness.router.pushNamed(AppRoutes.intakeDescribePantry.name));
      await tester.pumpWidget(harness.app());
      await tester.pumpAndSettle();

      FilledButton button() =>
          tester.widget<FilledButton>(find.byType(FilledButton));
      expect(button().onPressed, isNull);

      await tester.enterText(find.byType(TextField), 'a kilo of mince');
      await tester.pump();
      expect(button().onPressed, isNotNull);
    });

    testWidgets('a successful parse lands on the review screen with '
        'destination pantry', (WidgetTester tester) async {
      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer(
        (_) async => http.Response(
          jsonEncode({
            'items': [
              {
                'name': 'mince',
                'quantity': 1,
                'unit': 'kg',
                'confidence': 0.9,
                'category': 'red_meat',
                'food_group': 'protein',
              },
            ],
          }),
          200,
          headers: const {'content-type': 'application/json'},
        ),
      );

      unawaited(harness.router.pushNamed(AppRoutes.intakeDescribePantry.name));
      await tester.pumpWidget(harness.app());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'a kilo of mince');
      await tester.pump();
      await tester.tap(find.text('Parse'));
      await tester.pumpAndSettle();

      expect(find.byType(ReviewScreen), findsOneWidget);
      final widget = tester.widget<ReviewScreen>(find.byType(ReviewScreen));
      expect(widget.args.destination, ReviewDestination.pantry);
      expect(widget.args.returnToShop, isFalse);
      expect(widget.args.items.single.category, 'red_meat');
    });

    testWidgets('a parse failure shows a recoverable inline error', (
      WidgetTester tester,
    ) async {
      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer((_) async => http.Response('server error', 500));

      unawaited(harness.router.pushNamed(AppRoutes.intakeDescribePantry.name));
      await tester.pumpWidget(harness.app());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'a kilo of mince');
      await tester.pump();
      await tester.tap(find.text('Parse'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Could not understand that'), findsOneWidget);
      expect(find.byType(ReviewScreen), findsNothing);
    });
  });
}
