import 'package:flutter/material.dart';

import 'tokens.dart';

/// Tone for [GleanBadge].
enum GleanBadgeTone { neutral, primary, warning, danger }

/// A tinted, non-interactive label pill: a count, a category tag, a status label.
///
/// Bespoke because Material's `Badge` is a notification-dot overlay with no standalone mode, and
/// `Chip` is built for interactive elements. Colours and radius come from the theme.
class GleanBadge extends StatelessWidget {
  const GleanBadge({
    super.key,
    required this.label,
    this.tone = GleanBadgeTone.neutral,
  });

  final String label;
  final GleanBadgeTone tone;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    final AppTokens tokens = context.tokens;

    final (Color background, Color foreground) = switch (tone) {
      GleanBadgeTone.neutral => (
        colorScheme.surfaceContainerHighest,
        colorScheme.onSurfaceVariant,
      ),
      GleanBadgeTone.primary => (
        colorScheme.primaryContainer,
        colorScheme.onPrimaryContainer,
      ),
      GleanBadgeTone.warning => (tokens.warningLight, tokens.warning),
      GleanBadgeTone.danger => (
        colorScheme.errorContainer,
        colorScheme.onErrorContainer,
      ),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(tokens.radius.pill),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
          color: foreground,
          fontWeight: FontWeight.w700,
          letterSpacing: 0,
        ),
      ),
    );
  }
}
