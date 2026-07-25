import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;
import 'package:glean/design_system/design_system.dart';

import '../presentation.dart';
import 'recipe_detail_sections.dart';

/// The recipe detail body shared by the saved-recipe screen and the unsaved
/// preview screen — everything below the app bar except the save/add-to-plan
/// affordances, which differ between the two callers.
class RecipeDetailView extends StatelessWidget {
  const RecipeDetailView({required this.data, super.key});

  final RecipeDetailData data;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        if (data.tags.isNotEmpty)
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: <Widget>[
              for (final String tag in data.tags)
                GleanBadge(label: tag, tone: GleanBadgeTone.primary),
            ],
          ),
        if (data.notSuitableFor.isNotEmpty) ...<Widget>[
          SizedBox(height: tokens.spacing.md),
          _NotSuitableForBanner(flags: data.notSuitableFor),
        ],
        SizedBox(height: tokens.spacing.lg),
        _StatsRow(data: data),
        if (data.sourceUrl != null) ...<Widget>[
          SizedBox(height: tokens.spacing.md),
          _SourceAttribution(sourceUrl: data.sourceUrl!),
        ],
        SizedBox(height: tokens.spacing.xl),
        Text('Ingredients', style: Theme.of(context).textTheme.titleMedium),
        SizedBox(height: tokens.spacing.sm),
        IngredientsSection(ingredients: data.ingredients),
        SizedBox(height: tokens.spacing.xl),
        Text('Instructions', style: Theme.of(context).textTheme.titleMedium),
        SizedBox(height: tokens.spacing.sm),
        InstructionsSection(steps: data.instructions),
      ],
    );
  }
}

/// AC-MEAL-04: allergen-ish information, made hard to miss rather than a
/// footnote — a warning-toned banner near the top of the screen, not folded
/// into the tag row.
class _NotSuitableForBanner extends StatelessWidget {
  const _NotSuitableForBanner({required this.flags});

  final List<String> flags;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: tokens.warningLight,
        borderRadius: BorderRadius.circular(tokens.radius.md),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(Icons.warning_amber_rounded, color: tokens.warning, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Not suitable for: ${flags.join(', ')}',
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(color: tokens.warning),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatsRow extends StatelessWidget {
  const _StatsRow({required this.data});

  final RecipeDetailData data;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Expanded(
          child: _StatCell(
            value: data.totalTimeMins != null
                ? '${data.totalTimeMins} min'
                : '—',
            label: 'Total',
          ),
        ),
        Expanded(
          child: _StatCell(
            value: data.activeTimeMins != null
                ? '${data.activeTimeMins} min'
                : '—',
            label: 'Active',
          ),
        ),
        Expanded(
          child: _StatCell(
            value: data.yieldCount != null ? '${data.yieldCount}' : '—',
            label: 'Serves',
          ),
        ),
      ],
    );
  }
}

class _StatCell extends StatelessWidget {
  const _StatCell({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    return Column(
      children: <Widget>[
        Text(value, style: textTheme.titleMedium),
        Text(label, style: textTheme.bodySmall),
      ],
    );
  }
}

/// AC-MEAL-05: tappable attribution for imported recipes. There is no
/// `url_launcher` in this project's dependency set (pubspec.yaml is
/// orchestrator-owned — see the final report's flagged follow-up), so
/// "tappable" copies the link to the clipboard rather than opening a
/// browser; the orchestrator should wire a real "open in browser" once that
/// dependency lands.
class _SourceAttribution extends StatelessWidget {
  const _SourceAttribution({required this.sourceUrl});

  final String sourceUrl;

  String get _host {
    try {
      final Uri uri = Uri.parse(sourceUrl);
      return uri.host.isEmpty ? sourceUrl : uri.host;
    } catch (_) {
      return sourceUrl;
    }
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return InkWell(
      borderRadius: BorderRadius.circular(tokens.radius.md),
      onTap: () async {
        await Clipboard.setData(ClipboardData(text: sourceUrl));
        if (context.mounted) {
          GleanSnackBar.show(context, 'Recipe link copied');
        }
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          children: <Widget>[
            Icon(
              Icons.link_rounded,
              size: 18,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                'Imported from $_host',
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
            Icon(
              Icons.copy_rounded,
              size: 16,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ],
        ),
      ),
    );
  }
}
