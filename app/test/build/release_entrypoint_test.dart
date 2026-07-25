/// AC-AUTH-07's build-level guard.
///
/// `test/auth/auth_bypass_test.dart` already proves the bypass is
/// unreachable from `lib/main.dart`'s *Dart import graph*. That is
/// necessary but not sufficient: nothing stops a build script from pointing
/// its `-t`/`--target` flag at `lib/main_e2e.dart` regardless of what the
/// Dart source imports — the RN equivalent of that mistake was exactly the
/// deleted `tests/auth/ci-auth-bypass.test.ts` (§10), which regexed a CI
/// YAML whose env vars have since disappeared entirely.
///
/// This test complements the source-graph proof by scanning the actual
/// build/release *configuration* — the Fastlane lanes that produce what
/// ships to TestFlight/Play, and every GitHub Actions workflow — for the one
/// dangerous pattern: a release-shaped build command naming
/// `main_e2e.dart`. It does not re-check the source graph (that stays
/// `auth_bypass_test.dart`'s job), and it does not merely restate CI YAML
/// like the deleted RN test — a Fastfile/workflow is the actual build
/// configuration that runs, not a description of one.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Matches `main_e2e` (as in `lib/main_e2e.dart`) anywhere in a file's text,
/// case-sensitively — the same literal name `auth_bypass_test.dart` treats
/// as the one legitimate entrypoint for the bypass.
final RegExp _mainE2eMention = RegExp('main_e2e');

/// A `flutter build` (or `flutter run --release`/`gradlew assemble*`-style)
/// invocation shaped to produce a shippable artifact, as opposed to
/// `flutter test`/`flutter drive`, which run the integration suite without
/// producing anything release-shaped.
final RegExp _releaseBuildInvocation = RegExp(
  r'flutter\s+build|gradlew\s+(assemble|bundle)',
);

void main() {
  group('release lanes never target the e2e entrypoint', () {
    for (final String fastfilePath in <String>[
      'ios/fastlane/Fastfile',
      'android/fastlane/Fastfile',
    ]) {
      test('$fastfilePath builds lib/main.dart, never main_e2e', () {
        final File file = File(fastfilePath);
        expect(
          file.existsSync(),
          isTrue,
          reason:
              '$fastfilePath is missing — AC-CI-04 requires a release lane '
              'for both platforms',
        );

        final String contents = file.readAsStringSync();
        expect(
          contents,
          contains('lib/main.dart'),
          reason:
              '$fastfilePath must explicitly target lib/main.dart so the '
              'shipped entrypoint is never left to whatever the default '
              'happens to be',
        );

        // Explanatory comments (like this file's own header, and this
        // test's) are allowed to *say* "main_e2e" — what must never exist
        // is that name on the same line as the actual build invocation this
        // lane runs.
        final List<String> violations = <String>[
          for (final String line in contents.split('\n'))
            if (_releaseBuildInvocation.hasMatch(line) &&
                _mainE2eMention.hasMatch(line))
              line.trim(),
        ];
        expect(
          violations,
          isEmpty,
          reason:
              '$fastfilePath has a build invocation targeting main_e2e — '
              'exactly what AC-AUTH-07 forbids: $violations',
        );
      });
    }

    test(
      'no GitHub Actions workflow runs a release build against main_e2e',
      () {
        final Directory workflows = Directory('../.github/workflows');
        expect(
          workflows.existsSync(),
          isTrue,
          reason: 'expected .github/workflows to exist at the repo root',
        );

        final List<String> violations = <String>[];
        for (final FileSystemEntity entity in workflows.listSync()) {
          if (entity is! File) continue;
          if (!entity.path.endsWith('.yml') && !entity.path.endsWith('.yaml')) {
            continue;
          }

          final String contents = entity.readAsStringSync();
          // A release-shaped build step (`flutter build`/`gradlew
          // assemble*`) is fine on its own, and `main_e2e` on its own is
          // fine (the integration jobs legitimately run tests against it).
          // What must never happen is both on the *same line* — a build
          // step whose target is the bypass entrypoint.
          for (final String line in contents.split('\n')) {
            if (_releaseBuildInvocation.hasMatch(line) &&
                _mainE2eMention.hasMatch(line)) {
              violations.add('${entity.path}: ${line.trim()}');
            }
          }
        }

        expect(
          violations,
          isEmpty,
          reason:
              'these workflow lines build a release artifact from the e2e '
              'entrypoint: $violations',
        );
      },
    );

    test('the push-triggered CI workflow never mentions main_e2e at all', () {
      final File ciWorkflow = File('../.github/workflows/flutter-ci.yml');
      expect(ciWorkflow.existsSync(), isTrue);
      expect(
        _mainE2eMention.hasMatch(ciWorkflow.readAsStringSync()),
        isFalse,
        reason:
            'flutter-ci.yml runs on every push (AC-CI-01) and must have '
            'no path to the bypass entrypoint at all — not even to run '
            'tests against it',
      );
    });

    test('the workflow_dispatch integration workflow only *tests* main_e2e, '
        "never builds a release from it (that's the release lanes' job)", () {
      final File integrationWorkflow = File(
        '../.github/workflows/flutter-integration.yml',
      );
      expect(integrationWorkflow.existsSync(), isTrue);

      final String contents = integrationWorkflow.readAsStringSync();
      expect(
        _mainE2eMention.hasMatch(contents),
        isTrue,
        reason:
            'the integration jobs are expected to run the integration '
            'suite against main_e2e.dart — if this ever stops being true, '
            'update this test rather than deleting it',
      );
      for (final String line in contents.split('\n')) {
        expect(
          _releaseBuildInvocation.hasMatch(line) &&
              _mainE2eMention.hasMatch(line),
          isFalse,
          reason: 'release-shaped build line targets main_e2e: $line',
        );
      }
    });
  });
}
