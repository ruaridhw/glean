import 'dart:async' show unawaited;

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The semantic three-weight ladder; weight signals consequence:
/// - [selectionClick]: a discrete selection with no side effect yet (tab, segment, filter chip, slider step).
/// - [lightImpact]: the default acknowledgement for any other tappable.
/// - [mediumImpact]: committing a data change (confirm, save, mark-cooked, delete-commit).
///
/// `heavyImpact()` and `vibrate()` are deliberately not members, so a feature cannot reach them. There is no
/// notification-style haptic; success/failure is a snackbar plus [mediumImpact].
///
/// An interface so widget tests can swap in [RecordingHaptics] via [hapticsProvider]. Feature code never calls
/// `HapticFeedback` directly; it reads this through `hapticsProvider`, or gets it from the themed wrappers
/// (e.g. `SwipeToDeleteRow`).
abstract class Haptics {
  void selectionClick();
  void lightImpact();
  void mediumImpact();
}

/// The production [Haptics] implementation: thin pass-through to
/// `package:flutter/services.dart`'s `HapticFeedback`.
class SystemHaptics implements Haptics {
  const SystemHaptics();

  @override
  void selectionClick() {
    unawaited(HapticFeedback.selectionClick());
  }

  @override
  void lightImpact() {
    unawaited(HapticFeedback.lightImpact());
  }

  @override
  void mediumImpact() {
    unawaited(HapticFeedback.mediumImpact());
  }
}

/// A fake [Haptics] for widget tests: records every call so a test can assert which weight fired and how often.
class RecordingHaptics implements Haptics {
  final List<HapticWeight> calls = <HapticWeight>[];

  @override
  void selectionClick() => calls.add(HapticWeight.selection);

  @override
  void lightImpact() => calls.add(HapticWeight.light);

  @override
  void mediumImpact() => calls.add(HapticWeight.medium);
}

/// The only weights on the ladder.
enum HapticWeight { selection, light, medium }

/// DI seam for [Haptics]. Production gets [SystemHaptics]; widget tests override it with [RecordingHaptics].
final Provider<Haptics> hapticsProvider = Provider<Haptics>(
  (Ref ref) => const SystemHaptics(),
);
