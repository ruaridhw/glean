import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

const visualKey = ValueKey('visual-contract');

Future<void> loadBrandFonts() async {
  final fonts = FontLoader('PlusJakartaSans');
  for (final file in [
    '400Regular',
    '500Medium',
    '600SemiBold',
    '700Bold',
    '800ExtraBold',
  ]) {
    fonts.addFont(rootBundle.load('assets/fonts/PlusJakartaSans-$file.ttf'));
  }
  await fonts.load();
  await (FontLoader(
    'MaterialIcons',
  )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
}

Widget visual(Widget child, {ThemeData? theme, double scale = 1}) =>
    MaterialApp(
      theme: theme ?? gleanLightTheme,
      home: Scaffold(
        body: Center(
          child: MediaQuery(
            data: MediaQueryData(textScaler: TextScaler.linear(scale)),
            child: RepaintBoundary(
              key: visualKey,
              child: ColoredBox(
                color: Colors.white,
                child: SizedBox(
                  width: 420,
                  height: 280,
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: child,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );

Future<void> golden(WidgetTester tester, String name) => expectLater(
  find.byKey(visualKey),
  matchesGoldenFile(File('test/design_system/goldens/$name.png').absolute.uri),
);
