/// The "N items need using up" nudge, shown when the pantry has items
/// expiring soon — encourages planning a dinner that uses them before
/// they're wasted.
library;

import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import '../presentation.dart';

class PlanExpiryBanner extends StatelessWidget {
  const PlanExpiryBanner({super.key, required this.nudge});

  final PlanExpiryNudge nudge;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    return Container(
      key: const ValueKey<String>('plan.expiryNudge'),
      padding: EdgeInsets.all(tokens.spacing.md),
      decoration: BoxDecoration(
        color: tokens.warningLight,
        borderRadius: BorderRadius.circular(tokens.radius.lg),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(Icons.schedule_rounded, color: tokens.warning, size: 20),
          SizedBox(width: tokens.spacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(
                  nudge.title,
                  style: textTheme.titleSmall?.copyWith(
                    color: tokens.warning,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  nudge.message,
                  style: textTheme.bodySmall?.copyWith(color: tokens.warning),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
