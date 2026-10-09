import 'package:flutter/material.dart';

/// Snackbar helpers built on `ScaffoldMessenger`/`SnackBar`, themed centrally
/// by `SnackBarThemeData` in `theme.dart` (AC-DS-10). Replaces
/// `Toast.tsx` + `react-native-toast-message` — there is no bespoke toast
/// widget or queue; `ScaffoldMessenger` already queues.
class GleanSnackBar {
  const GleanSnackBar._();

  /// The undo snackbar shown after every destructive action (AC-UX-02):
  /// deleting a pantry item, a shopping row, a plan entry, a saved recipe,
  /// and reversing "Cooked". There is deliberately no confirm dialog anywhere
  /// in the app — this snackbar is the sole recovery path, so every call site
  /// that deletes something must go through it.
  ///
  /// Does **not** fire a haptic itself. The commit that caused the deletion
  /// (e.g. `SwipeToDeleteRow`'s `onDismissed`) already fired the single
  /// `mediumImpact()` for that action; firing a second one here from a purely
  /// presentational helper would reproduce the RN double-buzz bug this port
  /// is required to fix (AC-HAP-03).
  static void showUndo(
    BuildContext context, {
    required String message,
    required VoidCallback onUndo,
    Duration duration = const Duration(seconds: 4),
  }) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          duration: duration,
          action: SnackBarAction(label: 'Undo', onPressed: onUndo),
        ),
      );
  }

  /// A plain informational/error snackbar for moments with no undo affordance
  /// (e.g. a config-save failure surfacing per AC-SET-03). Still routes
  /// through the same themed `SnackBar`, never a bespoke toast.
  static void show(BuildContext context, String message) {
    showOn(ScaffoldMessenger.of(context), message);
  }

  /// A captured messenger survives route disposal during a pending Undo.
  static void showOn(ScaffoldMessengerState messenger, String message) {
    messenger
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }
}
