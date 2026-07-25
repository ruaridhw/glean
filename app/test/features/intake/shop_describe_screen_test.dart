// Widget coverage for the Shop "describe" flow (FINDINGS.md F-16): the
// screen the router wave's placeholder was silently standing in for until
// now. Parses a description, carries clarifying questions through to the
// shared review screen with `ReviewDestination.shop`, and surfaces a
// timeout / validation error recoverably rather than dead-ending.
//
// Uses `gleanWidgetTest` (releases the drift-watching tree in-body) and
// `pumpUntil`/`pumpPastSkeleton` rather than `pumpAndSettle` — this screen's
// submit button shows a genuinely indeterminate `CircularProgressIndicator`
// while a request is pending (AC-PAN-06's honest-progress requirement
// applies here too), which never reaches a quiescent frame (FINDINGS.md
// F-12/F-13).
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/intake/review_screen.dart';
import 'package:glean/features/intake/shop_describe_screen.dart';
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

  group('ShopDescribeScreen', () {
    late MockHttpClient httpClient;
    late AppTestHarness harness;

    setUp(() {
      httpClient = MockHttpClient();
      harness = AppTestHarness(httpClient: httpClient);
    });

    tearDown(() => harness.dispose());

    Future<void> pumpDescribe(WidgetTester tester) async {
      unawaited(harness.router.pushNamed(AppRoutes.intakeDescribeShop.name));
      await tester.pumpWidget(harness.app());
      await tester.pump();
    }

    gleanWidgetTest('the flow is reachable and no longer a dead-end '
        'placeholder (FINDINGS.md F-16)', (WidgetTester tester) async {
      await pumpDescribe(tester);

      expect(find.text('Describe list'), findsOneWidget);
      expect(find.byType(ShopDescribeScreen), findsOneWidget);
      // The tab bar is absent: this route sits outside the shell.
      expect(find.byType(NavigationBar), findsNothing);
    });

    gleanWidgetTest('parses a description and navigates to the review '
        'screen with destination shop, carrying clarifying questions '
        'through', (WidgetTester tester) async {
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
                'name': 'milk',
                'quantity': 1,
                'unit': 'l',
                'confidence': 0.9,
                'category': 'dairy',
                'food_group': 'dairy',
              },
            ],
            'clarifying_questions': ['Semi-skimmed or whole?'],
          }),
          200,
          headers: const {'content-type': 'application/json'},
        ),
      );

      await pumpDescribe(tester);

      await tester.enterText(find.byType(TextField), 'milk');
      await tester.pump();
      await tester.tap(find.text('Review items'));
      // Not `pumpAndSettle`: the button shows a real indeterminate spinner
      // while the request is in flight.
      await pumpUntil(
        tester,
        () => find.byType(ReviewScreen).evaluate().isNotEmpty,
        description: 'navigation to the review screen',
      );

      final widget = tester.widget<ReviewScreen>(find.byType(ReviewScreen));
      expect(widget.args.destination, ReviewDestination.shop);
      expect(widget.args.items.single.name, 'milk');
      expect(widget.args.items.single.category, 'dairy');
      // Pantry-only field never carried for a shop draft.
      expect(widget.args.items.single.unitPrice, isNull);
      expect(widget.args.clarifyingQuestions, <String>[
        'Semi-skimmed or whole?',
      ]);

      await pumpUntil(
        tester,
        () => find.text('Semi-skimmed or whole?').evaluate().isNotEmpty,
        description: 'the clarifying-questions card',
      );
    });

    gleanWidgetTest('a validation error surfaces and is recoverable', (
      WidgetTester tester,
    ) async {
      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer((_) async => http.Response('unprocessable', 422));

      await pumpDescribe(tester);

      await tester.enterText(find.byType(TextField), 'gibberish');
      await tester.pump();
      await tester.tap(find.text('Review items'));
      await pumpUntil(
        tester,
        () => find
            .textContaining('Could not turn that into a list')
            .evaluate()
            .isNotEmpty,
        description: 'the inline validation error',
      );

      expect(find.byType(ReviewScreen), findsNothing);

      // Recoverable: editing and resubmitting works, no dead end.
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
      await tester.enterText(find.byType(TextField), 'milk, bananas');
      await tester.pump();
      await tester.tap(find.text('Review items'));
      await pumpUntil(
        tester,
        () => find.byType(ReviewScreen).evaluate().isNotEmpty,
        description: 'recovery navigation to the review screen',
      );
    });

    gleanWidgetTest('a timeout surfaces a distinct, recoverable message '
        'rather than hanging (AC-PAN-14)', (WidgetTester tester) async {
      // A never-completing Completer, not `Future.delayed` — the latter
      // owns a real `Timer` that would still be "pending" once the
      // client's own 30s `.timeout()` fires first (see
      // `scan_progress_screen_test.dart` for the same pitfall).
      final neverResolves = Completer<http.Response>();
      addTearDown(() => neverResolves.complete(http.Response('', 500)));
      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer((_) => neverResolves.future);

      await pumpDescribe(tester);

      await tester.enterText(find.byType(TextField), 'milk');
      await tester.pump();
      await tester.tap(find.text('Review items'));

      // Advance past the client's request timeout (30s) in fixed steps —
      // never `pumpAndSettle` against the spinner that's on screen while
      // this is pending.
      await pumpUntil(
        tester,
        () => find
            .textContaining('Could not turn that into a list')
            .evaluate()
            .isNotEmpty,
        step: const Duration(seconds: 2),
        maxSteps: 20,
        description: 'the timeout error',
      );

      expect(find.byType(ReviewScreen), findsNothing);
      // Still on the describe screen, with a usable submit button — never a
      // dead end (AC-PAN-14; the RN app's scan-progress equivalent hung
      // forever on "Almost done…").
      expect(find.byType(ShopDescribeScreen), findsOneWidget);
      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNotNull,
      );
    });
  });
}
