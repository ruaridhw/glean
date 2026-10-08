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
/// build/release *configuration* — the iOS Fastlane lane, the Codemagic
/// Android workflow, and every GitHub Actions workflow — for the one
/// dangerous pattern: a release-shaped build command naming
/// `main_e2e.dart`. It does not re-check the source graph (that stays
/// `auth_bypass_test.dart`'s job), and it does not merely restate CI YAML
/// like the deleted RN test — a Fastfile/workflow is the actual build
/// configuration that runs, not a description of one.
///
/// ## Why this scans *logical* lines, not raw source lines
///
/// A previous version of this test matched `flutter build`/`gradlew
/// assemble*` and `main_e2e` only when both appeared on the same **raw**
/// line. The Fastfiles built via two string literals concatenated across
/// two physical lines with a trailing `\` continuation:
///
/// ```ruby
/// sh(
///   'cd ../.. && flutter build ipa --release ' \
///   "-t lib/main.dart --build-number=#{build_number}",
/// )
/// ```
///
/// `flutter build` lives on the first line, the `-t` target on the second.
/// Editing *only* the second line to `-t lib/main_e2e.dart` produced a
/// shippable release build of the auth-bypass entrypoint while the
/// raw-line guard kept passing 5/5 — a false negative, since fixed. Line
/// formatting must not be able to defeat a security guard, so this version
/// first joins any line ending in a backslash continuation (Ruby's
/// statement continuation and Bash's line continuation both use the same
/// character) onto the next line before applying any check, and — stronger
/// still — extracts the actual resolved `-t`/`--target` value each Fastlane
/// lane passes and asserts it is exactly `lib/main.dart`, rather than
/// merely asserting the absence of a substring.
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

/// Extracts the value passed to a `-t`/`--target` flag, tolerating the
/// surrounding Ruby/shell quoting this repo's build scripts use
/// (`-t lib/main.dart`, `--target=lib/main.dart`, `-t "lib/main.dart"`, …).
final RegExp _targetFlag = RegExp(
  r'''(?:-t|--target)[= ]+["']?([\w./]+\.dart)["']?''',
);

