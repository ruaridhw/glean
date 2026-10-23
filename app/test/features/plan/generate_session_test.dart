// Generate's create-then-poll flow: the session is created once, polled every second to a terminal status, and
// only a `done` result is ever written. Failures come out as the approved catalogue, never as a raw code.
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/features/plan/generate_failure.dart';
import 'package:glean/features/plan/providers/generate_week_controller.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../support/harness.dart';

/// A poller whose sleep moves a fake clock instead of waiting, so a test runs the 1 s cadence and the 5 min cap in
/// no time and can still assert where the clock ended up.
class FakeClock {
  DateTime now = DateTime(2026, 10, 5, 9);

  late final GenerateSessionPoller poller = GenerateSessionPoller(
    sleep: (Duration duration) async => now = now.add(duration),
    now: () => now,
  );
}

void main() {
  final week = DateTime(2026, 10, 5);

  Map<String, dynamic> pick(String id) => {
    'recipe_id': null,
    'external_id': id,
    'title': 'Corpus $id',
    'reason': 'fit',
  };

  http.Response session({
    required String status,
    Map<String, dynamic>? result,
    Map<String, dynamic>? error,
    int cursor = 1,
  }) => http.Response(
    jsonEncode({
      'status': status,
      'progress': <String>[],
      'cursor': cursor,
      'result': result,
      'error': error,
    }),
    200,
  );

  http.Response queued() => session(status: 'queued', cursor: 0);
  http.Response running() => session(status: 'running');

  /// A fake backend: one create, then the scripted [polls] in order. Past the script every poll stays `running`,
  /// so a loop that should have stopped runs to the cap and fails the test loudly instead of hanging it.
  http.Client backend({
    required List<http.Response Function()> polls,
    http.Response Function()? create,
    void Function(http.Request request)? capture,
  }) {
    var polled = 0;
    return MockClient((http.Request request) async {
      capture?.call(request);
      if (request.method == 'POST') {
        return (create ?? () => http.Response('{"session_id":"s1"}', 202))();
      }
      if (request.url.path.startsWith('/meal-plan/sessions/')) {
        if (polled < polls.length) return polls[polled++]();
        polled++;
        return running();
      }
      // Recipe detail, fetched while the picks are resolved.
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

  AppTestHarness harnessWith(FakeClock clock, http.Client client) =>
      AppTestHarness(
        httpClient: client,
        overrides: [
          generateSessionPollerProvider.overrideWithValue(clock.poller),
        ],
      );

  test('create, poll, then a done result commits the week as the sync call '
      'did', () async {
    final clock = FakeClock();
    final DateTime startedAt = clock.now;
    var polls = 0;
    http.Request? created;
    final h = harnessWith(
      clock,
      backend(
        capture: (request) {
          if (request.method == 'POST') created = request;
          if (request.url.path.startsWith('/meal-plan/sessions/')) polls++;
        },
        polls: [
          queued,
          running,
          () => session(
            status: 'done',
            result: {
              'suggestions': [pick('rec_a'), pick('rec_b')],
            },
          ),
        ],
      ),
    );
    addTearDown(h.dispose);

    await h.container
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: week, slots: 2, servings: 2);

    expect(
      h.container.read(generateWeekControllerProvider).hasError,
      isFalse,
      reason: 'a done session is not a failure',
    );
    expect(created!.url.path, '/meal-plan/sessions');
    final sent = jsonDecode(created!.body) as Map<String, dynamic>;
    expect(sent['meals_per_week'], 2);
    expect(sent['source'], 'corpus');
    expect(polls, 3, reason: 'queued and running are polled through');
    expect(
      clock.now.difference(startedAt),
      const Duration(seconds: 2),
      reason: 'one interval between each of the three polls',
    );
    final entries = await h.container
        .read(planRepositoryProvider)
        .getWeek(userId: h.userId, weekStart: week);
    expect(entries, hasLength(2));
    expect(entries.map((entry) => entry.recipeTitle), [
      'Corpus rec_a',
      'Corpus rec_b',
    ]);
    expect(
      await h.container
          .read(shoppingRepositoryProvider)
          .watchAll(h.userId)
          .first,
      isNotEmpty,
      reason: 'the same top-up gaps are added as before',
    );
  });

  test('polling stops at a terminal status: no wait, no extra poll', () async {
    final clock = FakeClock();
    var polls = 0;
    final h = harnessWith(
      clock,
      backend(
        capture: (request) {
          if (request.url.path.startsWith('/meal-plan/sessions/')) polls++;
        },
        polls: [
          () => session(status: 'done', result: {'suggestions': <Object?>[]}),
        ],
      ),
    );
    addTearDown(h.dispose);

    await h.container
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: week, slots: 1, servings: 1);
    await h.container.pump();

    expect(polls, 1);
    expect(
      clock.now,
      DateTime(2026, 10, 5, 9),
      reason: 'a terminal poll never waits again',
    );
  });

  for (final (
        String code,
        GenerateFailureKind kind,
        String message,
        String? action,
      )
      in <(String, GenerateFailureKind, String, String?)>[
        (
          'no_eligible_recipes',
          GenerateFailureKind.noEligibleRecipes,
          'No recipes fit your diet and time limit.',
          'Open Settings',
        ),
        (
          'model_error',
          GenerateFailureKind.modelError,
          'Something went wrong planning your week.',
          'Retry',
        ),
        (
          'worker_failed',
          GenerateFailureKind.workerFailed,
          'Something went wrong planning your week.',
          'Retry',
        ),
        (
          'invalid_request',
          GenerateFailureKind.invalidRequest,
          "Glean couldn't read this request.",
          'Report',
        ),
        (
          'a_code_from_the_future',
          GenerateFailureKind.unknown,
          'Something went wrong planning your week.',
          'Retry',
        ),
      ]) {
    test(
      'a failed session with $code shows the catalogue copy and action',
      () async {
        final clock = FakeClock();
        final h = harnessWith(
          clock,
          backend(
            polls: [
              () => session(
                status: 'failed',
                cursor: 2,
                error: {'code': code, 'retry_after_minutes': null},
              ),
            ],
          ),
        );
        addTearDown(h.dispose);

        await h.container
            .read(generateWeekControllerProvider.notifier)
            .generate(weekStart: week, slots: 2, servings: 2);

        final GenerateFailure failure =
            h.container.read(generateWeekControllerProvider).error!
                as GenerateFailure;
        expect(failure.kind, kind);
        expect(failure.message, message);
        expect(failure.actionLabel, action);
        expect(
          failure.message,
          isNot(contains(code)),
          reason: 'internal codes never reach the user',
        );
        expect(
          await h.container
              .read(planRepositoryProvider)
              .getWeek(userId: h.userId, weekStart: week),
          isEmpty,
          reason: 'a failed session writes nothing',
        );
      },
    );
  }

  test('rate_limited names the wait the session reports', () async {
    final clock = FakeClock();
    final h = harnessWith(
      clock,
      backend(
        polls: [
          () => session(
            status: 'failed',
            error: {'code': 'rate_limited', 'retry_after_minutes': 12},
          ),
        ],
      ),
    );
    addTearDown(h.dispose);

    await h.container
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: week, slots: 2, servings: 2);

    final GenerateFailure failure =
        h.container.read(generateWeekControllerProvider).error!
            as GenerateFailure;
    expect(failure.kind, GenerateFailureKind.rateLimited);
    expect(
      failure.message,
      "You've used too many AI credits. Try again in 12 minutes.",
    );
    expect(
      failure.actionLabel,
      isNull,
      reason: 'retrying now fails the same way',
    );
  });

  test('a 429 on create is rate_limited, with the hourly window as the '
      'wait', () async {
    final clock = FakeClock();
    final h = harnessWith(
      clock,
      backend(
        create: () =>
            http.Response('{"detail":"AI request limit reached"}', 429),
        polls: const [],
      ),
    );
    addTearDown(h.dispose);

    await h.container
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: week, slots: 2, servings: 2);

    final GenerateFailure failure =
        h.container.read(generateWeekControllerProvider).error!
            as GenerateFailure;
    expect(failure.kind, GenerateFailureKind.rateLimited);
    expect(
      failure.message,
      "You've used too many AI credits. Try again in 60 minutes.",
    );
  });

  test('a 429 with Retry-After uses the server figure', () async {
    final clock = FakeClock();
    final h = harnessWith(
      clock,
      backend(
        create: () => http.Response(
          '{"detail":"AI request limit reached"}',
          429,
          headers: {'retry-after': '120'},
        ),
        polls: const [],
      ),
    );
    addTearDown(h.dispose);

    await h.container
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: week, slots: 2, servings: 2);

    expect(
      (h.container.read(generateWeekControllerProvider).error!
              as GenerateFailure)
          .message,
      "You've used too many AI credits. Try again in 2 minutes.",
    );
  });

  test(
    'transient poll failures keep polling until the session finishes',
    () async {
      final clock = FakeClock();
      var polls = 0;
      final h = harnessWith(
        clock,
        backend(
          capture: (request) {
            if (request.url.path.startsWith('/meal-plan/sessions/')) polls++;
          },
          polls: [
            () => http.Response('{"detail":"boom"}', 500),
            () => throw http.ClientException('connection reset'),
            () => http.Response('not json', 200),
            () => session(
              status: 'done',
              result: {
                'suggestions': [pick('rec_a')],
              },
            ),
          ],
        ),
      );
      addTearDown(h.dispose);

      await h.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 1, servings: 1);

      expect(
        h.container.read(generateWeekControllerProvider).hasError,
        isFalse,
        reason: 'three bad polls do not fail a run that then succeeds',
      );
      expect(polls, 4);
      expect(
        await h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
        hasLength(1),
      );
    },
  );

  test('the 5 minute cap ends a run that never reports a status as '
      'stalled', () async {
    final clock = FakeClock();
    final DateTime startedAt = clock.now;
    var polls = 0;
    final h = harnessWith(
      clock,
      backend(
        capture: (request) {
          if (request.url.path.startsWith('/meal-plan/sessions/')) polls++;
        },
        polls: [running],
      ),
    );
    addTearDown(h.dispose);

    await h.container
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: week, slots: 1, servings: 1);

    final GenerateFailure failure =
        h.container.read(generateWeekControllerProvider).error!
            as GenerateFailure;
    expect(failure.kind, GenerateFailureKind.stalled);
    expect(failure.message, 'Planning stopped responding.');
    expect(failure.actionLabel, 'Retry');
    expect(clock.now, startedAt.add(const Duration(minutes: 5)));
    expect(polls, 300, reason: 'one poll per second for the full cap');
  });

  test(
    'unending transient failures end the run as stalled, not as a code',
    () async {
      final clock = FakeClock();
      final h = harnessWith(
        clock,
        backend(polls: [() => http.Response('{"detail":"boom"}', 503)]),
      );
      addTearDown(h.dispose);

      await h.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 1, servings: 1);

      expect(
        (h.container.read(generateWeekControllerProvider).error!
                as GenerateFailure)
            .kind,
        GenerateFailureKind.stalled,
      );
    },
  );

  test('a session the server no longer has stops polling and reports '
      'generically', () async {
    final clock = FakeClock();
    var polls = 0;
    final h = harnessWith(
      clock,
      MockClient((request) async {
        if (request.method == 'POST') {
          return http.Response('{"session_id":"s1"}', 202);
        }
        polls++;
        return http.Response('{"detail":"Unknown session"}', 404);
      }),
    );
    addTearDown(h.dispose);

    await h.container
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: week, slots: 1, servings: 1);

    final GenerateFailure failure =
        h.container.read(generateWeekControllerProvider).error!
            as GenerateFailure;
    expect(failure.kind, GenerateFailureKind.unknown);
    expect(failure.message, 'Something went wrong planning your week.');
    expect(polls, 1, reason: 'no wait rescues a session that is gone');
  });

  test(
    'each attempt opens its own session: nothing about it is kept',
    () async {
      final clock = FakeClock();
      final polled = <String>[];
      var opened = 0;
      final h = harnessWith(
        clock,
        MockClient((request) async {
          if (request.method == 'POST') {
            return http.Response(
              jsonEncode({'session_id': 's${++opened}'}),
              202,
            );
          }
          polled.add(request.url.pathSegments.last);
          return session(status: 'done', result: {'suggestions': <Object?>[]});
        }),
      );
      addTearDown(h.dispose);

      final controller = h.container.read(
        generateWeekControllerProvider.notifier,
      );
      await controller.generate(weekStart: week, slots: 1, servings: 1);
      await controller.generate(weekStart: week, slots: 1, servings: 1);

      expect(opened, 2);
      expect(polled, [
        's1',
        's2',
      ], reason: 'the second run polls its own session');
    },
  );

  test('Retry repeats the failed attempt with the same slots', () async {
    final clock = FakeClock();
    final slots = <int>[];
    var opened = 0;
    final h = harnessWith(
      clock,
      MockClient((request) async {
        if (request.method == 'POST') {
          opened++;
          slots.add(
            (jsonDecode(request.body) as Map<String, dynamic>)['meals_per_week']
                as int,
          );
          return http.Response(jsonEncode({'session_id': 's$opened'}), 202);
        }
        return session(
          status: 'failed',
          error: {'code': 'model_error', 'retry_after_minutes': null},
        );
      }),
    );
    addTearDown(h.dispose);

    final controller = h.container.read(
      generateWeekControllerProvider.notifier,
    );
    await controller.generate(weekStart: week, slots: 3, servings: 2);
    expect(
      (h.container.read(generateWeekControllerProvider).error!
              as GenerateFailure)
          .actionLabel,
      'Retry',
    );
    await controller.retry();

    expect(opened, 2);
    expect(slots, [3, 3]);
  });
}
