import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// The always-present back affordance on every Scan screen phase (AC-PAN-13):
/// permission-denied and permission-pending previously had no way out at all
/// — a hard dead end after a permanent deny. This renders identically across
/// every phase so there is exactly one place a user learns to look for it.
class ScanBackButton extends StatelessWidget {
  const ScanBackButton({super.key, required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Positioned(
      top: 16,
      left: 16,
      child: SafeArea(
        child: Material(
          color: tokens.cameraScrim,
          shape: const CircleBorder(),
          child: IconButton(
            icon: Icon(Icons.arrow_back_rounded, color: tokens.onCamera),
            tooltip: 'Cancel',
            onPressed: onPressed,
          ),
        ),
      ),
    );
  }
}
