/// Loading placeholder for the Plan screen, shown while `planWeekProvider`/
/// `userConfigProvider` resolve their first value. Cross-faded into content
/// by `GleanCrossFade` (AC-TRN-01) rather than swapped with a hard cut.
library;

import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

class PlanSkeleton extends StatelessWidget {
  const PlanSkeleton({super.key, this.rows = 5});

  final int rows;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return ListView(
      padding: EdgeInsets.all(tokens.spacing.lg),
      children: <Widget>[
        SkeletonBox(
          width: double.infinity,
          height: 88,
          borderRadius: BorderRadius.circular(tokens.radius.lg),
        ),
        SizedBox(height: tokens.spacing.lg),
        for (int i = 0; i < rows; i++)
          Padding(
            padding: EdgeInsets.only(bottom: tokens.spacing.sm),
            child: SkeletonBox(
              width: double.infinity,
              height: 64,
              borderRadius: BorderRadius.circular(tokens.radius.lg),
            ),
          ),
      ],
    );
  }
}
