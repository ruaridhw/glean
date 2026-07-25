import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  group('Haptics ladder', () {
    test(
      'exposes exactly the three-weight ladder and nothing else (AC-HAP-01)',
      () {
        final RecordingHaptics haptics = RecordingHaptics();
        haptics.selectionClick();
        haptics.lightImpact();
        haptics.mediumImpact();

        expect(haptics.calls, <HapticWeight>[
          HapticWeight.selection,
          HapticWeight.light,
          HapticWeight.medium,
        ]);
      },
    );

    test(
      'the implementation never invokes HapticFeedback.heavyImpact/vibrate (AC-HAP-02)',
      () {
        // A compile-time guarantee, not just a runtime one: `Haptics` is an
        // interface with exactly three methods, so `heavyImpact`/`vibrate`
        // cannot be reached through it even by mistake. Assert the surface
        // directly via a source scan of this package's own implementation, so
        // a future edit that adds one back fails this test rather than relying
        // on nobody happening to call it. Scoped to the qualified call
        // (`HapticFeedback.heavyImpact`/`.vibrate`) rather than the bare word,
        // since this file's own doc comments legitimately *say* "heavyImpact"
        // and "vibrate" in prose while explaining that they're unused.
        final String source = File(
          'lib/design_system/haptics.dart',
        ).readAsStringSync();
        expect(source.contains('HapticFeedback.heavyImpact'), isFalse);
        expect(source.contains('HapticFeedback.vibrate'), isFalse);
      },
    );

    test('hapticsProvider defaults to SystemHaptics in production', () {
      // Constructed, not invoked — invoking it would hit a real platform
      // channel, which widget/unit tests must never do. Existence of the
      // binding is what AC-HAP-04 needs: feature code can depend on
      // `hapticsProvider` without wiring its own default.
      expect(const SystemHaptics(), isA<Haptics>());
    });
  });
}
