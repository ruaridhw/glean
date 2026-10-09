import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Repo standards from `app/AGENTS.md` §Standards. Every rule is enforced with
/// no exceptions.

final RegExp _forbiddenFeatureImport = RegExp(
  r'''^\s*import\s+['"](package:drift/|package:glean/data/(database|tables|deletion_snapshots)\.dart|\.\./.*data/(database|tables|deletion_snapshots)\.dart)''',
  multiLine: true,
);

final RegExp _rawColour = RegExp(
  r'\bColors\.(?!transparent\b)\w+|\bColor\(0x[0-9A-Fa-f]{8}\)',
);

final RegExp _citation = RegExp(
  r'AC-[A-Z]+-\d+|\bR-\d\d\b|\bF-\d\d\b|FINDINGS\.md|REMEDIATION\.md|\.scratch/|\bWave \d|orchestrator',
);

final RegExp _bypassImport = RegExp(
  r'''^\s*(import|export)\s+['"][^'"]*auth_bypass\.dart['"]''',
  multiLine: true,
);

Iterable<File> _dartFiles(String root) => Directory(root)
    .listSync(recursive: true)
    .whereType<File>()
    .where((f) => f.path.endsWith('.dart') && !f.path.endsWith('.g.dart'));

String _rel(File f) => f.path.replaceAll('\\', '/');

void _expectNone({
  required Iterable<File> files,
  required bool Function(String source) violates,
  required String rule,
}) {
  final violations = <String>[
    for (final file in files)
      if (violates(file.readAsStringSync())) _rel(file),
  ];
  expect(violations, isEmpty, reason: '$rule — see app/AGENTS.md §Standards');
}

void main() {
  test('features reach data only through providers (rule 1)', () {
    _expectNone(
      files: _dartFiles('lib/features'),
      violates: _forbiddenFeatureImport.hasMatch,
      rule:
          'lib/features/** must not import drift, database.dart, '
          'tables.dart or deletion_snapshots.dart',
    );
  });

  test('colours come from the theme outside design_system (rule 2)', () {
    _expectNone(
      files: _dartFiles(
        'lib',
      ).where((f) => !_rel(f).startsWith('lib/design_system/')),
      violates: _rawColour.hasMatch,
      rule:
          'no Colors.* (except transparent) or Color(0x…) outside '
          'lib/design_system/',
    );
  });

  test('no process citations in comments (rule 3)', () {
    _expectNone(
      files: _dartFiles('lib'),
      violates: _citation.hasMatch,
      rule:
          'no AC-/R-/F-/FINDINGS/REMEDIATION/.scratch/Wave/orchestrator '
          'references in lib/',
    );
  });

  test('only main_e2e.dart imports auth_bypass.dart', () {
    const allowed = <String>{'lib/auth/auth_bypass.dart', 'lib/main_e2e.dart'};
    final violations = <String>[
      for (final f in _dartFiles('lib'))
        if (!allowed.contains(_rel(f)) &&
            _bypassImport.hasMatch(f.readAsStringSync()))
          _rel(f),
    ];
    expect(
      violations,
      isEmpty,
      reason: 'These files would pull the test bypass into a release build',
    );
  });
}
