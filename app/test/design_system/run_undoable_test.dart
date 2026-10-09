import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

Future<BuildContext> _pumpHost(WidgetTester tester) async {
  late BuildContext captured;
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) {
            captured = context;
            return const SizedBox();
          },
        ),
      ),
    ),
  );
  return captured;
}

void main() {
  testWidgets('shows undo and restores from the snapshot', (tester) async {
    final context = await _pumpHost(tester);
    String? restored;
    final ok = await GleanSnackBar.runUndoable<String>(
      context,
      perform: () async => 'snap',
      undo: (s) async => restored = s,
      message: 'Removed',
      failureMessage: 'Could not remove',
      undoFailureMessage: 'Could not restore',
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 750));
    expect(ok, isTrue);
    expect(find.text('Removed'), findsOneWidget);
    await tester.tap(find.text('Undo'));
    await tester.pump();
    expect(restored, 'snap');
  });

  testWidgets('a failing perform shows failureMessage and returns false', (
    tester,
  ) async {
    final context = await _pumpHost(tester);
    final ok = await GleanSnackBar.runUndoable<void>(
      context,
      perform: () async => throw StateError('db'),
      undo: (_) async {},
      message: 'Removed',
      failureMessage: 'Could not remove',
      undoFailureMessage: 'Could not restore',
    );
    await tester.pump();
    expect(ok, isFalse);
    expect(find.text('Could not remove'), findsOneWidget);
  });

  testWidgets('describeError overrides failureMessage', (tester) async {
    final context = await _pumpHost(tester);
    await GleanSnackBar.runUndoable<void>(
      context,
      perform: () async => throw const FormatException('units'),
      undo: (_) async {},
      message: 'x',
      failureMessage: 'generic',
      undoFailureMessage: 'y',
      describeError: (e) => e is FormatException ? 'Unit mismatch' : 'generic',
    );
    await tester.pump();
    expect(find.text('Unit mismatch'), findsOneWidget);
  });

  testWidgets('a failing undo reports on the captured messenger', (
    tester,
  ) async {
    final context = await _pumpHost(tester);
    await GleanSnackBar.runUndoable<void>(
      context,
      perform: () async {},
      undo: (_) async => throw StateError('db'),
      message: 'Removed',
      failureMessage: 'f',
      undoFailureMessage: 'Could not restore',
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 750));
    await tester.tap(find.text('Undo'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 750));
    expect(find.text('Could not restore'), findsOneWidget);
  });
}
