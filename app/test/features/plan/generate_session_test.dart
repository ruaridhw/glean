// Generate's create-then-poll flow, now a reviewed proposal (ADR 0019): the session is created once, polled
// every second to a terminal status, progress lines are kept as they arrive, and only Add to plan writes
// anything. Failures come out as the approved catalogue, never as a raw code.
import 'dart:async';
import 'dart:convert';

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
    'reason_kind': 'balance',
    'alternative': {
      'external_id': '${id}_alt',
      'title': 'Other $id',
      'reason': 'Also fits',
    },
  };

  http.Response session({
    required String status,
    Map<String, dynamic>? result,
    Map<String, dynamic>? error,
    int cursor = 1,
    List<String> progress = const <String>[],
  }) => http.Response(
    jsonEncode({
      'status': status,
      'progress': progress,
      'next_cursor': cursor,
      'result': result,
      'error': error,
    }),
    200,
  );

  http.Response queued() => session(status: 'queued', cursor: 0);
  http.Response running({List<String> progress = const <String>[]}) =>
      session(status: 'running', progress: progress);

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
      if (request.method == 'DELETE') {
        return http.Response('', 204);
      }
      if (request.method == 'POST') {
        return (create ?? () => http.Response('{"session_id":"s1"}', 202))();
      }
      if (request.url.path.startsWith('/meal-plan/sessions/')) {
        if (polled < polls.length) return polls[polled++]();
        polled++;
        return running();
      }
      // Recipe detail, fetched when Add to plan resolves the picks.
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

  test(
    'create, poll, then a done result is a proposal until Add to plan',
    () async {
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
            () => running(progress: ['Checking the week']),
            () => session(
              status: 'done',
              result: {
                'week_summary': 'Four quick dinners, one fish.',
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

      final GenerateProposalState state = h.container.read(
        generateWeekControllerProvider,
      );
      expect(state.phase, GenerateProposalPhase.proposal);
      expect(state.result!.suggestions, hasLength(2));
      expect(state.result!.weekSummary, 'Four quick dinners, one fish.');
      expect(state.progress, ['Checking the week']);
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
      expect(
        await h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
        isEmpty,
        reason: 'nothing is saved before Add to plan',
      );

      final GenerateSaveOutcome outcome = await h.container
          .read(generateWeekControllerProvider.notifier)
          .addToPlan();

      expect(outcome, isA<GenerateSaveSaved>());
      expect((outcome as GenerateSaveSaved).inserted, 2);
      final entries = await h.container
          .read(planRepositoryProvider)
          .getWeek(userId: h.userId, weekStart: week);
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
    },
  );

  test('progress lines accumulate across polls, newest last', () async {
    final clock = FakeClock();
    final h = harnessWith(
      clock,
      backend(
        polls: [
          () => running(progress: ['Checking what you cooked recently']),
          () => running(progress: ['Picking your meals']),
          () => running(progress: ['Checking the week']),
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

    expect(h.container.read(generateWeekControllerProvider).progress, [
      'Checking what you cooked recently',
      'Picking your meals',
      'Checking the week',
    ]);
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

    expect(polls, 1);
    expect(
      clock.now,
      DateTime(2026, 10, 5, 9),
      reason: 'a terminal poll never waits again',
    );
  });

  test('each poll sends the cursor the previous response gave', () async {
    final clock = FakeClock();
    final afters = <String?>[];
    final h = harnessWith(
      clock,
      backend(
        capture: (request) {
          if (request.url.path.startsWith('/meal-plan/sessions/')) {
            afters.add(request.url.queryParameters['after']);
          }
        },
        polls: [
          () => session(status: 'queued', cursor: 3),
          () => session(
            status: 'done',
            cursor: 7,
            result: {'suggestions': <Object?>[]},
          ),
        ],
      ),
    );
    addTearDown(h.dispose);

    await h.container
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: week, slots: 1, servings: 1);

    expect(
      afters,
      [null, '3'],
      reason:
          'the first poll asks from 0, the next from the next_cursor it was given',
    );
  });

  test(
    'waiting_for_user keeps the working state: the question is V11',
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
            () =>
                session(status: 'waiting_for_user', progress: ['One question']),
            () => running(progress: ['Picking your meals']),
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

      expect(polls, 3, reason: 'a question hint does not stop the poll loop');
      expect(
        h.container.read(generateWeekControllerProvider).phase,
        GenerateProposalPhase.proposal,
      );
    },
  );

  test('a 503 on create, because the queue would not take the run, is the '
      'generic copy with Retry', () async {
    final clock = FakeClock();
    var polls = 0;
    final h = harnessWith(
      clock,
      backend(
        create: () => http.Response('{"detail":"Could not queue"}', 503),
        capture: (request) {
          if (request.url.path.startsWith('/meal-plan/sessions/')) polls++;
        },
        polls: [running],
      ),
    );
    addTearDown(h.dispose);

    await h.container
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: week, slots: 2, servings: 2);

    final GenerateProposalState state = h.container.read(
      generateWeekControllerProvider,
    );
    expect(state.phase, GenerateProposalPhase.failed);
    expect(state.failure!.kind, GenerateFailureKind.unknown);
    expect(state.failure!.message, 'Something went wrong planning your week.');
    expect(state.failure!.actionLabel, 'Retry');
    expect(
      polls,
      0,
      reason: 'a run that never got a session has nothing to poll',
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

        final GenerateProposalState state = h.container.read(
          generateWeekControllerProvider,
        );
        expect(state.phase, GenerateProposalPhase.failed);
        expect(state.failure!.kind, kind);
        expect(state.failure!.message, message);
        expect(state.failure!.actionLabel, action);
        expect(
          state.failure!.message,
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

    final GenerateFailure failure = h.container
        .read(generateWeekControllerProvider)
        .failure!;
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

    final GenerateFailure failure = h.container
        .read(generateWeekControllerProvider)
        .failure!;
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
      h.container.read(generateWeekControllerProvider).failure!.message,
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
        h.container.read(generateWeekControllerProvider).phase,
        GenerateProposalPhase.proposal,
        reason: 'three bad polls do not fail a run that then succeeds',
      );
      expect(polls, 4);
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

    final GenerateProposalState state = h.container.read(
      generateWeekControllerProvider,
    );
    expect(state.phase, GenerateProposalPhase.failed);
    expect(state.failure!.kind, GenerateFailureKind.stalled);
    expect(state.failure!.message, 'Planning stopped responding.');
    expect(state.failure!.actionLabel, 'Retry');
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
        h.container.read(generateWeekControllerProvider).failure!.kind,
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

    final GenerateProposalState state = h.container.read(
      generateWeekControllerProvider,
    );
    expect(state.failure!.kind, GenerateFailureKind.unknown);
    expect(state.failure!.message, 'Something went wrong planning your week.');
    expect(polls, 1, reason: 'no wait rescues a session that is gone');
  });

  test(
    'a done session without a plan is a failure, not an empty week',
    () async {
      final clock = FakeClock();
      final h = harnessWith(
        clock,
        backend(polls: [() => session(status: 'done')]),
      );
      addTearDown(h.dispose);

      await h.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 1, servings: 1);

      expect(
        h.container.read(generateWeekControllerProvider).failure!.kind,
        GenerateFailureKind.unknown,
      );
    },
  );

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
      h.container.read(generateWeekControllerProvider).failure!.actionLabel,
      'Retry',
    );
    await controller.retry();

    expect(opened, 2);
    expect(slots, [3, 3]);
  });

  test(
    'Cancel DELETEs the session, discards the review and adds nothing',
    () async {
      final clock = FakeClock();
      final requests = <http.Request>[];
      final pendingPoll = Completer<http.Response>();
      final h = harnessWith(
        clock,
        MockClient((request) async {
          requests.add(request);
          if (request.method == 'DELETE') return http.Response('', 204);
          if (request.method == 'POST') {
            return http.Response('{"session_id":"s1"}', 202);
          }
          return pendingPoll.future;
        }),
      );
      addTearDown(h.dispose);

      final controller = h.container.read(
        generateWeekControllerProvider.notifier,
      );
      final Future<void> run = controller.generate(
        weekStart: week,
        slots: 1,
        servings: 1,
      );
      await pumpUntilCondition(
        () =>
            h.container.read(generateWeekControllerProvider).sessionId == 's1',
      );

      await controller.cancel();
      pendingPoll.complete(running());
      await run;

      final Iterable<http.Request> deletes = requests.where(
        (request) => request.method == 'DELETE',
      );
      expect(deletes, hasLength(1));
      expect(deletes.single.url.path, '/meal-plan/sessions/s1');
      expect(
        h.container.read(generateWeekControllerProvider).phase,
        GenerateProposalPhase.idle,
      );
      expect(
        await h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
        isEmpty,
      );
    },
  );

  test(
    'a cancelled status from the server is terminal and writes nothing',
    () async {
      final clock = FakeClock();
      final h = harnessWith(
        clock,
        backend(polls: [() => session(status: 'cancelled')]),
      );
      addTearDown(h.dispose);

      await h.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 1, servings: 1);

      expect(
        h.container.read(generateWeekControllerProvider).phase,
        GenerateProposalPhase.idle,
      );
    },
  );
}

/// Waits for a controller condition without real delays; the fake clock and the in-memory database resolve on
/// the event loop, so yielding is enough.
Future<void> pumpUntilCondition(bool Function() condition) async {
  for (int i = 0; i < 1000; i++) {
    if (condition()) return;
    await Future<void>.delayed(Duration.zero);
  }
  throw StateError('condition never became true');
}
