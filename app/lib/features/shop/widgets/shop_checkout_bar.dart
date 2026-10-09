/// The checkout bar (AC-SHOP-10): RN's floated ~90px above the screen
/// bottom, leaving a dead band. `ShopScreen` places this as the last child of
/// a `SafeArea(top: false)`-wrapped column with no extra bottom margin, so it
/// sits flush against the safe area instead.
///
/// Stacked as a header row over a button row, rather than everything in one
/// `Row` — RN only ever had one button here ("Scan receipt"); adding "Done
/// shopping" (AC-SHOP-02) alongside it in a single row overflows on a
/// 360dp-wide phone (the two button labels alone need more width than a
/// typical bar leaves once its padding is subtracted). Two `Expanded`
/// buttons sharing a row underneath the text can't overflow at any width.
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

  /// R-08/AC-AUTH-04: "Scan receipt" calls the AI backend, so it — but not
  /// "Done shopping", a purely local write — is disabled while this is
  /// false.
  final bool aiFeaturesAvailable;
  final VoidCallback onScanReceipt;
  final VoidCallback onDoneShopping;

  @override
  Widget build(BuildContext context) {
    // Nothing to check out — RN's `CheckoutBar` returned null here too.
    if (checkedCount == 0) return const SizedBox.shrink();

    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;

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
          // `tokens.ink` is documented for exactly this use — the checkout
          // bar is one of the "inverted surfaces" it names (tokens.dart).
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
                color: Colors.white,
                fontWeight: FontWeight.w800,
              ),
            ),
            Text(
              'Scan a receipt or finish without one',
              style: textTheme.bodySmall?.copyWith(color: Colors.white70),
            ),
            SizedBox(height: tokens.spacing.sm),
            Row(
              children: <Widget>[
                Expanded(
                  child: TextButton(
                    onPressed: busy ? null : onDoneShopping,
                    style: TextButton.styleFrom(foregroundColor: Colors.white),
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
