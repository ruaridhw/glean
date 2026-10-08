// Widget coverage for the "honest progress" screen (AC-PAN-06): a real
// indeterminate indicator (no fake staged steps), a scan timeout surfaces
// and is recoverable (AC-PAN-14 — the RN app hung on "Almost done…"
// forever), success lands on the shared review screen with the parsed items
// and their categories carried through (AC-BE-04), and both success and
// failure fire a `mediumImpact` haptic (R-11, AC-HAP-05).
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/intake/review_screen.dart';
import 'package:glean/features/intake/scan_progress_screen.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

import '../../support/harness.dart';

class MockHttpClient extends Mock implements http.Client {}

void main() {
  setUpAll(() {
    registerFallbackValue(
      http.Request('POST', Uri.parse('http://localhost:9999/')),
    );
  });

  group('ScanProgressScreen', () {
    late MockHttpClient httpClient;
    late AppTestHarness harness;

    setUp(() {
      httpClient = MockHttpClient();
      harness = AppTestHarness(httpClient: httpClient);
    });

    tearDown(() => harness.dispose());

    Future<void> pumpProgress(
      WidgetTester tester, {
      bool returnToShop = false,
    }) async {
      // Renders `/pantry` first (a real prior frame, establishing it in
      // history) before pushing on top. This checks stacked navigation;
      // replacement navigation is covered separately below.
      await harness.pumpAt(tester, AppRoutes.pantry.path);
      unawaited(
        harness.router.pushNamed(
          AppRoutes.intakeScanProgress.name,
          extra: ScanProgressArgs(
            photoBytes: Uint8List.fromList(<int>[1, 2, 3]),
            returnToShop: returnToShop,
          ),
        ),
      );
      await tester.pump();
      await tester.pump();
    }

    for (final returnToShop in [false, true]) {
      for (final failed in [false, true]) {
        testWidgets(
          'replacement-route ${failed ? 'error Back' : 'pending Cancel'} '
          'returns to ${returnToShop ? 'Shop' : 'Pantry'}',
          (tester) async {
            final response = Completer<http.StreamedResponse>();
            when(
              () => httpClient.send(any()),
            ).thenAnswer((_) => response.future);
            if (failed) {
              response.complete(
                http.StreamedResponse(const Stream<List<int>>.empty(), 500),
              );
            }
            await harness.pumpAt(tester, AppRoutes.pantry.path);
            harness.router.goNamed(
              AppRoutes.intakeScanProgress.name,
              extra: ScanProgressArgs(
                photoBytes: Uint8List.fromList([1, 2, 3]),
                returnToShop: returnToShop,
              ),
            );
            await tester.pump();
            await tester.pump();
            // Let the outgoing shell transition finish before re-entering it.
            await tester.pump(const Duration(milliseconds: 400));
            expect(harness.router.canPop(), isFalse);
            await tester.tap(find.text(failed ? 'Back' : 'Cancel'));
            await tester.pumpAndSettle();
            expect(
              harness.router.routeInformationProvider.value.uri.path,
              returnToShop ? AppRoutes.shop.path : AppRoutes.pantry.path,
            );
            if (!failed) {
              response.complete(
                http.StreamedResponse(
                  Stream.value(utf8.encode(jsonEncode({'items': []}))),
                  200,
                  headers: {'content-type': 'application/json'},
                ),
              );
              await tester.pumpAndSettle();
              expect(find.byType(ReviewScreen), findsNothing);
            }
          },
        );
      }
    }

    testWidgets('shows a real indeterminate spinner, not fake staged steps '
        '(AC-PAN-06)', (WidgetTester tester) async {
      final completer = Completer<http.StreamedResponse>();
      when(() => httpClient.send(any())).thenAnswer((_) => completer.future);

      await pumpProgress(tester);

      expect(find.text('Reading your receipt…'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      // No RN-style "Uploading image" / "Extracting items" fake steps.
      expect(find.textContaining('Uploading'), findsNothing);
      expect(find.textContaining('Extracting'), findsNothing);

      // Avoid an unresolved future outliving the test.
      completer.complete(
        http.StreamedResponse(const Stream<List<int>>.empty(), 500),
      );
      await tester.pump(const Duration(seconds: 1));
    });

    testWidgets('a timeout surfaces a distinct, recoverable message '
        '(AC-PAN-14)', (WidgetTester tester) async {
      // A never-completing Completer, not `Future.delayed` — the latter
      // owns a real `Timer` that would still be "pending" (and fail the
      // test's own timer-leak check) once the client's own 30s
      // `.timeout()` fires first and this test moves on without it.
      final neverResolves = Completer<http.StreamedResponse>();
      addTearDown(
        () => neverResolves.complete(
          http.StreamedResponse(const Stream.empty(), 500),
        ),
      );
      when(
        () => httpClient.send(any()),
      ).thenAnswer((_) => neverResolves.future);

      await pumpProgress(tester);
      // Advance past the client's request timeout (30s) without a real
      // 30-second wait.
      await tester.pump(const Duration(seconds: 31));
      await tester.pump();

      expect(
        find.textContaining('taking longer than expected'),
        findsOneWidget,
      );
      expect(find.text('Try again'), findsOneWidget);
      expect(find.text('Back'), findsOneWidget);
      // R-11: failure fires the ladder's data-commit weight — Flutter has
      // no notification-style haptic, so this plus the message above stand
      // in for one (§7).
      expect(harness.hapticCalls, contains(HapticWeight.medium));

      // Recoverable: "Back" pops out of the flow rather than being stuck.
      await tester.tap(find.text('Back'));
      await tester.pumpAndSettle();
      expect(find.byType(ScanProgressScreen), findsNothing);
    });

    testWidgets('success lands on the review screen carrying category '
        'through (AC-BE-04)', (WidgetTester tester) async {
      when(() => httpClient.send(any())).thenAnswer((_) async {
        final body = jsonEncode(<String, dynamic>{
          'items': <Map<String, dynamic>>[
            <String, dynamic>{
              'name': 'Milk',
              'quantity': 2,
              'unit': 'l',
              'confidence': 0.95,
              'category': 'dairy',
              'food_group': 'dairy',
            },
          ],
        });
        return http.StreamedResponse(
          Stream<List<int>>.value(utf8.encode(body)),
          200,
          headers: const {'content-type': 'application/json'},
        );
      });

      await pumpProgress(tester);
      await tester.pumpAndSettle();

      expect(find.byType(ReviewScreen), findsOneWidget);
      final widget = tester.widget<ReviewScreen>(find.byType(ReviewScreen));
      expect(widget.args.destination, ReviewDestination.pantry);
      expect(widget.args.items.single.name, 'Milk');
      expect(widget.args.items.single.category, 'dairy');
      // R-11: success also fires the ladder's data-commit weight, routed
      // through `hapticsProvider` (AC-HAP-04) rather than `HapticFeedback`
      // directly.
      expect(harness.hapticCalls, contains(HapticWeight.medium));
    });
  });
}
