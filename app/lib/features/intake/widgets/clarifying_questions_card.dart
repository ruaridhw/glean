import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// Follow-up questions the shop-describe parse couldn't resolve on its own
/// (`ShoppingParseResponse.clarifyingQuestions`). Always empty for pantry
/// intake — rendered generically here so the shared review screen doesn't
/// special-case a destination just to skip it.
class ClarifyingQuestionsCard extends StatelessWidget {
  const ClarifyingQuestionsCard({super.key, required this.questions});

  final List<String> questions;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Padding(
      padding: EdgeInsets.fromLTRB(
        tokens.spacing.lg,
        tokens.spacing.sm,
        tokens.spacing.lg,
        0,
      ),
      child: Card(
        color: Theme.of(context).colorScheme.primaryContainer,
        child: Padding(
          padding: EdgeInsets.all(tokens.spacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              for (final String question in questions) Text(question),
            ],
          ),
        ),
      ),
    );
  }
}
