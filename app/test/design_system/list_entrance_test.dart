// Coverage for R-10 (FLUTTER_MIGRATION.md §7, AC-TRN-02): list insertion had
// no animation anywhere in Pantry, Shop or Meals — only removal (via
// `Dismissible`) did. `GleanListEntrance` is the implicit-animation fix;
// this asserts the mechanism itself (starts hidden, settles once mounted)
// and the identity contract its own doc comment calls load-bearing: a row
// that merely shifted position keeps its already-settled state rather than
// replaying the fade for an item that isn't actually new.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  group('GleanListEntrance', () {
    testWidgets('settles from hidden to visible once mounted', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: GleanListEntrance(
            key: ValueKey<String>('row-1'),
            child: Text('Milk'),
          ),
        ),
      );

      // First frame: still off-place/transparent, before the post-frame
      // callback that starts the settle has run.
      AnimatedOpacity opacity = tester.widget(find.byType(AnimatedOpacity));
      expect(opacity.opacity, 0);
      AnimatedSlide slide = tester.widget(find.byType(AnimatedSlide));
      expect(slide.offset, isNot(Offset.zero));

      await tester.pump(const Duration(milliseconds: 300));

      opacity = tester.widget(find.byType(AnimatedOpacity));
      expect(opacity.opacity, 1);
      slide = tester.widget(find.byType(AnimatedSlide));
      expect(slide.offset, Offset.zero);
    });

    testWidgets(
      'a row that merely shifted position keeps its settled state; only a '
      'genuinely new key replays the entrance',
      (WidgetTester tester) async {
        Widget buildList(List<String> ids) {
          return MaterialApp(
            home: Scaffold(
              body: Column(
                children: <Widget>[
                  for (final String id in ids)
                    GleanListEntrance(
                      key: ValueKey<String>(id),
                      child: Text(id),
                    ),
                ],
              ),
            ),
          );
        }

        await tester.pumpWidget(buildList(<String>['a', 'b']));
        await tester.pump(const Duration(milliseconds: 300));
        expect(
          tester
              .widgetList<AnimatedOpacity>(find.byType(AnimatedOpacity))
              .map((AnimatedOpacity w) => w.opacity),
          everyElement(1),
        );

        // Insert a new id ahead of the existing two — 'a' and 'b' both
        // shift position, and a fresh 'c' appears at the front.
        await tester.pumpWidget(buildList(<String>['c', 'a', 'b']));

        // Immediately after the shift (before the new entry's own settle
        // pump): 'a' and 'b' are already fully visible because their state
        // moved with their key rather than resetting; only 'c' just started
        // its own fade from 0.
        final Finder aOpacity = find.ancestor(
          of: find.text('a'),
          matching: find.byType(AnimatedOpacity),
        );
        final Finder bOpacity = find.ancestor(
          of: find.text('b'),
          matching: find.byType(AnimatedOpacity),
        );
        final Finder cOpacity = find.ancestor(
          of: find.text('c'),
          matching: find.byType(AnimatedOpacity),
        );
        expect(tester.widget<AnimatedOpacity>(aOpacity).opacity, 1);
        expect(tester.widget<AnimatedOpacity>(bOpacity).opacity, 1);
        expect(tester.widget<AnimatedOpacity>(cOpacity).opacity, 0);

        await tester.pump(const Duration(milliseconds: 300));
        expect(tester.widget<AnimatedOpacity>(cOpacity).opacity, 1);
      },
    );
  });
}
