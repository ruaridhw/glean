/// The agent's one question, as a focused step that replaces the working state: the question, its options as
/// chips (one at most), an optional note, and "Skip, just plan" beside Send. Skip is always there, because the
/// question is a hint and never a reason to stop planning.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:glean/api/models/meal_plan_session.dart';
import 'package:glean/design_system/design_system.dart';

/// The longest note the backend takes; it screens the note before the agent reads it.
const int maxQuestionNoteLength = 500;

class QuestionStep extends StatefulWidget {
  const QuestionStep({
    super.key,
    required this.question,
    required this.onSend,
    required this.onSkip,
    this.sending = false,
    this.error,
  });

  final MealPlanSessionQuestion question;

  /// True while the answer is on its way: both buttons wait, and the choice stays as it is.
  final bool sending;

  /// Why the last send failed; Send and Skip stay available to try again.
  final String? error;
  final void Function({String? option, String? note}) onSend;
  final VoidCallback onSkip;

  @override
  State<QuestionStep> createState() => _QuestionStepState();
}

class _QuestionStepState extends State<QuestionStep> {
  final TextEditingController _note = TextEditingController();
  String? _option;

  /// Send has something to send once an option is tapped or a note typed; one tap is enough either way.
  bool get _canSend => _option != null || _note.text.trim().isNotEmpty;

  @override
  void initState() {
    super.initState();
    _note.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  void _send() {
    if (!_canSend || widget.sending) return;
    final String note = _note.text.trim();
    widget.onSend(option: _option, note: note.isEmpty ? null : note);
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Column(
      children: <Widget>[
        Expanded(
          child: Center(
            child: SingleChildScrollView(
              padding: EdgeInsets.all(tokens.spacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Text(
                    'Glean has a question before it finishes',
                    style: textTheme.bodyMedium?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                  SizedBox(height: tokens.spacing.sm),
                  Text(widget.question.question, style: textTheme.titleLarge),
                  SizedBox(height: tokens.spacing.md),
                  Wrap(
                    spacing: tokens.spacing.sm,
                    runSpacing: tokens.spacing.sm,
                    children: <Widget>[
                      for (final String option in widget.question.options)
                        ChoiceChip(
                          label: Text(option),
                          selected: _option == option,
                          // Tapping the chosen option again clears it, so a note alone can still be sent.
                          onSelected: (bool selected) => setState(
                            () => _option = selected ? option : null,
                          ),
                        ),
                    ],
                  ),
                  SizedBox(height: tokens.spacing.md),
                  TextField(
                    controller: _note,
                    minLines: 1,
                    maxLines: 3,
                    textCapitalization: TextCapitalization.sentences,
                    inputFormatters: <TextInputFormatter>[
                      LengthLimitingTextInputFormatter(maxQuestionNoteLength),
                    ],
                    decoration: const InputDecoration(
                      hintText: 'Add a note (optional)',
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        if (widget.error case final String error)
          Padding(
            padding: EdgeInsets.symmetric(horizontal: tokens.spacing.lg),
            child: SizedBox(
              width: double.infinity,
              child: Text(
                error,
                style: textTheme.bodyMedium?.copyWith(color: colorScheme.error),
              ),
            ),
          ),
        // A Wrap, like the screen's own bar: at a narrow width with large text the two actions stack instead of
        // overflowing.
        SafeArea(
          minimum: EdgeInsets.all(tokens.spacing.md),
          child: SizedBox(
            width: double.infinity,
            child: Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: tokens.spacing.sm,
              runSpacing: tokens.spacing.sm,
              children: <Widget>[
                OutlinedButton(
                  onPressed: widget.sending ? null : widget.onSkip,
                  child: const Text('Skip, just plan'),
                ),
                FilledButton(
                  onPressed: _canSend && !widget.sending ? _send : null,
                  child: const Text('Send'),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
