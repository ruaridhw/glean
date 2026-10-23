/// The V3 proposal screen (direction A, full-screen review): Generate opens it immediately in its working
/// state, progress lines arrive on the poll, and the proposal is reviewed before anything is saved. Add to
/// plan commits the whole review in one transaction; Back discards it and cancels the session.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/providers/clock_provider.dart';
import 'package:glean/data/providers/plan_providers.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/diagnostics/diagnostics.dart';
import 'package:glean/logging/logging.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';

import 'generate_failure.dart';
import 'presentation.dart';
import 'providers/generate_week_controller.dart';
import 'widgets/proposal_meal_card.dart';

class ProposalScreen extends ConsumerStatefulWidget {
  const ProposalScreen({super.key});

  @override
  ConsumerState<ProposalScreen> createState() => _ProposalScreenState();
}

class _ProposalScreenState extends ConsumerState<ProposalScreen> {
  /// Which new meal's swap panel is open, by index in the server's suggestion list.
  final Set<int> _openSwaps = <int>{};

  /// Which already-planned meal's swap panel is open, by plan entry id.
  final Set<int> _openPlannedSwaps = <int>{};

  /// Back and Cancel both discard and cancel; one in flight is enough.
  bool _leaving = false;

  GenerateWeekController get _controller =>
      ref.read(generateWeekControllerProvider.notifier);

  /// Discard whatever is on screen and ask the server to cancel the session. The screen closes after the
  /// DELETE is sent, as the wireframe's Cancel dictates.
  ///
  /// While Add to plan is resolving recipe details this aborts it: the controller drops the save before its
  /// transaction starts. Once the transaction has started Back is ignored, so a discarded review can never
  /// commit underneath the user.
  Future<void> _close() async {
    if (_leaving) return;
    final GenerateProposalState state = ref.read(
      generateWeekControllerProvider,
    );
    if (state.saving && state.committing) return;
    _leaving = true;
    await _controller.cancel();
    if (mounted) context.pop();
  }

  Future<void> _addToPlan() async {
    final int count = await _controller.addToPlan();
    if (!mounted || _leaving) return;
    // A failed save keeps the failed face and its copy on screen: nothing was added.
    if (ref.read(generateWeekControllerProvider).phase ==
        GenerateProposalPhase.failed) {
      return;
    }
    _leaveAfterSave(count);
  }

  /// Retry on a failed save stays on the review and re-runs the transaction; a successful one closes it like
  /// Add to plan does. Retry on a failed run stays on the working face, so there is nothing to close.
  Future<void> _retry() async {
    final bool wasSave =
        ref.read(generateWeekControllerProvider).result != null;
    final int count = await _controller.retry();
    if (!mounted || _leaving || !wasSave) return;
    if (ref.read(generateWeekControllerProvider).phase ==
        GenerateProposalPhase.failed) {
      return;
    }
    _leaveAfterSave(count);
  }

  void _leaveAfterSave(int count) {
    if (!mounted || _leaving) return;
    _leaving = true;
    ref.read(hapticsProvider).mediumImpact();
    GleanSnackBar.show(
      context,
      count == 0
          ? 'Week updated.'
          : '${count == 1 ? '1 dinner' : '$count dinners'} added to plan · '
                'missing ingredients went to your shopping list',
    );
    context.pop();
  }

  void _openSettings() => context.goNamed(AppRoutes.settings.name);

  Future<void> _report() async {
    final ScaffoldMessengerState messenger = ScaffoldMessenger.of(context);
    final GleanLogger? logger = ref.read(gleanLoggerProvider);
    try {
      final String prefix = await ref.read(diagnosticsExportProvider)();
      GleanSnackBar.showOn(messenger, 'Diagnostics exported to $prefix');
    } catch (error) {
      await logger?.error('export diagnostics failed: ${describeError(error)}');
      GleanSnackBar.showOn(
        messenger,
        'Could not export diagnostics. Try again.',
      );
    }
  }

  void _toggle(Set<int> open, int key) {
    setState(() {
      if (!open.remove(key)) open.add(key);
    });
  }

