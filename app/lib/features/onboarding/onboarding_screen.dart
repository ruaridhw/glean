/// First-run setup (FLUTTER_MIGRATION.md §6, AC-UX-04) — new; there is no
/// onboarding today. Captures dinners/week, servings and dietary flags —
/// the values that steer meal-plan generation and, absent this screen, sit
/// at their compile-time defaults forever — then points the user at
/// receipt-scan.
///
/// **Short and genuinely skippable**: three steps, a "Skip" escape hatch
/// visible on every one of them, and reused controls (`IntegerSliderControl`,
/// `DietaryFlagsControl`) rather than a bespoke duplicate set (§6 — "reuse
/// the same controls as Settings"). See `onboarding_gate.dart` for why this
/// screen isn't wired into real navigation yet.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

import '../settings/settings_presentation.dart';
import '../settings/widgets/dietary_flags_control.dart';
import '../settings/widgets/integer_slider_control.dart';
import 'providers/onboarding_status.dart';
import 'widgets/onboarding_step_scaffold.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  static const int stepCount = 3;

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  int _step = 0;
  int _dinners = UserConfigView.defaultMealsPerWeek;
  int _servings = UserConfigView.defaultPreferredServings;
  final Set<String> _dietaryFlags = <String>{};

  void _goToStep(int next) {
    ref.read(hapticsProvider).lightImpact();
    setState(() => _step = next);
  }

  /// The single exit path, however it's reached: the top "Skip" (any step,
  /// discards everything captured so far), "I'll do this later" (keeps what
  /// was captured), or "Scan a receipt" (keeps it, and continues into
  /// receipt-scan per AC-UX-04).
  Future<void> _finish({
    required bool persistCaptured,
    required bool navigateToScan,
  }) async {
    final String userId = ref.read(currentUserIdProvider);
    if (persistCaptured) {
      try {
        await ref
            .read(userConfigRepositoryProvider)
            .save(
              UserConfigView(
                id: userId,
                purchaseTolerance: UserConfigView.defaultPurchaseTolerance,
                preferredServings: _servings,
                mealsPerWeek: _dinners,
                dietaryFlags: _dietaryFlags.toList(),
                maxActiveTimeMins: null,
              ),
            );
      } catch (_) {
        if (mounted) {
          GleanSnackBar.show(
            context,
            'Could not save your preferences — you can set them later in '
            'Settings.',
          );
        }
      }
    }
    await ref.read(onboardingStatusStoreProvider).markCompleted(userId);
    if (!mounted) return;
    ref.read(hapticsProvider).mediumImpact();
    // Skipping/finishing without scanning needs no navigation: `OnboardingGate`
    // already swaps to the tab shell once this stream re-emits `true`.
    if (navigateToScan) {
      context.goNamed(AppRoutes.intakeScan.name, extra: const ScanArgs());
    }
  }

  Widget _buildStep() {
    switch (_step) {
      case 0:
        return OnboardingStepScaffold(
          key: const ValueKey<String>('step-dinners'),
          question: 'How many dinners do you cook at home most weeks?',
          child: IntegerSliderControl(
            value: _dinners,
            min: SettingsOptionRanges.dinnersPerWeek.min,
            max: SettingsOptionRanges.dinnersPerWeek.max,
            onChanged: (int v) => setState(() => _dinners = v),
            onCommitted: (int v) => setState(() => _dinners = v),
          ),
        );
      case 1:
        return OnboardingStepScaffold(
          key: const ValueKey<String>('step-servings'),
          question: 'How many people are you usually cooking for?',
          child: IntegerSliderControl(
            value: _servings,
            min: SettingsOptionRanges.defaultServings.min,
            max: SettingsOptionRanges.defaultServings.max,
            onChanged: (int v) => setState(() => _servings = v),
            onCommitted: (int v) => setState(() => _servings = v),
          ),
        );
      default:
        return OnboardingStepScaffold(
          key: const ValueKey<String>('step-dietary'),
          question: 'Any dietary preferences we should know about?',
          subtitle: 'Optional — skip this if none apply.',
          child: DietaryFlagsControl(
            selected: _dietaryFlags,
            onToggle: (String flag, bool isSelected) {
              setState(() {
                if (isSelected) {
                  _dietaryFlags.add(flag);
                } else {
                  _dietaryFlags.remove(flag);
                }
              });
            },
          ),
        );
    }
  }

  Widget _buildFooter(AppTokens tokens) {
    final bool isLastStep = _step == OnboardingScreen.stepCount - 1;
    if (!isLastStep) {
      return Row(
        children: <Widget>[
          if (_step > 0)
            OutlinedButton(
              onPressed: () => _goToStep(_step - 1),
              child: const Text('Back'),
            ),
          const Spacer(),
          FilledButton(
            onPressed: () => _goToStep(_step + 1),
            child: const Text('Next'),
          ),
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        FilledButton(
          onPressed: () =>
              unawaited(_finish(persistCaptured: true, navigateToScan: true)),
          child: const Text('Scan a receipt'),
        ),
        SizedBox(height: tokens.spacing.sm),
        TextButton(
          onPressed: () =>
              unawaited(_finish(persistCaptured: true, navigateToScan: false)),
          child: const Text("I'll do this later"),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: tokens.spacing.lg,
            vertical: tokens.spacing.md,
          ),
          child: Column(
            children: <Widget>[
              Row(
                children: <Widget>[
                  const GleanMark(size: 32),
                  const Spacer(),
                  TextButton(
                    onPressed: () => unawaited(
                      _finish(persistCaptured: false, navigateToScan: false),
                    ),
                    child: const Text('Skip'),
                  ),
                ],
              ),
              SizedBox(height: tokens.spacing.lg),
              Expanded(
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 200),
                  child: _buildStep(),
                ),
              ),
              _buildFooter(tokens),
            ],
          ),
        ),
      ),
    );
  }
}
