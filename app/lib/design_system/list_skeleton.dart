import 'package:flutter/material.dart';

import 'skeleton.dart';
import 'tokens.dart';

/// Loading placeholder: an optional header block then [rows] row blocks.
class ListSkeleton extends StatelessWidget {
  const ListSkeleton({
    super.key,
    this.rows = 5,
    this.rowHeight = 64,
    this.headerHeight,
    this.padding = true,
  });

  final int rows;
  final double rowHeight;
  final double? headerHeight;
  final bool padding;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final BorderRadius radius = BorderRadius.circular(tokens.radius.lg);
    return ListView(
      physics: const NeverScrollableScrollPhysics(),
      padding: padding ? EdgeInsets.all(tokens.spacing.lg) : EdgeInsets.zero,
      children: <Widget>[
        if (headerHeight != null) ...<Widget>[
          SkeletonBox(
            width: double.infinity,
            height: headerHeight!,
            borderRadius: radius,
          ),
          SizedBox(height: tokens.spacing.lg),
        ],
        for (int i = 0; i < rows; i++)
          Padding(
            padding: EdgeInsets.only(bottom: tokens.spacing.sm),
            child: SkeletonBox(
              width: double.infinity,
              height: rowHeight,
              borderRadius: radius,
            ),
          ),
      ],
    );
  }
}
