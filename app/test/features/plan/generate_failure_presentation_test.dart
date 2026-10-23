// The Plan tab's Generate presentation: the spinner is unchanged while a session runs, and a failure shows the
// approved catalogue copy with its action. The copy is V1's design gate, so these assertions are verbatim.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/diagnostics/diagnostics_exporter.dart';
import 'package:glean/features/settings/settings_screen.dart';
import 'package:glean/router/app_routes.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../support/harness.dart';
import '../../support/session_backend.dart';

void main() {
  Map<String, dynamic> pick(String id) => {
    'recipe_id': null,
    'external_id': id,
    'title': 'Corpus $id',
    'reason': 'fit',
  };

  /// A backend whose session reports [statuses] in order, then `done` with one pick.
  http.Client scripted(
    List<Map<String, dynamic>> polls, {
    List<int>? pollsSeen,
  }) {
    var index = 0;
    return MockClient((http.Request request) async {
      if (request.method == 'POST') {
        return http.Response('{"session_id":"s1"}', 202);
      }
      if (request.url.path.startsWith('/meal-plan/sessions/')) {
        pollsSeen?.add(1);
        if (index < polls.length) {
          final Map<String, dynamic> body = polls[index++];
          return http.Response(
            jsonEncode({
              'status': body['status'],
              'progress': body['progress'] ?? <String>[],
              'cursor': index,
              'result': null,
              'error': body['error'],
            }),
            200,
          );
        }
        return sessionDone({
          'suggestions': [pick('rec_a')],
        });
      }
      final String id = request.url.pathSegments.last;
      return http.Response(
        jsonEncode({
          'external_id': id,
          'title': 'Corpus $id',
          'ingredients': [
            {'canonical_name': 'beans', 'quantity': 200, 'unit': 'g'},
          ],
        }),
        200,
      );
    });
  }

  gleanWidgetTest(
    'the Generate spinner is unchanged while the session runs, and progress '
    'lines stay off screen',
    (tester) async {
      var polls = 0;
      final h = AppTestHarness(
        httpClient: MockClient((request) async {
          if (request.method == 'POST') {
            return http.Response('{"session_id":"s1"}', 202);
          }
          if (!request.url.path.startsWith('/meal-plan/sessions/')) {
            final String id = request.url.pathSegments.last;
            return http.Response(
              jsonEncode({
                'external_id': id,
                'title': 'Corpus $id',
                'ingredients': [
                  {'canonical_name': 'beans', 'quantity': 200, 'unit': 'g'},
                ],
              }),
              200,
            );
          }
          polls++;
          if (polls < 3) {
            return http.Response(
              jsonEncode({
                'status': 'running',
                'progress': ['Ranking recipes'],
                'cursor': polls,
                'result': null,
                'error': null,
              }),
              200,
            );
          }
          return sessionDone({
            'suggestions': [pick('rec_a')],
          });
        }),
      );
      addTearDown(h.dispose);
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await pumpUntil(tester, () => polls >= 1, description: 'the first poll');
      expect(find.text('Generating'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Generating'),
            )
            .onPressed,
        isNull,
        reason: 'a second tap cannot open a second session',
      );
      expect(
        find.textContaining('Ranking recipes'),
        findsNothing,
        reason: 'V1 shows no progress lines',
      );

      await pumpUntil(
        tester,
        () => polls >= 3,
        description: 'the session finishing',
      );
      await tester.pumpAndSettle();
      expect(find.text('Generating'), findsNothing);
      expect(
        find.textContaining('Week generated'),
        findsOneWidget,
        reason: 'a done result commits and reports as before',
      );
    },
  );

  gleanWidgetTest(
    'no_eligible_recipes shows its copy and Open Settings, which opens '
    'Settings',
    (tester) async {
      final h = AppTestHarness(
        httpClient: scripted([
          {
            'status': 'failed',
            'error': {
              'code': 'no_eligible_recipes',
              'retry_after_minutes': null,
            },
          },
        ]),
      );
      addTearDown(h.dispose);
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle();

      expect(
        find.text('No recipes fit your diet and time limit.'),
        findsOneWidget,
      );
      expect(find.text('Open Settings'), findsOneWidget);

      await tester.tap(find.text('Open Settings'));
      await tester.pumpAndSettle();
      expect(find.byType(SettingsScreen), findsOneWidget);
    },
  );

  gleanWidgetTest(
    'model_error shows the generic copy and Retry starts a new session',
    (tester) async {
      final h = AppTestHarness(
        httpClient: scripted([
          {
            'status': 'failed',
            'error': {'code': 'model_error', 'retry_after_minutes': null},
          },
        ]),
      );
      addTearDown(h.dispose);
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle();

      expect(
        find.text('Something went wrong planning your week.'),
        findsOneWidget,
      );
      expect(find.textContaining('model_error'), findsNothing);

      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Week generated'), findsOneWidget);
    },
  );

  gleanWidgetTest(
    'invalid_request shows its copy and Report exports diagnostics',
    (tester) async {
      final h = AppTestHarness(
        httpClient: scripted([
          {
            'status': 'failed',
            'error': {'code': 'invalid_request', 'retry_after_minutes': null},
          },
        ]),
        overrides: [
          diagnosticsExportProvider.overrideWithValue(
            () async => 'exports/test-user/2026-10-22',
          ),
        ],
      );
      addTearDown(h.dispose);
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle();

      expect(find.text("Glean couldn't read this request."), findsOneWidget);
      await tester.tap(find.text('Report'));
      await tester.pumpAndSettle();
      expect(
        find.text('Diagnostics exported to exports/test-user/2026-10-22'),
        findsOneWidget,
      );
    },
  );

  gleanWidgetTest('rate_limited says how long to wait and offers no action', (
    tester,
  ) async {
    final h = AppTestHarness(
      httpClient: MockClient(
        (request) async => http.Response(
          '{"detail":"AI request limit reached"}',
          429,
          headers: {'retry-after': '180'},
        ),
      ),
    );
    addTearDown(h.dispose);
    await h.pumpAt(tester, AppRoutes.plan.path);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
    await tester.pumpAndSettle();

    expect(
      find.text("You've used too many AI credits. Try again in 3 minutes."),
      findsOneWidget,
    );
    expect(find.byType(SnackBarAction), findsNothing);
  });
}
