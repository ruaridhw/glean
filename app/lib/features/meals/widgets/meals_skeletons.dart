import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// Loading placeholder for a recipe list — the saved library or live search
/// results — cross-faded into real content via `GleanCrossFade` (AC-TRN-01),
/// never a bare spinner.
class RecipeListSkeleton extends StatelessWidget {
  const RecipeListSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return ListView.separated(
      padding: EdgeInsets.all(tokens.spacing.lg),
      physics: const NeverScrollableScrollPhysics(),
      itemCount: 4,
      separatorBuilder: (_, _) => SizedBox(height: tokens.spacing.md),
      itemBuilder: (_, _) => SkeletonBox(
        width: double.infinity,
        height: 96,
        borderRadius: BorderRadius.circular(tokens.radius.lg),
      ),
    );
  }
}

/// Loading placeholder for recipe detail (saved or previewed) — standardises
/// on the same skeleton pattern rather than the RN detail screen's bare
/// `ActivityIndicator` (FLUTTER_MIGRATION.md §7, AC-MEAL-11/AC-TRN-01).
class RecipeDetailSkeleton extends StatelessWidget {
  const RecipeDetailSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return ListView(
      padding: EdgeInsets.all(tokens.spacing.lg),
      physics: const NeverScrollableScrollPhysics(),
      children: <Widget>[
        SkeletonBox(
          width: double.infinity,
          height: 96,
          borderRadius: BorderRadius.circular(tokens.radius.lg),
        ),
        SizedBox(height: tokens.spacing.md),
        SkeletonBox(
          width: double.infinity,
          height: 64,
          borderRadius: BorderRadius.circular(tokens.radius.lg),
        ),
        SizedBox(height: tokens.spacing.xl),
        SkeletonBox(
          width: double.infinity,
          height: 160,
          borderRadius: BorderRadius.circular(tokens.radius.lg),
        ),
        SizedBox(height: tokens.spacing.xl),
        SkeletonBox(
          width: double.infinity,
          height: 160,
          borderRadius: BorderRadius.circular(tokens.radius.lg),
        ),
      ],
    );
  }
}
