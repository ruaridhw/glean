/// The Settings screen. Auto-save, no Save button: every control persists on its own commit point (a slider's
/// release, a chip's tap, the max-time field's debounce) through [UserConfigRepository.save].
/// [_SettingsContentState] seeds its local fields once from the resolved `config`, and thereafter this screen is
/// the only writer of that row, so the stream re-emitting after a save never fights an in-progress edit.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/auth/auth.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/providers/user_config_providers.dart';
import 'package:glean/design_system/design_system.dart';

import 'settings_presentation.dart';
import 'widgets/account_section.dart';
import 'widgets/dietary_preferences_card.dart';
import 'widgets/max_time_field.dart';
import 'widgets/preference_slider_card.dart';
import 'widgets/settings_stats_row.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<UserConfigView> asyncConfig = ref.watch(
      userConfigProvider,
    );
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 220),
        child: KeyedSubtree(
          key: ValueKey<bool>(!asyncConfig.hasValue),
          child: !asyncConfig.hasValue
              ? const ListSkeleton(rows: 3, rowHeight: 120, headerHeight: 72)
              : asyncConfig.maybeWhen(
                  data: (UserConfigView config) =>
                      _SettingsContent(config: config),
                  orElse: () => const SettingsLoadError(),
                ),
        ),
      ),
    );
  }
}

/// Shown if `userConfigProvider` surfaces an `AsyncValue.error` (a genuine DB
/// error, distinct from "no row saved yet", which resolves to defaults).
class SettingsLoadError extends StatelessWidget {
  const SettingsLoadError({super.key});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Text(
        'Could not load settings. Check your connection and try again.',
        style: Theme.of(context).textTheme.bodyMedium,
        textAlign: TextAlign.center,
      ),
    );
  }
}

class _SettingsContent extends ConsumerStatefulWidget {
  const _SettingsContent({required this.config});

  final UserConfigView config;

  @override
  ConsumerState<_SettingsContent> createState() => _SettingsContentState();
}

class _SettingsContentState extends ConsumerState<_SettingsContent> {
  static const Duration _debounce = Duration(milliseconds: 500);

  late double _tolerance;
  late int _dinners;
  late int _servings;
  late Set<String> _dietaryFlags;
  late final TextEditingController _maxTimeController;
  String? _maxTimeError;
  Timer? _maxTimeDebounce;

  @override
  void initState() {
    super.initState();
    _tolerance = widget.config.purchaseTolerance;
    _dinners = widget.config.mealsPerWeek;
    _servings = widget.config.preferredServings;
    _dietaryFlags = widget.config.dietaryFlags.toSet();
    _maxTimeController = TextEditingController(
      text: widget.config.maxActiveTimeMins?.toString() ?? '',
    );
  }

  @override
  void dispose() {
    _maxTimeDebounce?.cancel();
    _maxTimeController.dispose();
    super.dispose();
  }

  UserConfigView _snapshot() => UserConfigView(
    id: widget.config.id,
    purchaseTolerance: _tolerance,
    preferredServings: _servings,
    mealsPerWeek: _dinners,
    dietaryFlags: _dietaryFlags.toList(),
    maxActiveTimeMins: _parsedMaxTime(),
  );

  int? _parsedMaxTime() {
    final String text = _maxTimeController.text.trim();
    return text.isEmpty ? null : int.tryParse(text);
  }

  /// The single write path for every control. [fireCommitHaptic] is false for dietary chips, which are on the
  /// `selectionClick` rung, not `mediumImpact`.
  Future<void> _persist({required bool fireCommitHaptic}) async {
    try {
      await ref.read(userConfigRepositoryProvider).save(_snapshot());
      if (!mounted) return;
      if (fireCommitHaptic) ref.read(hapticsProvider).mediumImpact();
    } catch (_) {
      if (!mounted) return;
      // A config-save failure must surface to the user.
      GleanSnackBar.show(context, 'Could not save your settings. Try again.');
    }
  }