/// Joins backslash-continued lines into one logical line so that a build
/// invocation split across physical lines — Ruby's `sh('a ' \` + `'b')`
/// pattern used by the iOS Fastfile, or an equally idiomatic multi-line shell
/// command in a workflow's `run: |` block — is scanned as the single
/// statement it actually is, rather than as independent lines a naive
/// per-line regex can be defeated by.
///
/// Full-line comments (Ruby `#`/YAML `#`, once trimmed) are dropped first:
/// this is prose about builds ("`flutter build ipa` names the output
/// after…"), not a build invocation, and joining across a comment boundary
/// would otherwise manufacture a fake "statement" out of unrelated code.
///
/// This is a text heuristic, not a Ruby/YAML/Bash parser — it only needs to
/// hold for the build-configuration files this test reads, not arbitrary
/// source. A line continues onto the next when, after trimming trailing
/// whitespace, it ends in exactly one `\`.
List<String> _logicalLines(String contents) {
  final List<String> rawLines = contents.split('\n');
  final List<String> logical = <String>[];
  final StringBuffer pending = StringBuffer();

  for (final String rawLine in rawLines) {
    if (rawLine.trim().startsWith('#')) {
      continue;
    }
    final String trimmedEnd = rawLine.replaceFirst(RegExp(r'\s+$'), '');
    final bool continues =
        trimmedEnd.endsWith(r'\') && !trimmedEnd.endsWith(r'\\');
    pending.write(
      continues ? trimmedEnd.substring(0, trimmedEnd.length - 1) : rawLine,
    );
    if (continues) {
      pending.write(' ');
    } else {
      logical.add(pending.toString());
      pending.clear();
    }
  }
  if (pending.isNotEmpty) {
    logical.add(pending.toString());
  }
  return logical;
}

/// Extracts the argument text passed to the Fastfile's single `sh(...)`
/// call — the actual shell command Fastlane executes — as opposed to any
/// other Ruby string in the file (e.g. an error message that happens to
/// *mention* `flutter build` in prose). This is what "resolved target" means in
/// practice: the one piece of text that is actually handed to a shell,
/// scoped precisely so prose elsewhere can't be mistaken for it.
///
/// Follows this repo's Fastfile convention of `sh(` opening a call whose
/// closing `)` sits alone on its own line.
String? _shInvocationBody(String contents) {
  final List<String> rawLines = contents.split('\n');
  final int start = rawLines.indexWhere(
    // A comment mentioning the call (e.g. "the `sh(...)` call below") also
    // contains the substring `sh(` — skip comment lines so that prose
    // about the invocation can't be mistaken for the invocation itself.
    (String line) => !line.trim().startsWith('#') && line.contains('sh('),
  );
  if (start == -1) {
    return null;
  }
  final int end = rawLines.indexWhere(
    (String line) => line.trim() == ')',
    start + 1,
  );
  if (end == -1) {
    return null;
  }
  return rawLines.sublist(start + 1, end).join('\n');
}

/// Finds every logical line that both looks like a release build invocation
/// and mentions `main_e2e` — the one pattern that must never exist, however
/// the source happens to be wrapped across physical lines.
List<String> _sameStatementViolations(String contents) => <String>[
  for (final String line in _logicalLines(contents))
    if (_releaseBuildInvocation.hasMatch(line) &&
        _mainE2eMention.hasMatch(line))
      line.trim(),
];

void main() {
  group('release lanes never target the e2e entrypoint', () {
    for (final String fastfilePath in <String>['ios/fastlane/Fastfile']) {
      test('$fastfilePath resolves its build target to lib/main.dart', () {
        final File file = File(fastfilePath);
        expect(
          file.existsSync(),
          isTrue,
          reason: '$fastfilePath is missing — iOS releases need it',
        );

        final String contents = file.readAsStringSync();

        // Scope to the actual `sh(...)` call — the one piece of text
        // Fastlane hands to a shell — not any other string in the file.
        final String? shBody = _shInvocationBody(contents);
        expect(
          shBody,
          isNotNull,
          reason:
              '$fastfilePath has no `sh(...)` call shaped as this repo\'s '
              'Fastfiles use — expected one opening `sh(` and a `)` alone '
              'on its own line',
        );

        // Join continuations *within the sh(...) body only* — after
        // joining, this is the single logical statement Fastlane executes,
        // however many physical lines/string literals it was wrapped
        // across (the Fastfile concatenates two string literals with a
        // trailing `\` continuation).
        final List<String> joined = _logicalLines(
          shBody!,
        ).where((String line) => line.trim().isNotEmpty).toList();
        expect(
          joined,
          hasLength(1),
          reason:
              'expected the sh(...) body in $fastfilePath to join into one '
              'logical statement, got: $joined',
        );
        final String buildStatement = joined.single;
        expect(
          _releaseBuildInvocation.hasMatch(buildStatement),
          isTrue,
          reason:
              '$fastfilePath\'s sh(...) call is not a release build '
              'invocation: $buildStatement',
        );

        // Assert on the *resolved* target rather than merely on the
        // absence of a substring — this is what makes the assertion
        // immune to line formatting: however the statement is wrapped,
        // once joined there is exactly one target value, and it must be
        // lib/main.dart.
        final RegExpMatch? targetMatch = _targetFlag.firstMatch(buildStatement);
        expect(
          targetMatch,
          isNotNull,
          reason:
              '$fastfilePath\'s release build invocation has no '
              '-t/--target flag at all: $buildStatement',
        );
        expect(
          targetMatch!.group(1),
          'lib/main.dart',
          reason:
              '$fastfilePath\'s release build must target lib/main.dart — '
              'found target "${targetMatch.group(1)}" in: $buildStatement',
        );

        // Defence in depth, and a clearer failure message than the target
        // check alone would give if main_e2e shows up somewhere in the
        // statement other than the target flag itself.
        expect(
          _sameStatementViolations(contents),
          isEmpty,
          reason:
              '$fastfilePath has a build invocation mentioning main_e2e — '
              'exactly what AC-AUTH-07 forbids',
        );
      });
    }

    test('codemagic.yaml builds its distributed APK from lib/main.dart', () {
      final File file = File('../codemagic.yaml');
      expect(
        file.existsSync(),
        isTrue,
        reason:
            'codemagic.yaml is missing — Android test builds come from it '
            '(docs/ANDROID_TEST_DISTRIBUTION.md)',
      );

      final List<String> builds = _logicalLines(
        file.readAsStringSync(),
      ).where((String line) => _releaseBuildInvocation.hasMatch(line)).toList();
      expect(
        builds,
        isNotEmpty,
        reason: 'codemagic.yaml has no flutter build step',
      );
      for (final String build in builds) {
        expect(
          _targetFlag.firstMatch(build)?.group(1),
          'lib/main.dart',
          reason:
              'every Codemagic build must target lib/main.dart, '
              'found: ${build.trim()}',
        );
      }
    });

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
          // What must never happen is both in the same logical statement —
          // a build step whose resolved target is the bypass entrypoint.
          // Logical-line joining (see `_logicalLines`) means wrapping a
          // shell command across multiple `run: |` lines with a trailing
          // `\` — completely idiomatic YAML/Bash, and already used by this
          // very file for its `flutter test` invocations — cannot be used
          // to split the two matches apart the way the Fastfile split once
          // did.
          for (final String violation in _sameStatementViolations(contents)) {
            violations.add('${entity.path}: $violation');
          }
        }

        expect(
          violations,
          isEmpty,
          reason:
              'these workflow statements build a release artifact from the '
              'e2e entrypoint: $violations',
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
        "never builds a release from it (that's the release builds' job)", () {
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
      expect(
        _sameStatementViolations(contents),
        isEmpty,
        reason:
            'a release-shaped build statement in flutter-integration.yml '
            'targets main_e2e',
      );
    });
  });
}