  @override
  Widget build(BuildContext context) {
    final GenerateProposalState state = ref.watch(
      generateWeekControllerProvider,
    );
    final DateTime weekStart =
        state.weekStart ?? startOfWeek(ref.read(clockProvider)());
    final bool canLeave = state.phase != GenerateProposalPhase.idle;

    return PopScope(
      // Back is a discard, not an escape that leaves a session running.
      canPop: !canLeave,
      onPopInvokedWithResult: (bool didPop, Object? result) {
        if (!didPop) unawaited(_close());
      },
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_rounded),
            tooltip: 'Back',
            onPressed: () => unawaited(_close()),
          ),
          title: const Text('Plan this week'),
          actions: <Widget>[
            Padding(
              padding: EdgeInsets.only(right: context.tokens.spacing.md),
              child: Center(
                child: Text(
                  weekRangeLabel(weekStart),
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            ),
          ],
        ),
        body: SafeArea(child: _body(state)),
        bottomNavigationBar: _bottomBar(state),
      ),
    );
  }

  Widget _body(GenerateProposalState state) {
    switch (state.phase) {
      case GenerateProposalPhase.idle:
        return const Center(child: Text('Nothing to review.'));
      case GenerateProposalPhase.working:
        return _WorkingBody(slots: state.slots, progress: state.progress);
      case GenerateProposalPhase.failed:
        return _FailedBody(
          failure:
              state.failure ??
              const GenerateFailure(GenerateFailureKind.unknown),
          saving: state.saving,
          onRetry: () => unawaited(_retry()),
          onOpenSettings: _openSettings,
          onReport: () => unawaited(_report()),
        );
      case GenerateProposalPhase.proposal:
        final MealPlanResponse result = state.result!;
        if (result.suggestions.isEmpty) {
          return _NoMealsBody(
            message: const GenerateFailure(
              GenerateFailureKind.noEligibleRecipes,
            ).message,
            onOpenSettings: _openSettings,
          );
        }
        return _proposalBody(state, result);
    }
  }

  Widget _proposalBody(GenerateProposalState state, MealPlanResponse result) {
    final AppTokens tokens = context.tokens;
    final DateTime? weekStart = state.weekStart;
    final List<MealPlanEntryView> planned = weekStart == null
        ? const <MealPlanEntryView>[]
        : (ref.watch(planWeekProvider(weekStart)).value ??
                  const <MealPlanEntryView>[])
              .where((MealPlanEntryView entry) => !entry.isCooked)
              .toList();
    final Map<String, MealPlanRecipe> plannedAlternatives =
        <String, MealPlanRecipe>{
          for (final MealPlanPlannedAlternative item
              in result.plannedAlternatives)
            item.externalId: item.alternative,
        };

    return ListView(
      padding: EdgeInsets.all(tokens.spacing.lg),
      children: <Widget>[
        if (result.weekSummary.isNotEmpty) ...<Widget>[
          _SummaryCard(summary: result.weekSummary),
          SizedBox(height: tokens.spacing.sm),
        ],
        for (final MealPlanEntryView entry in planned) ...<Widget>[
          ProposalPlannedCard(
            key: ValueKey<String>('planned-${entry.id}'),
            title: state.plannedSwaps[entry.id]?.title ?? entry.recipeTitle,
            alternative: plannedAlternatives[entry.externalIdSnapshot],
            swapped: state.plannedSwaps.containsKey(entry.id),
            swapOpen: _openPlannedSwaps.contains(entry.id),
            onToggleSwap: () {
              // "Swap back" is instant and local, exactly like taking the alternative; only the unswapped
              // card opens the panel.
              if (state.plannedSwaps.containsKey(entry.id)) {
                final MealPlanRecipe? alternative =
                    plannedAlternatives[entry.externalIdSnapshot];
                if (alternative != null) {
                  _controller.swapPlanned(entry.id, alternative);
                }
                setState(() => _openPlannedSwaps.remove(entry.id));
              } else {
                _toggle(_openPlannedSwaps, entry.id);
              }
            },
            onUseAlternative: () {
              final MealPlanRecipe? alternative =
                  plannedAlternatives[entry.externalIdSnapshot];
              if (alternative == null) return;
              _controller.swapPlanned(entry.id, alternative);
              setState(() => _openPlannedSwaps.remove(entry.id));
            },
          ),
          SizedBox(height: tokens.spacing.sm),
        ],
        for (
          int index = 0;
          index < result.suggestions.length;
          index++
        ) ...<Widget>[
          ProposalMealCard(
            key: ValueKey<String>('suggestion-$index'),
            meal: state.suggestionAt(index),
            alternative: result.suggestions[index].alternative,
            swapped: state.isSwapped(index),
            swapOpen: _openSwaps.contains(index),
            onToggleSwap: () {
              if (state.isSwapped(index)) {
                _controller.swapSuggestion(index);
                setState(() => _openSwaps.remove(index));
              } else {
                _toggle(_openSwaps, index);
              }
            },
            onUseAlternative: () {
              _controller.swapSuggestion(index);
              setState(() => _openSwaps.remove(index));
            },
          ),
          SizedBox(height: tokens.spacing.sm),
        ],
      ],
    );
  }

  Widget _bottomBar(GenerateProposalState state) {
    final AppTokens tokens = context.tokens;
    final List<Widget> actions;
    switch (state.phase) {
      case GenerateProposalPhase.working:
        actions = <Widget>[
          OutlinedButton(
            onPressed: () => unawaited(_close()),
            child: const Text('Cancel'),
          ),
        ];
      case GenerateProposalPhase.proposal when state.hasProposal:
        final int count = state.result!.suggestions.length;
        actions = <Widget>[
          OutlinedButton(
            onPressed: state.saving ? null : () => unawaited(_close()),
            child: const Text('Discard'),
          ),
          SizedBox(width: tokens.spacing.sm),
          FilledButton(
            onPressed: state.saving ? null : () => unawaited(_addToPlan()),
            child: Text(
              count == 0
                  ? 'Save changes'
                  : 'Add ${count == 1 ? '1 dinner' : '$count dinners'} to plan',
            ),
          ),
        ];
      case GenerateProposalPhase.proposal:
      case GenerateProposalPhase.failed:
      case GenerateProposalPhase.idle:
        actions = <Widget>[
          OutlinedButton(
            onPressed: () => unawaited(_close()),
            child: const Text('Close'),
          ),
        ];
    }
    // A Wrap, not a Row: at a 320 px screen with 2x text the two actions cannot share one line, and a Row
    // overflows instead of stacking them.
    return SafeArea(
      minimum: EdgeInsets.all(tokens.spacing.md),
      child: Wrap(
        alignment: WrapAlignment.end,
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: tokens.spacing.sm,
        runSpacing: tokens.spacing.sm,
        children: <Widget>[
          if (state.saving &&
              state.phase == GenerateProposalPhase.proposal) ...<Widget>[
            const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          ],
          ...actions,
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.summary});

  final String summary;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    return Card(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('This week', style: textTheme.titleMedium),
            SizedBox(height: tokens.spacing.xs),
            Text(
              summary,
              style: textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _WorkingBody extends StatelessWidget {
  const _WorkingBody({required this.slots, required this.progress});

  final int slots;
  final List<String> progress;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return ListView(
      padding: EdgeInsets.all(tokens.spacing.lg),
      children: <Widget>[
        Card(
          child: Padding(
            padding: EdgeInsets.all(tokens.spacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'Planning ${slots == 1 ? '1 dinner' : '$slots dinners'}…',
                  style: textTheme.titleMedium,
                ),
                SizedBox(height: tokens.spacing.sm),
                if (progress.isEmpty)
                  Row(
                    children: <Widget>[
                      const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      SizedBox(width: tokens.spacing.sm),
                      Text(
                        'Getting started',
                        style: textTheme.bodyMedium?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  )
                else
                  for (int i = 0; i < progress.length; i++)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          SizedBox(
                            width: 20,
                            child: i == progress.length - 1
                                ? const Padding(
                                    padding: EdgeInsets.only(top: 2),
                                    child: SizedBox(
                                      width: 12,
                                      height: 12,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                      ),
                                    ),
                                  )
                                : Icon(
                                    Icons.check_rounded,
                                    size: 16,
                                    color: colorScheme.primary,
                                  ),
                          ),
                          Expanded(
                            child: Text(
                              progress[i],
                              style: textTheme.bodyMedium,
                            ),
                          ),
                        ],
                      ),
                    ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _FailedBody extends StatelessWidget {
  const _FailedBody({
    required this.failure,
    required this.saving,
    required this.onRetry,
    required this.onOpenSettings,
    required this.onReport,
  });

  final GenerateFailure failure;
  final bool saving;
  final VoidCallback onRetry;
  final VoidCallback onOpenSettings;
  final VoidCallback onReport;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return ListView(
      padding: EdgeInsets.all(tokens.spacing.lg),
      children: <Widget>[
        Card(
          child: Padding(
            padding: EdgeInsets.all(tokens.spacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(failure.message, style: textTheme.titleMedium),
                SizedBox(height: tokens.spacing.xs),
                Text(
                  'Nothing was added to your plan.',
                  style: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
                if (failure.action != null) ...<Widget>[
                  SizedBox(height: tokens.spacing.md),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: FilledButton(
                      onPressed: saving
                          ? null
                          : switch (failure.action!) {
                              GenerateFailureAction.openSettings =>
                                onOpenSettings,
                              GenerateFailureAction.retry => onRetry,
                              GenerateFailureAction.report => onReport,
                            },
                      child: Text(failure.actionLabel!),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _NoMealsBody extends StatelessWidget {
  const _NoMealsBody({required this.message, required this.onOpenSettings});

  final String message;
  final VoidCallback onOpenSettings;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return ListView(
      padding: EdgeInsets.all(tokens.spacing.lg),
      children: <Widget>[
        Card(
          child: Padding(
            padding: EdgeInsets.all(tokens.spacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text('No meals to suggest', style: textTheme.titleMedium),
                SizedBox(height: tokens.spacing.xs),
                Text(
                  message,
                  style: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
                SizedBox(height: tokens.spacing.md),
                Align(
                  alignment: Alignment.centerLeft,
                  child: OutlinedButton(
                    onPressed: onOpenSettings,
                    child: const Text('Open Settings'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
