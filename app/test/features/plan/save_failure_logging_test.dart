import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/features/plan/providers/generate_week_controller.dart';
import 'package:glean/logging/logging.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

import '../../support/harness.dart';
import '../../support/session_backend.dart';

class _MockHttp extends Mock implements http.Client {}

class _CollectingSink implements PlatformLogSink {
  final List<String> lines = <String>[];

  @override
  Future<void> write({
    required String level,
    required String tag,
    required String message,
  }) async => lines.add('$level $message');
}

void main() {
  setUpAll(() => registerFallbackValue(Uri.parse('http://localhost/')));

  test('a failed Add to plan is written to the log with its cause', () async {
    final _MockHttp client = _MockHttp();
    final _CollectingSink sink = _CollectingSink();
    final AppTestHarness harness = AppTestHarness(
      httpClient: client,
      overrides: [
        gleanLoggerProvider.overrideWithValue(
          GleanLogger(file: RotatingLogFile.memory(), platform: sink),
        ),
      ],
    );
    addTearDown(harness.dispose);
    when(
      () => client.post(
        any(),
        headers: any(named: 'headers'),
        body: any(named: 'body'),
      ),
    ).thenAnswer(
      (_) async => http.Response(jsonEncode({'session_id': 'session-1'}), 202),
    );
    stubSessionPolls(
      client,
      result: {
        'suggestions': [
          {
            'recipe_id': null,
            'external_id': 'rec_a',
            'title': 'a',
            'reason': 'fit',
          },
        ],
      },
    );
    when(
      () => client.get(
        any(that: predicate<Uri>((uri) => uri.path.endsWith('/rec_a'))),
        headers: any(named: 'headers'),
      ),
    ).thenAnswer(
      (_) async => http.Response(
        jsonEncode({
          'external_id': 'rec_a',
          'title': 'a',
          'ingredients': <Object>[],
        }),
        200,
      ),
    );
    final notifier = harness.container.read(
      generateWeekControllerProvider.notifier,
    );
    await notifier.generate(
      weekStart: DateTime(2026, 10, 5),
      slots: 1,
      servings: 2,
    );
    await harness.failInsertsOn('meal_plan_entries', message: 'disk is full');

    final GenerateSaveOutcome outcome = await notifier.addToPlan();

    expect(outcome, isA<GenerateSaveFailed>());
    expect(sink.lines, anyElement(contains('disk is full')));
  });
}
