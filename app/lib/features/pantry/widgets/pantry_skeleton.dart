import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// Loading placeholder for the pantry list, shown only while the very first
/// stream event hasn't arrived (AC-DATA-04) — never re-shown on every tab
/// focus the way RN's `loading = true` on focus did.
class PantrySkeleton extends StatelessWidget {
  const PantrySkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Padding(
      padding: EdgeInsets.all(tokens.spacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          SkeletonBox(
            width: 160,
            height: 20,
            borderRadius: BorderRadius.circular(tokens.radius.sm),
          ),
          SizedBox(height: tokens.spacing.lg),
          for (int i = 0; i < 4; i++) ...<Widget>[
            SkeletonBox(
              width: double.infinity,
              height: 64,
              borderRadius: BorderRadius.circular(tokens.radius.lg),
            ),
            SizedBox(height: tokens.spacing.sm),
          ],
        ],
      ),
    );
  }
}
