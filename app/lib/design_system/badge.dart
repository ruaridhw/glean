import 'package:flutter/material.dart';

import 'tokens.dart';

/// Tone for [GleanBadge], mirroring the RN `Badge` component's `BadgeTone`.
enum GleanBadgeTone { neutral, primary, warning, danger }

/// A tinted, non-interactive label pill — a count, a category tag, an "In
/// plan" status label.
///
/// This is **the one sanctioned bespoke primitive** in the design system
/// (AC-DS-12; FLUTTER_MIGRATION.md §4 names it explicitly as "likely to stay
/// bespoke"). It is not built from either close built-in:
/// - `Badge` (Material) is a notification-dot *overlay* anchored to another
///   widget — it has no "standalone tinted label" mode at all.
/// - `Chip` is themed and used elsewhere in this design system (see
///   `theme.dart`'s `chipTheme`) as the pill-chip button variant, but its
///   anatomy — ink response, selection state, optional avatar/delete-icon
///   slots — exists for an *interactive* element. A purely decorative label
///   fights that anatomy rather than using it.
///
/// Every colour and radius below comes from [Theme.of(context)]
/// (`ColorScheme` for the primary/warning/danger tones, [AppTokens] for the
/// pill radius), never a local constant (AC-DS-03).
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
