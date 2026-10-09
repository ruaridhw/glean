import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

Widget host(Widget child, {ThemeData? theme, double scale = 1}) => MaterialApp(
  theme: theme ?? gleanLightTheme,
  home: Scaffold(
    body: Center(
      child: MediaQuery(
        data: MediaQueryData(textScaler: TextScaler.linear(scale)),
        child: child,
      ),
    ),
  ),
);

void main() {
  testWidgets(
    'status pills stay readable and accessible at twice the text scale',
    (tester) async {
      await tester.pumpWidget(
        host(
          const Column(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              GleanBadge(label: '3 expiring', tone: GleanBadgeTone.warning),
              GleanBadge(label: 'In plan', tone: GleanBadgeTone.primary),
            ],
          ),
          scale: 2,
        ),
      );
      expect(tester.getSemantics(find.text('3 expiring')).label, '3 expiring');
      expect(tester.takeException(), isNull);
    },
  );
}
