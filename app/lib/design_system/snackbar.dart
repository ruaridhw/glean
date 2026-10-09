import 'dart:async';

import 'package:flutter/material.dart';

/// Snackbar helpers built on `ScaffoldMessenger`/`SnackBar`, themed centrally
/// by `SnackBarThemeData` in `theme.dart` (AC-DS-10). Replaces
/// `Toast.tsx` + `react-native-toast-message` — there is no bespoke toast
/// widget or queue; `ScaffoldMessenger` already queues.
class GleanSnackBar {
  const GleanSnackBar._();

  /// Runs a destructive [perform], shows the undo snackbar, and runs [undo]
  /// with perform's result if tapped. All failures surface as snackbars on the
  /// messenger captured *before* perform, so a popped route cannot swallow them.
  /// Returns true when perform succeeded.
  ///
  /// Fires no haptic itself; pass [onSuccess] for one (swipe-to-delete already
  /// fires its own).
  static Future<bool> runUndoable<T>(
    BuildContext context, {
    required Future<T> Function() perform,
    required Future<void> Function(T snapshot) undo,
    required String message,
    required String failureMessage,
    required String undoFailureMessage,
    String Function(Object error)? describeError,
    VoidCallback? onSuccess,
  }) async {
    final messenger = ScaffoldMessenger.of(context);
    final T snapshot;
    try {
      snapshot = await perform();
    } catch (error) {
      if (messenger.mounted) {
        showOn(messenger, describeError?.call(error) ?? failureMessage);
      }
      return false;
    }
    onSuccess?.call();
    if (!messenger.mounted) return true;
    messenger
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          action: SnackBarAction(
            label: 'Undo',
            onPressed: () => unawaited(() async {
              try {
                await undo(snapshot);
              } catch (_) {
                if (messenger.mounted) showOn(messenger, undoFailureMessage);
              }
            }()),
          ),
        ),
      );
    return true;
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
