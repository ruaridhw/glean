/// Cards for the proposal review: a meal the generation suggested, and a meal already in the week that the
/// planner offered an alternative for. Both put Swap on the card and open their panel in place, with the
/// panel's buttons on one row at the bottom (V3 direction A). A suggested meal's panel also offers "Find
/// another", which works in place on that card (V10 direction A); a meal already in the week never offers it,
/// because a swap never replaces a planned meal.
library;

import 'package:flutter/material.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/design_system/design_system.dart';

import '../proposal_labels.dart';
import '../providers/generate_week_controller.dart' show FindAnotherState;

/// Progress lines as they arrive: a tick for each finished line and a spinner on the newest. The working screen
/// and a card finding another meal draw them the same way.
class ProposalProgressLines extends StatelessWidget {
  const ProposalProgressLines({
    super.key,
    required this.lines,
    this.waiting = 'Getting started',
  });

  final List<String> lines;

  /// What shows before the first line arrives.
  final String waiting;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    if (lines.isEmpty) {
      return Row(
        children: <Widget>[
          const SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          SizedBox(width: tokens.spacing.sm),
          Text(
            waiting,
            style: textTheme.bodyMedium?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        for (int i = 0; i < lines.length; i++)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                SizedBox(
                  width: 20,
                  child: i == lines.length - 1
                      ? const Padding(
                          padding: EdgeInsets.only(top: 2),
                          child: SizedBox(
                            width: 12,
                            height: 12,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        )
                      : Icon(
                          Icons.check_rounded,
                          size: 16,
                          color: colorScheme.primary,
                        ),
                ),
                Expanded(child: Text(lines[i], style: textTheme.bodyMedium)),
              ],
            ),
          ),
      ],
    );
  }
}

/// What a meal is: protein, carb, dish type and hands-on time, as V3's design places them (direction A,
/// "fish · rice · traybake · 20 min"). The values are measured by V5's enrichment; a meal with nothing measured
/// yet, or nothing the model was sure enough about, gets no row at all rather than an empty chip or a guess.
class ProposalAttributeLabels extends StatelessWidget {
  const ProposalAttributeLabels({super.key, required this.attributes});

  final MealPlanAttributes? attributes;

  @override
  Widget build(BuildContext context) {
    final List<String> labels = proposalLabels(attributes);
    if (labels.isEmpty) {
      return const SizedBox.shrink();
    }
    return Wrap(
      spacing: context.tokens.spacing.xs,
      runSpacing: context.tokens.spacing.xs,
      children: <Widget>[
        for (final String label in labels) GleanBadge(label: label),
      ],
    );
  }
}

/// Open swap panel: the server's one alternative, taken in place, and for a suggested meal "Find another",
/// which opens an optional note field and sends a swap. Every button sits on one row at the bottom.
class ProposalSwapPanel extends StatefulWidget {
  const ProposalSwapPanel({
    super.key,
    required this.alternative,
    required this.onUseAlternative,
    this.onFindAnother,
    this.findAnotherEnabled = true,
  });

  final MealPlanRecipe? alternative;
  final VoidCallback onUseAlternative;

  /// Sends the swap with the note typed, or null. Absent on a meal already in the week.
  final ValueChanged<String?>? onFindAnother;

  /// False while another card's swap runs: one swap at a time.
  final bool findAnotherEnabled;

  @override
  State<ProposalSwapPanel> createState() => _ProposalSwapPanelState();
}

