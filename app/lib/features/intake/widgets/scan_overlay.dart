import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// The framing guide, hint text and shutter button drawn over the live
/// camera preview.
class ScanOverlay extends StatelessWidget {
  const ScanOverlay({
    super.key,
    required this.capturing,
    required this.onCapture,
  });

  final bool capturing;
  final VoidCallback onCapture;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Stack(
      children: <Widget>[
        Positioned(
          left: 36,
          right: 36,
          top: 80,
          bottom: 120,
          child: IgnorePointer(
            child: DecoratedBox(
              decoration: BoxDecoration(
                border: Border.all(
                  color: Colors.white.withValues(alpha: 0.75),
                  width: 2.5,
                ),
                borderRadius: BorderRadius.circular(tokens.radius.xl),
              ),
            ),
          ),
        ),
        Positioned(
          left: 0,
          right: 0,
          bottom: 36,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.45),
                  borderRadius: BorderRadius.circular(tokens.radius.pill),
                ),
                child: Text(
                  'Line the receipt up inside the frame',
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: Colors.white),
                ),
              ),
              SizedBox(height: tokens.spacing.lg),
              _ShutterButton(capturing: capturing, onPressed: onCapture),
            ],
          ),
        ),
      ],
    );
  }
}

class _ShutterButton extends StatelessWidget {
  const _ShutterButton({required this.capturing, required this.onPressed});

  final bool capturing;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 72,
      height: 72,
      child: Material(
        color: Colors.white.withValues(alpha: 0.3),
        shape: const CircleBorder(),
        child: InkWell(
          key: const ValueKey<String>('scan-shutter'),
          customBorder: const CircleBorder(),
          onTap: capturing ? null : onPressed,
          child: Center(
            child: capturing
                ? const SizedBox(
                    width: 28,
                    height: 28,
                    child: CircularProgressIndicator(
                      strokeWidth: 3,
                      color: Colors.white,
                    ),
                  )
                : Container(
                    width: 58,
                    height: 58,
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      shape: BoxShape.circle,
                    ),
                  ),
          ),
        ),
      ),
    );
  }
}
