import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import '../support/visual.dart';

void main() {
  setUpAll(loadBrandFonts);
  Widget rows(List<String> ids) => visual(
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final id in ids)
          GleanListEntrance(key: ValueKey(id), child: Text(id)),
      ],
    ),
  );
  testWidgets('an inserted row moves from visually hidden to visible', (
    tester,
  ) async {
    await tester.pumpWidget(rows(['Milk']));
    await golden(tester, 'entrance-hidden');
    await tester.pumpAndSettle();
    await golden(tester, 'entrance-visible');
  });
  testWidgets(
    'prepending a row keeps existing rows visible without replaying their entrance',
    (tester) async {
      await tester.pumpWidget(rows(['a', 'b']));
      await tester.pumpAndSettle();
      await tester.pumpWidget(rows(['c', 'a', 'b']));
      await golden(tester, 'entrance-prepend');
      await tester.pumpAndSettle();
      await golden(tester, 'entrance-complete');
    },
  );
}
