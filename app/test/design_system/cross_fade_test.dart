import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  group('GleanCrossFade', () {
    testWidgets(
      'cross-fades from skeleton to content via AnimatedSwitcher (AC-TRN-01)',
      (WidgetTester tester) async {
        bool showSkeleton = true;

        await tester.pumpWidget(
          MaterialApp(
            home: StatefulBuilder(
              builder: (BuildContext context, StateSetter setState) {
                return Scaffold(
                  body: Column(
                    children: <Widget>[
                      GleanCrossFade(
                        showSkeleton: showSkeleton,
                        skeleton: const Text('loading'),
                        content: const Text('loaded'),
                      ),
                      TextButton(
                        onPressed: () => setState(() => showSkeleton = false),
                        child: const Text('flip'),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        );

        expect(find.byType(AnimatedSwitcher), findsOneWidget);
        expect(find.text('loading'), findsOneWidget);
        expect(find.text('loaded'), findsNothing);

        await tester.tap(find.text('flip'));
        // Mid cross-fade: both keyed subtrees briefly coexist rather than a
        // hard cut — this is what AnimatedSwitcher buys over a bare
        // `showSkeleton ? a : b` swap.
        await tester.pump(const Duration(milliseconds: 50));
        expect(find.text('loaded'), findsOneWidget);

        await tester.pumpAndSettle();
        expect(find.text('loading'), findsNothing);
        expect(find.text('loaded'), findsOneWidget);
      },
    );
  });
}
