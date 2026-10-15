/// First-run setup (FLUTTER_MIGRATION.md §6, AC-UX-04) — new; there is no
/// onboarding today. Captures dinners/week, servings and dietary flags —
/// the values that steer meal-plan generation and, absent this screen, sit
/// at their compile-time defaults forever — then offers receipt-scan on a
/// final step of its own.
///
/// **Short and genuinely skippable**: four steps, a "Skip" escape hatch
/// visible on every one of them, and reused controls (`IntegerSliderControl`,
/// `DietaryFlagsControl`) rather than a bespoke duplicate set (§6 — "reuse
/// the same controls as Settings"). See `onboarding_gate.dart` for how this
/// screen is wired into real navigation (`OnboardingGate`, in the router's
/// tab-shell builder).
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

import 'providers/onboarding_status.dart';
import 'widgets/onboarding_footer.dart';
import 'widgets/onboarding_step_body.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  static const int stepCount = 4;

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
                  child: OnboardingStepBody(
                    key: ValueKey<int>(_step),
                    step: _step,
                    dinners: _dinners,
                    servings: _servings,
                    dietaryFlags: _dietaryFlags,
                    onDinnersChanged: (int v) => setState(() => _dinners = v),
                    onServingsChanged: (int v) => setState(() => _servings = v),
                    onDietaryFlagToggled: (String flag, bool isSelected) {
                      setState(() {
                        if (isSelected) {
                          _dietaryFlags.add(flag);
                        } else {
                          _dietaryFlags.remove(flag);
                        }
                      });
                    },
                  ),
                ),
              ),
              OnboardingFooter(
                step: _step,
                onBack: () => _goToStep(_step - 1),
                onNext: () => _goToStep(_step + 1),
                onScanReceipt: () => unawaited(
                  _finish(persistCaptured: true, navigateToScan: true),
                ),
                onFinishLater: () => unawaited(
                  _finish(persistCaptured: true, navigateToScan: false),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
