/// The checkout bar. `ShopScreen` places it as the last child of a `SafeArea(top: false)`-wrapped column with no
/// extra bottom margin, so it sits flush against the safe area.
///
/// Stacked as a header row over a button row: "Scan receipt" and "Done shopping" in a single row overflow on a
/// 360dp-wide phone, while two `Expanded` buttons under the text can't overflow at any width.
library;

import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import '../presentation.dart';

class ShopCheckoutBar extends StatelessWidget {
  const ShopCheckoutBar({
    required this.checkedCount,
    required this.busy,
    required this.aiFeaturesAvailable,
    required this.onScanReceipt,
    required this.onDoneShopping,
    super.key,
  });

  final int checkedCount;

  /// True while "Done shopping" is committing — disables both actions so a
  /// double-tap can't fire the checkout (or a second scan) twice.
  final bool busy;

  /// "Scan receipt" calls the AI backend, so it (but not "Done shopping", a local write) is disabled while this
  /// is false.
  final bool aiFeaturesAvailable;
  final VoidCallback onScanReceipt;
  final VoidCallback onDoneShopping;

  @override
  Widget build(BuildContext context) {
    // Nothing to check out.
    if (checkedCount == 0) return const SizedBox.shrink();

    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final Color onPrimary = Theme.of(context).colorScheme.onPrimary;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        tokens.spacing.lg,
        0,
        tokens.spacing.lg,
        tokens.spacing.sm,
      ),
      child: Container(
        padding: EdgeInsets.symmetric(
          horizontal: tokens.spacing.lg,
          vertical: tokens.spacing.md,
        ),
        decoration: BoxDecoration(
          // `tokens.ink` is documented for exactly this use: the checkout bar is one of its "inverted surfaces".
          color: tokens.ink,
          borderRadius: BorderRadius.circular(tokens.radius.xl),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              cartCountLabel(checkedCount),
              style: textTheme.bodyMedium?.copyWith(
                color: onPrimary,
                fontWeight: FontWeight.w800,
              ),
            ),
            Text(
              'Add them to your pantry, or scan a receipt',
              style: textTheme.bodySmall?.copyWith(
                color: onPrimary.withValues(alpha: 0.7),
              ),
            ),
            SizedBox(height: tokens.spacing.sm),
            Row(
              children: <Widget>[
                Expanded(
                  child: TextButton(
                    onPressed: busy ? null : onDoneShopping,
                    style: TextButton.styleFrom(foregroundColor: onPrimary),
                    child: const Text('Done shopping'),
                  ),
                ),
                SizedBox(width: tokens.spacing.sm),
                Expanded(
                  child: FilledButton(
                    onPressed: busy || !aiFeaturesAvailable
                        ? null
                        : onScanReceipt,
                    child: const Text('Scan receipt'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