  String? _validateMaxTime(String raw) {
    final String text = raw.trim();
    if (text.isEmpty) return null; // blank = "no limit", not an error.
    return validateBoundedInteger(
      text,
      SettingsOptionRanges.maxActiveTimeMins.min,
      SettingsOptionRanges.maxActiveTimeMins.max,
      'Max active time',
    );
  }

  void _onMaxTimeChanged(String raw) {
    setState(() => _maxTimeError = _validateMaxTime(raw));
    _maxTimeDebounce?.cancel();
    _maxTimeDebounce = Timer(_debounce, () {
      if (_maxTimeError == null) {
        unawaited(_persist(fireCommitHaptic: true));
      }
    });
  }

  Future<void> _handleSignOut() async {
    try {
      await ref.read(authControllerProvider.notifier).signOut();
      if (!mounted) return;
      ref.read(hapticsProvider).mediumImpact();
    } catch (_) {
      if (!mounted) return;
      GleanSnackBar.show(context, 'Could not sign out. Try again.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return ListView(
      padding: EdgeInsets.all(tokens.spacing.lg),
      children: <Widget>[
        SettingsStatsRow(
          dinners: _dinners,
          servings: _servings,
          dietCount: _dietaryFlags.length,
          tolerancePercent: (_tolerance * 100).round(),
        ),
        SizedBox(height: tokens.spacing.md),
        // Settings copy must state these values steer generation.
        Text(
          'These preferences steer how Glean plans your meals each week.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        SizedBox(height: tokens.spacing.lg),
        const _SectionLabel('Preferences'),
        SizedBox(height: tokens.spacing.sm),
        ToleranceCard(
          sliderKey: const Key('settings.toleranceSlider'),
          tolerance: _tolerance,
          onChanged: (double v) => setState(() => _tolerance = v),
          onCommitted: (double v) {
            setState(() => _tolerance = v);
            unawaited(_persist(fireCommitHaptic: true));
          },
        ),
        SizedBox(height: tokens.spacing.md),
        PreferenceSliderCard(
          sliderKey: const Key('settings.dinnersSlider'),
          title: 'Dinners per week',
          value: _dinners,
          min: SettingsOptionRanges.dinnersPerWeek.min,
          max: SettingsOptionRanges.dinnersPerWeek.max,
          onChanged: (int v) => setState(() => _dinners = v),
          onCommitted: (int v) {
            setState(() => _dinners = v);
            unawaited(_persist(fireCommitHaptic: true));
          },
        ),
        SizedBox(height: tokens.spacing.md),
        PreferenceSliderCard(
          sliderKey: const Key('settings.servingsSlider'),
          title: 'Default servings',
          value: _servings,
          min: SettingsOptionRanges.defaultServings.min,
          max: SettingsOptionRanges.defaultServings.max,
          onChanged: (int v) => setState(() => _servings = v),
          onCommitted: (int v) {
            setState(() => _servings = v);
            unawaited(_persist(fireCommitHaptic: true));
          },
        ),
        SizedBox(height: tokens.spacing.md),
        MaxTimeField(
          controller: _maxTimeController,
          errorText: _maxTimeError,
          onChanged: _onMaxTimeChanged,
        ),
        SizedBox(height: tokens.spacing.lg),
        const _SectionLabel('Dietary preferences'),
        SizedBox(height: tokens.spacing.sm),
        DietaryPreferencesCard(
          selected: _dietaryFlags,
          onToggle: (String flag, bool isSelected) {
            setState(() {
              if (isSelected) {
                _dietaryFlags.add(flag);
              } else {
                _dietaryFlags.remove(flag);
              }
            });
            unawaited(_persist(fireCommitHaptic: false));
          },
        ),
        SizedBox(height: tokens.spacing.lg),
        const _SectionLabel('Account'),
        SizedBox(height: tokens.spacing.sm),
        AccountSection(onSignOut: () => unawaited(_handleSignOut())),
      ],
    );
  }
}

/// A small uppercase section heading. `labelSmall` already carries the right size/weight/letter-spacing, so this
/// only adds `.toUpperCase()` once rather than at every call site.
class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: Theme.of(context).textTheme.labelSmall,
    );
  }
}
