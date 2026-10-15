import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// Loading placeholder for the shopping list, cross-faded into real content
/// via `GleanCrossFade` (AC-TRN-01) — never a bare spinner, and never shown
/// unconditionally on every tab focus the way RN's `loading` flag did.
class ShopListSkeleton extends StatelessWidget {
  const ShopListSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return ListView.separated(
      physics: const NeverScrollableScrollPhysics(),
      itemCount: 5,
      separatorBuilder: (BuildContext _, int _) =>
          SizedBox(height: tokens.spacing.sm),
      itemBuilder: (BuildContext _, int _) => SkeletonBox(
        width: double.infinity,
        height: 56,
        borderRadius: BorderRadius.circular(tokens.radius.lg),
      ),
    );
  }
}
