// Test doubles for Generate's two-request session flow (`POST /meal-plan/sessions`, then
// `GET /meal-plan/sessions/{id}`). Not a suite itself.
//
// A suite that only cares what Generate *writes* should not repeat the create-then-poll dance, so both helpers
// take the old single-shot body (a JSON object with `suggestions`) and serve it as a session that is already
// `done` on its first poll.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart' show predicate;
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mocktail/mocktail.dart';

/// The body of a session that finished with [result] on its first poll.
http.Response sessionDone(Map<String, dynamic> result) => http.Response(
  jsonEncode({
    'status': 'done',
    'progress': <String>[],
    'next_cursor': 1,
    'session_id': 'session-1',
    'updated_at': '2026-10-23T09:13:29.669974Z',
    'result': result,
    'error': null,
  }),
  200,
);

/// Wraps a [MockClient] suite's own [handler] with the session routes.
///
/// A `POST /meal-plan/sessions` reaches [handler] as the old `POST /meal-plan` did: a 200 from it becomes a
/// session that reports `done` with that body, and any other status (429, 422) is returned as the create call's
/// own failure, which is exactly how the backend answers those. Every other request is passed through, so the
/// recipe-detail GETs in these suites keep working.
http.Client sessionRoutes(
  Future<http.Response> Function(http.Request request) handler,
) {
  final Map<String, http.Response> finished = <String, http.Response>{};
  var opened = 0;
  return MockClient((http.Request request) async {
    final List<String> path = request.url.pathSegments;
    final bool sessions =
        path.length >= 2 && path[0] == 'meal-plan' && path[1] == 'sessions';
    if (sessions && request.method == 'POST' && path.length == 2) {
      final http.Response generated = await handler(request);
      if (generated.statusCode != 200) return generated;
      final String id = 'session-${++opened}';
      finished[id] = generated;
      return http.Response(jsonEncode({'session_id': id}), 202);
    }
    if (sessions && request.method == 'GET' && path.length == 3) {
      final http.Response? result = finished.remove(path[2]);
      if (result == null) {
        return http.Response('{"detail":"Unknown session"}', 404);
      }
      return sessionDone(jsonDecode(result.body) as Map<String, dynamic>);
    }
    return handler(request);
  });
}

/// The mocktail equivalent of [sessionRoutes]: stubs the create on [client] to hand back [sessionId], and that
/// session's polls to report `done` with [result]. Stub the create yourself when the test also inspects the
/// request body — a later stub wins.
void stubSession(
  http.Client client, {
  required Map<String, dynamic> result,
  String sessionId = 'session-1',
}) {
  when(
    () => client.post(
      any(),
      headers: any(named: 'headers'),
      body: any(named: 'body'),
    ),
  ).thenAnswer(
    (_) async => http.Response(jsonEncode({'session_id': sessionId}), 202),
  );
  stubSessionPolls(client, result: result, sessionId: sessionId);
}

/// Just the polling half of [stubSession], for a test that supplies its own create stub.
void stubSessionPolls(
  http.Client client, {
  required Map<String, dynamic> result,
  String sessionId = 'session-1',
}) {
  when(
    () => client.get(
      any(
        that: predicate<Uri>(
          (uri) => uri.path == '/meal-plan/sessions/$sessionId',
        ),
      ),
      headers: any(named: 'headers'),
    ),
  ).thenAnswer((_) async => sessionDone(result));
}
