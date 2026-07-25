import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// The "N items expiring soon" banner. Wrapped in an [AnimatedSwitcher] so
/// it fades in/out as [expiringCount] crosses zero, rather than popping
/// (AC-TRN-04) — appearing/disappearing with every pantry mutation would
/// otherwise be an abrupt layout jump.
class PantryExpiryBanner extends StatelessWidget {
  const PantryExpiryBanner({super.key, required this.expiringCount});

  final int expiringCount;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 220),
      child: expiringCount <= 0
          ? const SizedBox(key: ValueKey<String>('no-expiry-banner'))
          : Container(
              key: const ValueKey<String>('expiry-banner'),
              margin: EdgeInsets.only(bottom: tokens.spacing.md),
              padding: EdgeInsets.symmetric(
                horizontal: tokens.spacing.md,
                vertical: tokens.spacing.sm,
              ),
              decoration: BoxDecoration(
                color: tokens.warningLight,
                borderRadius: BorderRadius.circular(tokens.radius.md),
              ),
              child: Row(
                children: <Widget>[
                  Icon(
                    Icons.warning_amber_rounded,
                    color: tokens.warning,
                    size: 18,
                  ),
                  SizedBox(width: tokens.spacing.sm),
                  Expanded(
                    child: Text(
                      '$expiringCount item${expiringCount == 1 ? '' : 's'} expiring soon',
                      style: Theme.of(
                        context,
                      ).textTheme.bodyMedium?.copyWith(color: tokens.warning),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
