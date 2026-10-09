/// Week pagination (AC-PLAN-02): forward and backward arrows around the
/// current week's label — RN had no equivalent at all, since "This Week"
/// was the only week it could ever show.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';

import '../presentation.dart';

class PlanWeekPager extends ConsumerWidget {
  const PlanWeekPager({
    super.key,
    required this.weekStart,
    required this.onPrevious,
    required this.onNext,
  });

  final DateTime weekStart;
  final VoidCallback onPrevious;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bool current = isCurrentWeek(weekStart);
    final String label = current
        ? 'This week · ${weekRangeLabel(weekStart)}'
        : weekRangeLabel(weekStart);

    void tap(VoidCallback action) {
      ref.read(hapticsProvider).lightImpact();
      action();
    }

    return Row(
      children: <Widget>[
        IconButton(
          onPressed: () => tap(onPrevious),
          icon: const Icon(Icons.chevron_left_rounded),
          tooltip: 'Previous week',
        ),
        Expanded(
          child: Center(
            child: Text(
              label,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleSmall,
            ),
          ),
        ),
        IconButton(
          onPressed: () => tap(onNext),
          icon: const Icon(Icons.chevron_right_rounded),
          tooltip: 'Next week',
        ),
      ],
    );
  }
}