class _ProposalSwapPanelState extends State<ProposalSwapPanel> {
  final TextEditingController _note = TextEditingController();
  bool _writingNote = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    final MealPlanRecipe? alternative = widget.alternative;
    final ValueChanged<String?>? onFindAnother = widget.onFindAnother;
    return Container(
      margin: EdgeInsets.only(top: tokens.spacing.sm),
      padding: EdgeInsets.all(tokens.spacing.md),
      decoration: BoxDecoration(
        border: Border.all(color: colorScheme.outline, width: 2),
        borderRadius: BorderRadius.circular(tokens.radius.md),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (_writingNote) ...<Widget>[
            Text('Find another', style: textTheme.titleSmall),
            SizedBox(height: tokens.spacing.sm),
            TextField(
              controller: _note,
              autofocus: true,
              maxLength: 500,
              minLines: 1,
              maxLines: 3,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _send(),
              decoration: const InputDecoration(
                labelText: 'Anything in mind? (optional)',
                hintText: 'Something lighter, maybe fish',
                counterText: '',
              ),
            ),
          ] else if (alternative != null) ...<Widget>[
            Text(
              'Alternative: ${alternative.title}',
              style: textTheme.titleSmall,
            ),
            if (proposalLabels(alternative.attributes).isNotEmpty) ...<Widget>[
              SizedBox(height: tokens.spacing.xs),
              ProposalAttributeLabels(attributes: alternative.attributes),
            ],
            if (alternative.reason.isNotEmpty) ...<Widget>[
              SizedBox(height: tokens.spacing.xs),
              Text(
                alternative.reason,
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
          SizedBox(height: tokens.spacing.sm),
          // Wrap constrains the buttons to the card's width, so a long label wraps instead of overflowing at
          // large text scales. The panel's actions stay on one row while they fit.
          Wrap(
            alignment: WrapAlignment.end,
            spacing: tokens.spacing.sm,
            runSpacing: tokens.spacing.sm,
            children: <Widget>[
              if (_writingNote) ...<Widget>[
                TextButton(
                  onPressed: () => setState(() => _writingNote = false),
                  child: const Text('Cancel'),
                ),
                FilledButton(onPressed: _send, child: const Text('Send')),
              ] else ...<Widget>[
                if (alternative != null)
                  OutlinedButton(
                    onPressed: widget.onUseAlternative,
                    child: const Text('Use alternative'),
                  ),
                if (onFindAnother != null)
                  OutlinedButton(
                    onPressed: widget.findAnotherEnabled
                        ? () => setState(() => _writingNote = true)
                        : null,
                    child: const Text('Find another'),
                  ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  void _send() {
    final ValueChanged<String?>? onFindAnother = widget.onFindAnother;
    if (onFindAnother == null || !widget.findAnotherEnabled) return;
    final String note = _note.text.trim();
    onFindAnother(note.isEmpty ? null : note);
  }
}

/// The widest a card's Swap / Swap back button may be. Uncapped, "Swap back" at 2x text is wider than the space
/// beside the title on a 320 px screen and the title Row overflows; capped, its label wraps instead.
double _swapButtonMaxWidth(BuildContext context) =>
    MediaQuery.sizeOf(context).width * 0.4;

/// One suggested meal. [meal] is what the card currently shows (the original, a swapped alternative, or a
/// replacement "Find another" brought in); [alternative] is the server's alternative, which is what Swap offers.
///
/// While [finding] is set the card works in place: its own progress lines, the note it was sent with, and no
/// Swap. [notice] is one plain line from the last swap (an error, nothing else fits, or a dropped note).
class ProposalMealCard extends StatelessWidget {
  const ProposalMealCard({
    super.key,
    required this.meal,
    required this.alternative,
    required this.swapped,
    required this.swapOpen,
    required this.onToggleSwap,
    required this.onUseAlternative,
    this.onFindAnother,
    this.findAnotherEnabled = true,
    this.finding,
    this.notice,
    this.replaced = false,
    this.onUndoReplacement,
    this.onCancelFindAnother,
  });

  final MealPlanRecipe meal;
  final MealPlanRecipe? alternative;
  final bool swapped;
  final bool swapOpen;
  final VoidCallback onToggleSwap;
  final VoidCallback onUseAlternative;
  final ValueChanged<String?>? onFindAnother;
  final bool findAnotherEnabled;
  final FindAnotherState? finding;
  final String? notice;

  /// True when "Find another" brought [meal] in, so the card offers Undo swap.
  final bool replaced;
  final VoidCallback? onUndoReplacement;

  /// Stops the "Find another" this card is working on and puts the card back as it was.
  final VoidCallback? onCancelFindAnother;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    final FindAnotherState? finding = this.finding;
    if (finding != null) {
      return Card(
        child: Padding(
          padding: EdgeInsets.all(tokens.spacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text('Finding another…', style: textTheme.titleMedium),
              if (finding.note != null) ...<Widget>[
                SizedBox(height: tokens.spacing.xs),
                Text(
                  'Your note: "${finding.note}"',
                  style: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
              SizedBox(height: tokens.spacing.sm),
              ProposalProgressLines(
                lines: finding.progress,
                waiting: 'Asking for another dinner',
              ),
              if (onCancelFindAnother != null)
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: onCancelFindAnother,
                    child: const Text('Cancel'),
                  ),
                ),
            ],
          ),
        ),
      );
    }
    final bool canSwap = alternative != null || onFindAnother != null;
    return Card(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Expanded(child: Text(meal.title, style: textTheme.titleMedium)),
                if (canSwap)
                  ConstrainedBox(
                    constraints: BoxConstraints(
                      maxWidth: _swapButtonMaxWidth(context),
                    ),
                    child: TextButton(
                      onPressed: onToggleSwap,
                      child: Text(swapped ? 'Swap back' : 'Swap'),
                    ),
                  ),
              ],
            ),
            if (proposalLabels(meal.attributes).isNotEmpty) ...<Widget>[
              SizedBox(height: tokens.spacing.xs),
              ProposalAttributeLabels(attributes: meal.attributes),
            ],
            if (meal.reason.isNotEmpty) ...<Widget>[
              SizedBox(height: tokens.spacing.sm),
              Text(
                meal.reason,
                style: textTheme.bodyMedium?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ],
            if (notice != null) ...<Widget>[
              SizedBox(height: tokens.spacing.xs),
              Text(
                notice!,
                style: textTheme.bodySmall?.copyWith(color: colorScheme.error),
              ),
            ],
            if (replaced && onUndoReplacement != null && !swapOpen)
              Align(
                alignment: Alignment.centerRight,
                child: Padding(
                  padding: EdgeInsets.only(top: tokens.spacing.sm),
                  child: OutlinedButton(
                    onPressed: onUndoReplacement,
                    child: const Text('Undo swap'),
                  ),
                ),
              ),
            if (swapOpen && canSwap)
              ProposalSwapPanel(
                alternative: alternative,
                onUseAlternative: onUseAlternative,
                onFindAnother: onFindAnother,
                findAnotherEnabled: findAnotherEnabled,
              ),
          ],
        ),
      ),
    );
  }
}

/// A meal already in the week: greyed, tagged, and swappable through `planned_alternatives`. Generation never
/// replaces it on its own (ADR 0020); only the user's own swap, saved with Add to plan, changes the entry.
class ProposalPlannedCard extends StatelessWidget {
  const ProposalPlannedCard({
    super.key,
    required this.title,
    required this.alternative,
    required this.swapped,
    required this.swapOpen,
    required this.onToggleSwap,
    required this.onUseAlternative,
  });

  final String title;
  final MealPlanRecipe? alternative;
  final bool swapped;
  final bool swapOpen;
  final VoidCallback onToggleSwap;
  final VoidCallback onUseAlternative;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Opacity(
      opacity: 0.55,
      child: Card(
        child: Padding(
          padding: EdgeInsets.all(tokens.spacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Expanded(child: Text(title, style: textTheme.titleMedium)),
                  if (alternative != null)
                    ConstrainedBox(
                      constraints: BoxConstraints(
                        maxWidth: _swapButtonMaxWidth(context),
                      ),
                      child: TextButton(
                        onPressed: onToggleSwap,
                        child: Text(swapped ? 'Swap back' : 'Swap'),
                      ),
                    ),
                ],
              ),
              SizedBox(height: tokens.spacing.xs),
              Align(
                alignment: Alignment.centerLeft,
                child: Container(
                  padding: EdgeInsets.symmetric(
                    horizontal: tokens.spacing.sm,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    border: Border.all(color: colorScheme.outline),
                    borderRadius: BorderRadius.circular(tokens.radius.sm),
                  ),
                  child: Text('already planned', style: textTheme.labelSmall),
                ),
              ),
              if (swapOpen && alternative != null)
                ProposalSwapPanel(
                  alternative: alternative!,
                  onUseAlternative: onUseAlternative,
                ),
            ],
          ),
        ),
      ),
    );
  }
}
