import 'package:flutter/material.dart';

/// The always-present back affordance on every Scan screen phase (AC-PAN-13):
/// permission-denied and permission-pending previously had no way out at all
/// — a hard dead end after a permanent deny. This renders identically across
/// every phase so there is exactly one place a user learns to look for it.
class ScanBackButton extends StatelessWidget {
  const ScanBackButton({super.key, required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Positioned(
      top: 16,
      left: 16,
      child: SafeArea(
        child: Material(
          color: Colors.black.withValues(alpha: 0.45),
          shape: const CircleBorder(),
          child: IconButton(
            icon: const Icon(Icons.arrow_back_rounded, color: Colors.white),
            tooltip: 'Cancel',
            onPressed: onPressed,
          ),
        ),
      ),
    );
  }
}
