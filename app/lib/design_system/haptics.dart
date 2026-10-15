import 'dart:async' show unawaited;

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The semantic three-weight ladder (FLUTTER_MIGRATION.md §7, AC-HAP-01).
///
/// Weight signals consequence, not decoration:
/// - [selectionClick] — a discrete selection with no side effect yet: tab
///   switch, segment switch, filter chip, dietary chip, a slider stepping to
///   a new value.
/// - [lightImpact] — the default acknowledgement for any tappable that isn't
///   one of the other two cases.
/// - [mediumImpact] — committing a data change: confirm, save, add-to-plan,
///   mark-cooked, delete-commit.
///
/// `heavyImpact()` and `vibrate()` are deliberately **not** members of this
/// interface (AC-HAP-02) — there is no ladder rung for them, so a feature
/// cannot reach them through the design system even by accident. Flutter's
/// `HapticFeedback` also has no notification-style haptic (success/warning);
/// that is fine and deliberate — success/failure is a snackbar plus
/// [mediumImpact] (see `snackbar.dart`).
///
/// This is an interface (not a set of static functions) precisely so it can
/// be swapped for a [RecordingHaptics] fake in widget tests via
/// [hapticsProvider] — see AC-TEST-13. Feature code must never call
/// `HapticFeedback` directly (AC-HAP-04): it reads this through
/// `ref.read(hapticsProvider)`/`ref.watch(hapticsProvider)`, or gets it for
/// free from the themed wrapper widgets in this package (e.g.
/// `SwipeToDeleteRow`) that already fire the right rung on commit.
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

/// A fake [Haptics] for widget tests: records every call so a test can assert
/// exactly which weight fired, and how many times (AC-TEST-13, AC-HAP-03 — a
/// single delete tap must fire exactly one haptic).
class RecordingHaptics implements Haptics {
  final List<HapticWeight> calls = <HapticWeight>[];

  @override
  void selectionClick() => calls.add(HapticWeight.selection);

  @override
  void lightImpact() => calls.add(HapticWeight.light);

  @override
  void mediumImpact() => calls.add(HapticWeight.medium);
}

/// The only weights on the ladder. There is intentionally no `heavy` or
/// `vibrate` member (AC-HAP-02).
enum HapticWeight { selection, light, medium }

/// DI seam for [Haptics]. Production code never overrides this (it gets
/// [SystemHaptics] by default); widget tests override it with
/// [RecordingHaptics] via `ProviderScope(overrides: [...])` to assert which
/// rung fired without touching a real platform channel.
final Provider<Haptics> hapticsProvider = Provider<Haptics>(
  (Ref ref) => const SystemHaptics(),
);
