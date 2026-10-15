import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  group('GleanSnackBar.runUndoable', () {
    testWidgets('a second destructive action replaces the undo snackbar', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: gleanLightTheme,
          home: Scaffold(
            body: Builder(
              builder: (BuildContext context) {
                Widget button(String label, String message) => ElevatedButton(
                  onPressed: () => GleanSnackBar.runUndoable<void>(
                    context,
                    perform: () async {},
                    undo: (_) async {},
                    message: message,
                    failureMessage: 'f',
                    undoFailureMessage: 'u',
                  ),
                  child: Text(label),
                );
                return Column(
                  children: <Widget>[
                    button('delete-1', 'First item deleted'),
                    button('delete-2', 'Second item deleted'),
                  ],
                );
              },
            ),
          ),
        ),
      );

      await tester.tap(find.text('delete-1'));
      await tester.pump();
      await tester.tap(find.text('delete-2'));
      await tester.pump();

      expect(find.text('First item deleted'), findsNothing);
      expect(find.text('Second item deleted'), findsOneWidget);
    });

    testWidgets('the undo snackbar hides after 5 seconds without interaction', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(_undoHost());

      await tester.tap(find.text('delete'));
      await tester.pumpAndSettle();
      expect(find.text('Item deleted'), findsOneWidget);

      await tester.pump(const Duration(seconds: 4));
      expect(find.text('Item deleted'), findsOneWidget);

      await tester.pump(const Duration(seconds: 2));
      await tester.pumpAndSettle(); // exit animation

      expect(find.text('Item deleted'), findsNothing);
      expect(find.text('Undo'), findsNothing);
    });
  });
}

Widget _undoHost() {
  return MaterialApp(
    theme: gleanLightTheme,
    home: Scaffold(
      body: Builder(
        builder: (BuildContext context) {
          return ElevatedButton(
            onPressed: () => GleanSnackBar.runUndoable<void>(
              context,
              perform: () async {},
              undo: (_) async {},
              message: 'Item deleted',
              failureMessage: 'f',
              undoFailureMessage: 'u',
            ),
            child: const Text('delete'),
          );
        },
      ),
    ),
  );
}
