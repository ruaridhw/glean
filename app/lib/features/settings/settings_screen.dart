/// The Settings screen (FLUTTER_MIGRATION.md §6 "Settings & auth").
///
/// **Auto-save, no Save button (AC-SET-01).** Every control persists on its
/// own commit point — a slider's release, a chip's tap, the max-time field's
/// debounce — through [UserConfigRepository.save]. There is no separate
/// "unsaved" copy of the form for switching tabs to silently discard (the RN
/// dirty-state trap): [_SettingsContentState] seeds its local fields once
/// from the `config` its parent already resolved, and from then on the only
/// writer of that row is this screen itself, so the stream re-emitting after
/// a save never fights with an in-progress edit (AC-DATA-04/05 — no
/// `ref.invalidate` anywhere below; the stream already re-emits on its own).
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/providers/user_config_providers.dart';
import 'package:glean/design_system/design_system.dart';

import 'providers/sign_out_action.dart';
import 'settings_presentation.dart';
import 'widgets/account_section.dart';
import 'widgets/dietary_preferences_card.dart';
import 'widgets/legal_links_section.dart';
import 'widgets/max_time_field.dart';
import 'widgets/preference_slider_card.dart';
import 'widgets/section_label.dart';
import 'widgets/settings_skeleton.dart';
import 'widgets/settings_stats_row.dart';
import 'widgets/tolerance_card.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<UserConfigView> asyncConfig = ref.watch(
      userConfigProvider,
    );
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      // Skeleton -> content cross-fade (AC-TRN-01), never a hard cut.
      body: GleanCrossFade(
        showSkeleton: !asyncConfig.hasValue,
        skeleton: const SettingsSkeleton(),
        content: asyncConfig.maybeWhen(
          data: (UserConfigView config) => _SettingsContent(config: config),
          orElse: () => const SettingsLoadError(),
        ),
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

  /// The single write path for every control (AC-SET-01/AC-SET-03).
  /// [fireCommitHaptic] is false for dietary chips, which are on the
  /// `selectionClick` rung, not `mediumImpact` (AC-HAP-05) — see
  /// `DietaryFlagsControl`'s doc comment.
  Future<void> _persist({required bool fireCommitHaptic}) async {
    try {
      await ref.read(userConfigRepositoryProvider).save(_snapshot());
      if (!mounted) return;
      if (fireCommitHaptic) ref.read(hapticsProvider).mediumImpact();
    } catch (_) {
      if (!mounted) return;
      // AC-SET-03: a config-save failure must surface. RN's `saveUserConfig`
      // failing showed the user nothing at all.
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
      await ref.read(signOutActionProvider)();
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
        // AC-UX-05: settings copy must state these values steer generation.
        Text(
          'These preferences steer how Glean plans your meals each week.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        SizedBox(height: tokens.spacing.lg),
        const SectionLabel('Preferences'),
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
        const SectionLabel('Dietary preferences'),
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
        const SectionLabel('Account'),
        SizedBox(height: tokens.spacing.sm),
        AccountSection(onSignOut: () => unawaited(_handleSignOut())),
        SizedBox(height: tokens.spacing.lg),
        const SectionLabel('Legal'),
        SizedBox(height: tokens.spacing.sm),
        const LegalLinksSection(),
      ],
    );
  }
}
