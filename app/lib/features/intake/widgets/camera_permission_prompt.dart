import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// The denied/permanently-denied camera-permission states (AC-PAN-13). Both
/// render the same shape — an explanation plus one recovery action — since
/// the only difference is *which* action can recover them: a plain re-prompt
/// while the OS will still ask, or a trip to Settings once it won't.
class CameraPermissionPrompt extends StatelessWidget {
  const CameraPermissionPrompt({
    super.key,
    required this.permanentlyDenied,
    required this.onRequestPermission,
    required this.onOpenSettings,
  });

  final bool permanentlyDenied;
  final VoidCallback onRequestPermission;
  final VoidCallback onOpenSettings;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Container(
      color: const Color(0xFF111511),
      alignment: Alignment.center,
      padding: EdgeInsets.all(tokens.spacing.xl),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          const Icon(
            Icons.no_photography_rounded,
            color: Colors.white,
            size: 48,
          ),
          SizedBox(height: tokens.spacing.lg),
          Text(
            permanentlyDenied
                ? 'Camera access is turned off for Glean. Enable it in '
                      'Settings to scan a receipt.'
                : 'Camera permission is needed to scan receipts.',
            textAlign: TextAlign.center,
            style: Theme.of(
              context,
            ).textTheme.bodyLarge?.copyWith(color: Colors.white),
          ),
          SizedBox(height: tokens.spacing.lg),
          FilledButton(
            onPressed: permanentlyDenied ? onOpenSettings : onRequestPermission,
            child: Text(
              permanentlyDenied ? 'Open Settings' : 'Grant permission',
            ),
          ),
        ],
      ),
    );
  }
}
