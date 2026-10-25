/// The "This week" box at the top of the Plan tab: what the household tells the planner about this week.
///
/// Collapsed by default to one summary line. Generate sits in the box's top right and is there whether it is
/// open or not, so the default path is still one tap. Opening it shows the chips and the note. When the last
/// plan could not use the note, the box says so and the chips still applied.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';

import '../week_feedback.dart';
import 'generate_button.dart';

class ThisWeekBox extends ConsumerStatefulWidget {
  const ThisWeekBox({super.key, required this.weekStart});

  final DateTime weekStart;

  @override
  ConsumerState<ThisWeekBox> createState() => _ThisWeekBoxState();
}

class _ThisWeekBoxState extends ConsumerState<ThisWeekBox> {
  bool _expanded = false;
  late final TextEditingController _note;

  @override
  void initState() {
    super.initState();
    // The Plan tab keys the box by week, so one box only ever shows one week's note.
    _note = TextEditingController(
      text: ref.read(weekFeedbackProvider(widget.weekStart)).note,
    );
  }

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    final WeekFeedback feedback = ref.watch(
      weekFeedbackProvider(widget.weekStart),
    );
    // The saved note arrives a moment after the box first builds; show it unless the field already says it.
    ref.listen(weekFeedbackProvider(widget.weekStart), (
      WeekFeedback? previous,
      WeekFeedback next,
    ) {
      if (next.note != _note.text) _note.text = next.note;
    });
    final WeekFeedbackController controller = ref.read(
      weekFeedbackProvider(widget.weekStart).notifier,
    );

    // At large text sizes the title and Generate no longer fit side by side, so Generate drops below the title,
    // still on the right and still visible whether the box is open or not.
    final bool stacked = MediaQuery.textScalerOf(context).scale(1) > 1.5;
    final Widget toggle = Semantics(
      button: true,
      expanded: _expanded,
      child: InkWell(
        key: const ValueKey<String>('this-week-toggle'),
        borderRadius: BorderRadius.circular(tokens.radius.sm),
        onTap: () => setState(() => _expanded = !_expanded),
        child: Padding(
          padding: EdgeInsets.symmetric(vertical: tokens.spacing.xs),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Flexible(
                    child: Text(
                      'This week',
                      style: theme.textTheme.titleMedium,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(
                    _expanded
                        ? Icons.expand_less_rounded
                        : Icons.expand_more_rounded,
                    size: 20,
                  ),
                ],
              ),
              Text(
                feedback.summary,
                key: const ValueKey<String>('this-week-summary'),
                style: theme.textTheme.bodySmall,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );

    return Card(
      key: const ValueKey<String>('this-week-box'),
      shape: feedback.isEmpty
          ? null
          : RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(tokens.radius.lg),
              side: BorderSide(color: theme.colorScheme.outline),
            ),
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            if (stacked) ...<Widget>[
              toggle,
              SizedBox(height: tokens.spacing.sm),
              Align(
                alignment: Alignment.centerRight,
                child: PlanGenerateButton(weekStart: widget.weekStart),
              ),
            ] else
              Row(
                children: <Widget>[
                  Expanded(child: toggle),
                  SizedBox(width: tokens.spacing.sm),
                  PlanGenerateButton(weekStart: widget.weekStart),
                ],
              ),
            if (_expanded) ...<Widget>[
              SizedBox(height: tokens.spacing.md),
              Wrap(
                spacing: tokens.spacing.sm,
                runSpacing: tokens.spacing.sm,
                children: <Widget>[
                  for (final FeedbackChip chip in FeedbackChip.values)
                    FilterChip(
                      key: ValueKey<String>('chip-${chip.wire}'),
                      label: Text(chip.label),
                      selected: feedback.chips.contains(chip),
                      onSelected: (_) => controller.toggle(chip),
                    ),
                ],
              ),
              SizedBox(height: tokens.spacing.md),
              TextField(
                key: const ValueKey<String>('this-week-note'),
                controller: _note,
                maxLength: maxWeekNoteLength,
                minLines: 1,
                maxLines: 3,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(
                  hintText: '+ Add a note',
                  counterText: '',
                ),
                onChanged: controller.setNote,
              ),
            ],
            if (feedback.noteUnused && feedback.hasNote) ...<Widget>[
              SizedBox(height: tokens.spacing.sm),
              Text(
                "Couldn't use that note. Your chips still apply.",
                key: const ValueKey<String>('this-week-note-unused'),
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
