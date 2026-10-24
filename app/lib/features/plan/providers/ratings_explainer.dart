import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Whether the one-off ratings explainer is on screen right now.
///
/// The "first tap ever" claim is atomic in `UserConfigRepository`, so only one tap can win it. This flag is
/// the second guard: if a claim ever resolves while the sheet is already open (a slow first write on a cold
/// database, or a second tap landing in the same frame), the caller must not stack another copy on top.
final NotifierProvider<RatingsExplainerOpen, bool>
ratingsExplainerOpenProvider = NotifierProvider<RatingsExplainerOpen, bool>(
  RatingsExplainerOpen.new,
);

class RatingsExplainerOpen extends Notifier<bool> {
  @override
  bool build() => false;

  /// Claims the screen for the explainer; false when one is already showing.
  bool open() {
    if (state) return false;
    state = true;
    return true;
  }

  void close() => state = false;
}
