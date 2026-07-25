// AC-PLAN-14: nav params are typed objects, not serialised strings. The RN
// app did an unguarded `JSON.parse` on a nav param and could white-screen a
// route with no back button (§11) — there is no decode step here to fail,
// so these tests assert the exact typed object survives the round trip.

import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/intake/review_screen.dart';
import 'package:glean/features/intake/scan_progress_screen.dart';
import 'package:glean/features/intake/scan_screen.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';

import '../support/harness.dart';

void main() {
  late AppTestHarness harness;

  setUp(() {
    harness = AppTestHarness();
  });

  tearDown(() => harness.dispose());

  Future<void> pump(WidgetTester tester) async {
    await tester.pumpWidget(harness.app());
    await tester.pumpAndSettle();
  }

  testWidgets('ScanArgs round-trips as a real object, not a query string', (
    tester,
  ) async {
    const args = ScanArgs(returnToShop: true);
    unawaited(harness.router.push(AppRoutes.intakeScan.path, extra: args));
    await pump(tester);

    final widget = tester.widget<ScanScreen>(find.byType(ScanScreen));
    expect(widget.args, same(args));
    expect(widget.args.returnToShop, isTrue);
  });

  testWidgets('ScanProgressArgs carries raw bytes, no base64 string param', (
    tester,
  ) async {
    final photoBytes = Uint8List.fromList(<int>[1, 2, 3, 4, 5]);
    final args = ScanProgressArgs(photoBytes: photoBytes, returnToShop: true);
    unawaited(
      harness.router.push(AppRoutes.intakeScanProgress.path, extra: args),
    );
    await pump(tester);

    final widget = tester.widget<ScanProgressScreen>(
      find.byType(ScanProgressScreen),
    );
    expect(widget.args, same(args));
    expect(widget.args.photoBytes, equals(photoBytes));
  });

  testWidgets(
    'ReviewArgs carries structured items and questions, not JSON strings',
    (tester) async {
      const args = ReviewArgs(
        destination: ReviewDestination.shop,
        items: <ReviewItemDraft>[
          ReviewItemDraft(
            reviewId: 'a',
            name: 'Milk',
            quantity: 2,
            unit: 'l',
            confidence: 0.9,
          ),
        ],
        clarifyingQuestions: <String>['Semi-skimmed or whole?'],
      );
      unawaited(harness.router.push(AppRoutes.intakeReview.path, extra: args));
      await pump(tester);

      final widget = tester.widget<ReviewScreen>(find.byType(ReviewScreen));
      expect(widget.args, same(args));
      expect(widget.args.destination, ReviewDestination.shop);
      expect(widget.args.items.single.name, 'Milk');
      expect(widget.args.clarifyingQuestions, <String>[
        'Semi-skimmed or whole?',
      ]);
    },
  );

  testWidgets(
    'missing extra on a route that requires it shows a recoverable error',
    (tester) async {
      unawaited(harness.router.push(AppRoutes.intakeReview.path));
      await pump(tester);

      expect(find.text('Nothing to review.'), findsOneWidget);
      expect(find.byType(ReviewScreen), findsNothing);
    },
  );

  test(
    'ReviewItemDraft and ReviewArgs value-equality holds across separate instances',
    () {
      const a = ReviewItemDraft(
        reviewId: 'x',
        name: 'Eggs',
        quantity: 6,
        unit: 'units',
        confidence: 0.8,
      );
      const b = ReviewItemDraft(
        reviewId: 'x',
        name: 'Eggs',
        quantity: 6,
        unit: 'units',
        confidence: 0.8,
      );
      expect(a, equals(b));

      const argsA = ReviewArgs(
        destination: ReviewDestination.pantry,
        items: <ReviewItemDraft>[a],
      );
      const argsB = ReviewArgs(
        destination: ReviewDestination.pantry,
        items: <ReviewItemDraft>[b],
      );
      expect(argsA, equals(argsB));
    },
  );
}
