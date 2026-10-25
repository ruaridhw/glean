/// The "This week" box at the top of the Plan tab: what the household tells the planner about the week shown.
///
/// Two halves that read as one box. The header ([ThisWeekHeader]) is pinned above the plan, so Generate, in its
/// top right, is on screen in both box states however far the week scrolls; it is collapsed by default to one
/// summary line. Opening it shows the panel ([ThisWeekPanel]) at the top of the scrolling plan: the chips and the
/// note. When the last plan could not use the note, the panel says so and the chips still applied.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';

import '../presentation.dart';
import '../week_feedback.dart';
import 'generate_button.dart';

/// Whether a week's box is open. In memory only: every launch, and every week, starts closed.
final thisWeekBoxOpenProvider =
    NotifierProvider.family<ThisWeekBoxOpen, bool, DateTime>(
      ThisWeekBoxOpen.new,
    );

class ThisWeekBoxOpen extends Notifier<bool> {
  ThisWeekBoxOpen(this.weekStart);

  final DateTime weekStart;

  @override
  bool build() => false;

  void toggle() => state = !state;
}

/// The box's two corners that meet the other half when it is open, squared off so the two read as one box.
BorderRadius _boxCorners(
  AppTokens tokens, {
  required bool top,
  required bool open,
}) {
  final Radius round = Radius.circular(tokens.radius.lg);
  const Radius square = Radius.zero;
  return top
      ? BorderRadius.vertical(top: round, bottom: open ? square : round)
      : BorderRadius.vertical(top: square, bottom: round);
}

ShapeBorder _boxShape(
  AppTokens tokens,
  ThemeData theme,
  WeekFeedback feedback, {
  required bool top,
  required bool open,
}) => RoundedRectangleBorder(
  borderRadius: _boxCorners(tokens, top: top, open: open),
  side: feedback.isEmpty
      ? BorderSide.none
      : BorderSide(color: theme.colorScheme.outline),
);

/// The box's header, pinned above the plan so Generate is on screen however far the week scrolls: the week's
/// title, the one-line summary that opens and closes the box, and Generate in the top right.
class ThisWeekHeader extends ConsumerWidget {
  const ThisWeekHeader({super.key, required this.weekStart});

  final DateTime weekStart;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    final WeekFeedback feedback = ref.watch(weekFeedbackProvider(weekStart));
    final bool open = ref.watch(thisWeekBoxOpenProvider(weekStart));

    // At large text sizes the title and Generate no longer fit side by side, so Generate drops below the title,
    // still on the right and still visible whether the box is open or not.
    final bool stacked = MediaQuery.textScalerOf(context).scale(1) > 1.5;
    final Widget toggle = Semantics(
      button: true,
      expanded: open,
      child: InkWell(
        key: const ValueKey<String>('this-week-toggle'),
        borderRadius: BorderRadius.circular(tokens.radius.sm),
        onTap: ref.read(thisWeekBoxOpenProvider(weekStart).notifier).toggle,
        child: Padding(
          padding: EdgeInsets.symmetric(vertical: tokens.spacing.xs),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Flexible(
                    child: Text(
                      // The week this box steers: "This week" for the current one, else its dates.
                      isCurrentWeek(weekStart)
                          ? 'This week'
                          : weekRangeLabel(weekStart),
                      key: const ValueKey<String>('this-week-title'),
                      style: theme.textTheme.titleMedium,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(
                    open
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
      margin: EdgeInsets.zero,
      shape: _boxShape(tokens, theme, feedback, top: true, open: open),
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            stacked
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      toggle,
                      SizedBox(height: tokens.spacing.sm),
                      Align(
                        alignment: Alignment.centerRight,
                        child: PlanGenerateButton(weekStart: weekStart),
                      ),
                    ],
                  )
                : Row(
                    children: <Widget>[
                      Expanded(child: toggle),
                      SizedBox(width: tokens.spacing.sm),
                      PlanGenerateButton(weekStart: weekStart),
                    ],
                  ),
            // In the header, so it shows with the box closed too, which is how every launch starts.
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

/// The open half of the box, at the top of the scrolling plan under the pinned header: the chips and the note.
/// "Couldn't use that note" lives in the header, so it shows either way. Nothing when the box is closed.
class ThisWeekPanel extends ConsumerWidget {
  const ThisWeekPanel({super.key, required this.weekStart});

  final DateTime weekStart;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bool open = ref.watch(thisWeekBoxOpenProvider(weekStart));
    return open ? _OpenPanel(weekStart: weekStart) : const SizedBox.shrink();
  }
}

class _OpenPanel extends ConsumerStatefulWidget {
  const _OpenPanel({required this.weekStart});

  final DateTime weekStart;

  @override
  ConsumerState<_OpenPanel> createState() => _OpenPanelState();
}

class _OpenPanelState extends ConsumerState<_OpenPanel> {
  late final TextEditingController _note;

  @override
  void initState() {
    super.initState();
    // The Plan tab keys the panel by week, so one panel only ever shows one week's note.
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

    return Card(
      key: const ValueKey<String>('this-week-panel'),
      margin: EdgeInsets.zero,
      shape: _boxShape(tokens, theme, feedback, top: false, open: true),
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          tokens.spacing.md,
          0,
          tokens.spacing.md,
          tokens.spacing.md,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
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
                    // The gate's dark fill and a check, so a chip that is on cannot be mistaken for one off.
                    showCheckmark: true,
                    selectedColor: theme.colorScheme.inverseSurface,
                    checkmarkColor: theme.colorScheme.onInverseSurface,
                    labelStyle: feedback.chips.contains(chip)
                        ? TextStyle(color: theme.colorScheme.onInverseSurface)
                        : null,
                  ),
              ],
            ),
            SizedBox(height: tokens.spacing.md),
            TextField(
              key: const ValueKey<String>('this-week-note'),
              controller: _note,
              // The bound counts code points, the unit the backend counts (`clipWeekNote`).
              inputFormatters: const <TextInputFormatter>[_WeekNoteFormatter()],
              minLines: 1,
              maxLines: 3,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(hintText: '+ Add a note'),
              onChanged: controller.setNote,
            ),
          ],
        ),
      ),
    );
  }
}

/// Keeps the note within [maxWeekNoteLength] code points: an edit that would cross it is refused whole, so
/// typing into the middle of a full note neither drops characters from its end nor moves the cursor.
class _WeekNoteFormatter extends TextInputFormatter {
  const _WeekNoteFormatter();

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) => newValue.text.runes.length > maxWeekNoteLength ? oldValue : newValue;
}
