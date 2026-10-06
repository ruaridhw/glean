import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// Optional shopping hints, with an answer box per question (#96).
class ClarifyingQuestionsCard extends StatefulWidget {
  const ClarifyingQuestionsCard({
    super.key,
    required this.questions,
    this.onSubmit,
    this.pending = false,
  });

  final List<String> questions;
  final Future<void> Function(Map<String, String>)? onSubmit;
  final bool pending;

  @override
  State<ClarifyingQuestionsCard> createState() =>
      _ClarifyingQuestionsCardState();
}

class _ClarifyingQuestionsCardState extends State<ClarifyingQuestionsCard> {
  final Map<String, String> _answers = {};

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Card(
      color: Theme.of(context).colorScheme.primaryContainer,
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (final question in widget.questions) ...[
              Text(question),
              if (widget.onSubmit != null)
                Padding(
                  padding: EdgeInsets.only(
                    top: tokens.spacing.sm,
                    bottom: tokens.spacing.md,
                  ),
                  child: TextField(
                    key: ValueKey(question),
                    enabled: !widget.pending,
                    decoration: const InputDecoration(labelText: 'Answer'),
                    onChanged: (value) =>
                        setState(() => _answers[question] = value),
                  ),
                ),
            ],
            if (widget.onSubmit != null)
              FilledButton(
                onPressed:
                    widget.pending ||
                        !widget.questions.any(
                          (q) => (_answers[q] ?? '').trim().isNotEmpty,
                        )
                    ? null
                    : () => widget.onSubmit!({
                        for (final q in widget.questions) q: _answers[q] ?? '',
                      }),
                child: Text(
                  widget.pending
                      ? 'Updating suggestions'
                      : 'Update suggestions',
                ),
              ),
          ],
        ),
      ),
    );
  }
}
