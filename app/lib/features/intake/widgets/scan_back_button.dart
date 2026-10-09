import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// The always-present back affordance on every Scan screen phase, so permission-denied and
/// permission-pending are never a dead end. Rendered identically across phases.
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
