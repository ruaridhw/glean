import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  testWidgets('renders header plus rows', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: gleanLightTheme,
        home: const ListSkeleton(rows: 3, headerHeight: 88),
      ),
    );
    expect(find.byType(SkeletonBox), findsNWidgets(4));
  });

  testWidgets('renders only rows without a header', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: gleanLightTheme,
        home: const ListSkeleton(rows: 2, padding: false),
      ),
    );
    expect(find.byType(SkeletonBox), findsNWidgets(2));
  });
}
