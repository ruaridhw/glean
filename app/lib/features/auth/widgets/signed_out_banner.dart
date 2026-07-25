/// The "signed out" banner AC-AUTH-04 requires: a token expiry gates
/// AI-backed features behind this, but never evicts the user from their
/// (fully local) data or routes them anywhere — nothing here touches
/// navigation.
///
/// Feature screens that offer an AI-backed action (Scan/Describe/Import/
/// Generate) should mount `const SignedOutBanner()` near the top of their
/// body; it renders nothing while AI features are available, so it is
/// always safe to include unconditionally rather than conditionally
/// building it.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/auth/auth_controller.dart'
    show aiFeaturesAvailableProvider;
import 'package:glean/design_system/design_system.dart';

class SignedOutBanner extends ConsumerWidget {
  const SignedOutBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bool available = ref.watch(aiFeaturesAvailableProvider);
    // AC-TRN-04: fades in/out rather than popping.
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 200),
      child: available
          ? const SizedBox.shrink(
              key: ValueKey<String>('signed-out-banner-hidden'),
            )
          : const _SignedOutBannerContent(
              key: ValueKey<String>('signed-out-banner-visible'),
            ),
    );
  }
}

class _SignedOutBannerContent extends StatelessWidget {
  const _SignedOutBannerContent({super.key});

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Container(
      width: double.infinity,
      padding: EdgeInsets.symmetric(
        horizontal: tokens.spacing.lg,
        vertical: tokens.spacing.md,
      ),
      color: tokens.warningLight,
      child: Row(
        children: <Widget>[
          Icon(Icons.wifi_off_rounded, color: tokens.warning, size: 20),
          SizedBox(width: tokens.spacing.sm),
          Expanded(
            child: Text(
              'Signed out — reconnect to use AI features. Your saved data is '
              'still here.',
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(color: tokens.warning),
            ),
          ),
        ],
      ),
    );
  }
}
