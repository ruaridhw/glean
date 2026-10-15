import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Taps on the Settings version label that unlock developer mode.
const int developerModeUnlockTaps = 7;

/// Whether developer-only actions (Export diagnostics) are shown. Off at every launch: unlocking is a
/// deliberate gesture, available on release builds, and holds only for the running session.
class DeveloperMode extends Notifier<bool> {
  int _taps = 0;

  @override
  bool build() => false;

  /// Counts one tap on the version label; the [developerModeUnlockTaps]th unlocks.
  void registerVersionTap() {
    if (state) return;
    _taps++;
    if (_taps >= developerModeUnlockTaps) state = true;
  }
}

final NotifierProvider<DeveloperMode, bool> developerModeProvider =
    NotifierProvider<DeveloperMode, bool>(DeveloperMode.new);
