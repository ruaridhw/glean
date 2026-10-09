import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/auth_bypass.dart';
import 'package:glean/auth/auth_controller.dart';
import 'package:glean/auth/auth_mode.dart';
import 'package:glean/router/auth_state.dart';

void main() {
  group('bypassAuthSnapshot', () {
    test('is always active and resolves a stable identity', () {
      final AuthSessionSnapshot snapshot = bypassAuthSnapshot();

      expect(snapshot.status, AuthStatus.active);
      expect(snapshot.userId, kAuthBypassUserSub);
      expect(
        snapshot.tokens,
        isNull,
        reason:
            'bypass has no tokens at all — every backend LLM router still '
            'requires a valid one, so a bypass build cannot call one',
      );
    });

    test('honours a custom identity', () {
      final AuthSessionSnapshot snapshot = bypassAuthSnapshot(
        userId: 'ci-e2e-user-sub',
      );
      expect(snapshot.userId, 'ci-e2e-user-sub');
    });
  });

  group('assertAuthBypassUnreachable', () {
    test('throws for a production-looking API base URL', () {
      expect(
        () => assertAuthBypassUnreachable(
          'https://abc123.execute-api.eu-west-2.amazonaws.com',
        ),
        throwsA(isA<StateError>()),
      );
    });

    test('does not throw for local/loopback API base URLs', () {
      expect(
        () => assertAuthBypassUnreachable('http://localhost:8000'),
        returnsNormally,
      );
      expect(
        () => assertAuthBypassUnreachable('http://10.0.2.2:8000'),
        returnsNormally,
      );
    });
  });

  test('AC-AUTH-06: no file under lib/ other than auth_bypass.dart itself and '
      'the (orchestrator-owned) main_e2e.dart entrypoint imports/exports it — '
      'the structural guarantee that a production binary cannot reach it', () {
    final RegExp importOfBypass = RegExp(
      '''^\\s*(import|export)\\s+['"][^'"]*auth_bypass\\.dart['"]''',
      multiLine: true,
    );
    const Set<String> allowedReferrers = <String>{
      'lib/auth/auth_bypass.dart',
      'lib/main_e2e.dart',
    };

    final List<String> violations = <String>[];
    for (final FileSystemEntity entity in Directory(
      'lib',
    ).listSync(recursive: true)) {
      if (entity is! File || !entity.path.endsWith('.dart')) continue;
      final String normalizedPath = entity.path.replaceAll('\\', '/');
      if (allowedReferrers.any(normalizedPath.endsWith)) continue;

      final String source = entity.readAsStringSync();
      if (importOfBypass.hasMatch(source)) {
        violations.add(normalizedPath);
      }
    }

    expect(
      violations,
      isEmpty,
      reason:
          'These files reference auth_bypass.dart and would pull the test '
          'bypass into a production build: $violations',
    );
  });
}
