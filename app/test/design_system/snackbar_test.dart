import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  group('GleanSnackBar.showUndo', () {
    testWidgets('shows the undo snackbar and its action fires the callback', (
      WidgetTester tester,
    ) async {
      bool undone = false;

      await tester.pumpWidget(
        MaterialApp(
          theme: gleanLightTheme,
          home: Scaffold(
            body: Builder(
              builder: (BuildContext context) {
                return ElevatedButton(
                  onPressed: () {
                    GleanSnackBar.showUndo(
                      context,
                      message: 'Item deleted',
                      onUndo: () => undone = true,
                    );
                  },
                  child: const Text('delete'),
                );
              },
            ),
          ),
        ),
      );

      await tester.tap(find.text('delete'));
      await tester
          .pumpAndSettle(); // let the snackbar's entrance animation finish

      expect(find.text('Item deleted'), findsOneWidget);
      expect(find.text('Undo'), findsOneWidget);

      await tester.tap(find.text('Undo'));
      await tester.pump();

      expect(undone, isTrue);
    });

    testWidgets(
      'a second destructive action replaces rather than stacks the snackbar',
      (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            theme: gleanLightTheme,
            home: Scaffold(
              body: Builder(
                builder: (BuildContext context) {
                  return Column(
                    children: <Widget>[
                      ElevatedButton(
                        onPressed: () {
                          GleanSnackBar.showUndo(
                            context,
                            message: 'First item deleted',
                            onUndo: () {},
                          );
                        },
                        child: const Text('delete-1'),
                      ),
                      ElevatedButton(
                        onPressed: () {
                          GleanSnackBar.showUndo(
                            context,
                            message: 'Second item deleted',
                            onUndo: () {},
                          );
                        },
                        child: const Text('delete-2'),
                      ),
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
      },
    );
  });
}
