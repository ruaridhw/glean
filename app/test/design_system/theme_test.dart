import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  group('gleanLightTheme', () {
    test(
      'declares a single font family and resolves weight, not family name (AC-BUILD-03)',
      () {
        // pubspec.yaml declares ONE family ('PlusJakartaSans') with weight
        // descriptors 400/500/600/700/800. Unlike the RN app — which had to
        // pick a *different family name* per weight because RN resolves weight
        // from the family name, not `fontWeight` — every TextTheme role below
        // must share this one family and differ only by `fontWeight`.
        final ThemeData theme = gleanLightTheme;

        final Map<String, TextStyle?> roles = <String, TextStyle?>{
          'headlineLarge': theme.textTheme.headlineLarge, // largeTitle: 800
          'titleLarge': theme.textTheme.titleLarge, // title2: 700
          'titleMedium': theme.textTheme.titleMedium, // headline: 700
          'bodyLarge': theme.textTheme.bodyLarge, // body: 400
          'bodyMedium': theme.textTheme.bodyMedium, // subhead: 600
          'bodySmall': theme.textTheme.bodySmall, // caption: 600
          'labelSmall': theme.textTheme.labelSmall, // sectionLabel: 800
        };

        for (final MapEntry<String, TextStyle?> entry in roles.entries) {
          expect(
            entry.value?.fontFamily,
            'PlusJakartaSans',
            reason: '${entry.key} must use the single declared family',
          );
        }

        expect(theme.textTheme.headlineLarge?.fontWeight, FontWeight.w800);
        expect(theme.textTheme.titleLarge?.fontWeight, FontWeight.w700);
        expect(theme.textTheme.titleMedium?.fontWeight, FontWeight.w700);
        expect(theme.textTheme.bodyLarge?.fontWeight, FontWeight.w400);
        expect(theme.textTheme.bodyMedium?.fontWeight, FontWeight.w600);
        expect(theme.textTheme.bodySmall?.fontWeight, FontWeight.w600);
        expect(theme.textTheme.labelSmall?.fontWeight, FontWeight.w800);

        // Confirms weight — not family — is what's varying (the actual AC-BUILD-03
        // contract): two roles, same family, different declared weight.
        expect(
          theme.textTheme.headlineLarge?.fontFamily,
          theme.textTheme.bodyLarge?.fontFamily,
        );
        expect(
          theme.textTheme.headlineLarge?.fontWeight,
          isNot(equals(theme.textTheme.bodyLarge?.fontWeight)),
        );
      },
    );

    test('maps the RN palette onto ColorScheme roles (AC-DS-02, §4)', () {
      final ColorScheme scheme = gleanLightTheme.colorScheme;
      expect(scheme.primary, const Color(0xFF2E9D63));
      expect(scheme.onPrimary, Colors.white);
      expect(scheme.primaryContainer, const Color(0xFFE3F2E7));
      expect(scheme.onPrimaryContainer, const Color(0xFF1C6B41));
      expect(scheme.error, const Color(0xFFB13C25)); // RN `danger`
      expect(
        scheme.errorContainer,
        const Color(0xFFF9DED8),
      ); // RN `dangerLight`
      expect(scheme.surface, const Color(0xFFFFFFFF));
      expect(scheme.onSurface, const Color(0xFF26362B));
    });

    test('no cupertino import anywhere in the design system (AC-DS-01)', () {
      for (final String path in <String>[
        'lib/design_system/theme.dart',
        'lib/design_system/tokens.dart',
        'lib/design_system/badge.dart',
        'lib/design_system/brand_mark.dart',
        'lib/design_system/skeleton.dart',
        'lib/design_system/cross_fade.dart',
        'lib/design_system/swipe_to_delete.dart',
        'lib/design_system/snackbar.dart',
        'lib/design_system/haptics.dart',
      ]) {
        expect(
          File(path).readAsStringSync().contains('cupertino'),
          isFalse,
          reason: '$path must not import package:flutter/cupertino.dart',
        );
      }
    });
  });
}
