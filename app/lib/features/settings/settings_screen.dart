/// The Settings screen. Auto-save, no Save button: every control persists on its own commit point (a slider's
/// release, a chip's tap, the max-time field's debounce) through [UserConfigRepository.save].
/// [_SettingsContentState] seeds its local fields from the resolved `config`. The stream re-emitting this screen's own
/// saves never fights an in-progress edit, while a row changed by anything else (a restored backup) replaces the form,
/// so the next control change cannot write a stale row back.
library;

import 'dart:async';

import 'package:flutter/foundation.dart' show setEquals;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api.dart';
import 'package:glean/auth/auth.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/providers/user_config_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/diagnostics/diagnostics.dart';
import 'package:glean/logging/logging.dart';

import 'settings_presentation.dart';
import 'widgets/account_section.dart';
import 'widgets/developer_section.dart';
import 'widgets/dietary_preferences_card.dart';
import 'widgets/max_time_field.dart';
import 'widgets/preference_slider_card.dart';
import 'widgets/restore_backup_sheet.dart';
import 'widgets/settings_stats_row.dart';
import 'widgets/version_label.dart';

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
  bool _exporting = false;
  bool _restoring = false;

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

  /// The rows this screen saved recently; the stream echoing one back is not an outside change.
  final List<UserConfigView> _ownWrites = <UserConfigView>[];

  @override
  void didUpdateWidget(_SettingsContent oldWidget) {
    super.didUpdateWidget(oldWidget);
    final UserConfigView next = widget.config;
    if (identical(next, oldWidget.config)) return;
    if (_sameSettings(next, _snapshot())) return;
    if (_ownWrites.any((UserConfigView w) => _sameSettings(w, next))) return;
    _ownWrites.clear();
    _tolerance = next.purchaseTolerance;
    _dinners = next.mealsPerWeek;
    _servings = next.preferredServings;
    _dietaryFlags = next.dietaryFlags.toSet();
    // Leave the field alone while it already parses to the stored value, so a half-typed entry survives.
    if (_parsedMaxTime() != next.maxActiveTimeMins) {
      _maxTimeDebounce?.cancel();
      _maxTimeController.text = next.maxActiveTimeMins?.toString() ?? '';
      _maxTimeError = null;
    }
  }

  static bool _sameSettings(UserConfigView a, UserConfigView b) =>
      a.purchaseTolerance == b.purchaseTolerance &&
      a.preferredServings == b.preferredServings &&
      a.mealsPerWeek == b.mealsPerWeek &&
      a.maxActiveTimeMins == b.maxActiveTimeMins &&
      setEquals(a.dietaryFlags.toSet(), b.dietaryFlags.toSet());

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
    final UserConfigView row = _snapshot();
    _ownWrites.add(row);
    if (_ownWrites.length > 8) _ownWrites.removeAt(0);
    try {
      await ref.read(userConfigRepositoryProvider).save(row);
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

  Future<void> _handleExportDiagnostics() async {
    setState(() => _exporting = true);
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
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<void> _handleRestoreBackup() async {
    final ScaffoldMessengerState messenger = ScaffoldMessenger.of(context);
    final BackupSummary? chosen = await showModalBottomSheet<BackupSummary>(
      context: context,
      builder: (BuildContext _) => const RestoreBackupSheet(),
    );
    if (chosen == null || !mounted) return;
    final bool confirmed =
        await showDialog<bool>(
          context: context,
          builder: (BuildContext context) => AlertDialog(
            title: const Text('Replace everything on this phone?'),
            content: const Text(
              'Your pantry, plan, shopping list, recipes and history will be '
              'replaced by this backup.',
            ),
            actions: <Widget>[
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
              TextButton(
                key: const Key('restore.confirm'),
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Restore'),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed || !mounted) return;
    setState(() => _restoring = true);
    final GleanLogger? logger = ref.read(gleanLoggerProvider);
    try {
      await ref.read(backupRestoreProvider)(chosen);
      GleanSnackBar.showOn(messenger, 'Backup restored');
    } on BackupTooNewException catch (error) {
      GleanSnackBar.showOn(messenger, error.toString());
    } catch (error) {
      await logger?.error('restore backup failed: ${describeError(error)}');
      GleanSnackBar.showOn(
        messenger,
        'Could not restore the backup. Your current data has not been changed.',
      );
    } finally {
      if (mounted) setState(() => _restoring = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final bool developerMode = ref.watch(developerModeProvider);
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
        if (developerMode) ...<Widget>[
          SizedBox(height: tokens.spacing.lg),
          const _SectionLabel('Developer'),
          SizedBox(height: tokens.spacing.sm),
          DeveloperSection(
            exporting: _exporting,
            onExportDiagnostics: () => unawaited(_handleExportDiagnostics()),
            restoring: _restoring,
            onRestoreBackup: () => unawaited(_handleRestoreBackup()),
          ),
        ],
        VersionLabel(
          onTap: () =>
              ref.read(developerModeProvider.notifier).registerVersionTap(),
        ),
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
