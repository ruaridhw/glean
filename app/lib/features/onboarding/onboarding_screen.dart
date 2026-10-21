/// First-run setup: one "basics" page carrying dinners per week, servings and
/// the dietary flags (which steer meal-plan generation and otherwise stay at
/// their defaults), then the pantry step, which is the only page that writes
/// what was chosen. Both pages are skippable, and skipping the basics page
/// leaves today's defaults untouched. Wired in by `OnboardingGate`.
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

import 'onboarding_page.dart';
import 'widgets/onboarding_footer.dart';
import 'widgets/onboarding_progress.dart';
import 'widgets/onboarding_step_body.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  OnboardingPage _page = OnboardingPage.basics;

  int _dinners = UserConfigView.defaultMealsPerWeek;
  int _servings = UserConfigView.defaultPreferredServings;
  final Set<String> _dietaryFlags = <String>{};

  /// What the basics page handed forward when Continue was tapped. `null`
  /// means the page was skipped, and the finish writes nothing at all — the
  /// stored defaults stay exactly as they were.
  _BasicsAnswers? _answers;

  void _continueToPantry() {
    ref.read(hapticsProvider).lightImpact();
    setState(() {
      _answers = _BasicsAnswers(
        dinners: _dinners,
        servings: _servings,
        dietaryFlags: _dietaryFlags.toList(),
      );
      _page = OnboardingPage.pantry;
    });
  }

  /// Skips this page only: the values chosen so far are not handed forward, so
  /// finishing setup writes nothing and the defaults apply.
  void _skipBasics() {
    ref.read(hapticsProvider).lightImpact();
    setState(() {
      _answers = null;
      _page = OnboardingPage.pantry;
    });
  }

  void _backToBasics() {
    ref.read(hapticsProvider).lightImpact();
    setState(() => _page = OnboardingPage.basics);
  }

  /// The single exit path from the pantry page: "Scan a receipt" continues into
  /// receipt-scan after saving, "I'll do this later" (the pantry page's skip)
  /// saves and finishes. Both persist whatever the basics page handed forward.
  Future<void> _finish({required bool navigateToScan}) async {
    final String userId = ref.read(currentUserIdProvider);
    final _BasicsAnswers? answers = _answers;
    if (answers != null) {
      try {
        await ref
            .read(userConfigRepositoryProvider)
            .save(
              UserConfigView(
                id: userId,
                purchaseTolerance: UserConfigView.defaultPurchaseTolerance,
                preferredServings: answers.servings,
                mealsPerWeek: answers.dinners,
                dietaryFlags: answers.dietaryFlags.toList(),
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
    await ref
        .read(userConfigRepositoryProvider)
        .markOnboardingCompleted(userId);
    if (!mounted) return;
    ref.read(hapticsProvider).mediumImpact();
    // Finishing without scanning needs no navigation: `OnboardingGate` already
    // swaps to the tab shell once this stream re-emits `true`.
    if (navigateToScan) {
      context.goNamed(AppRoutes.intakeScan.name, extra: const ScanArgs());
    }
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
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
                  SizedBox(width: tokens.spacing.sm),
                  Expanded(
                    child: Text(
                      'About a minute',
                      textAlign: TextAlign.end,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
              SizedBox(height: tokens.spacing.md),
              OnboardingProgress(
                currentSlot: _page == OnboardingPage.basics
                    ? OnboardingProgress.basicsSlot
                    : OnboardingProgress.pantrySlot,
              ),
              SizedBox(height: tokens.spacing.sm),
              Expanded(
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 200),
                  // Pages fill the body and start at its top; the pantry page
                  // centres itself, the basics page scrolls from the heading.
                  layoutBuilder:
                      (Widget? current, List<Widget> previousChildren) => Stack(
                        fit: StackFit.expand,
                        children: <Widget>[...previousChildren, ?current],
                      ),
                  child: OnboardingStepBody(
                    key: ValueKey<OnboardingPage>(_page),
                    page: _page,
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
                page: _page,
                onBack: _backToBasics,
                onContinue: _continueToPantry,
                onSkipBasics: _skipBasics,
                onScanReceipt: () => unawaited(_finish(navigateToScan: true)),
                onFinishLater: () => unawaited(_finish(navigateToScan: false)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The basics page's answers, carried from Continue to the pantry page's save.
class _BasicsAnswers {
  const _BasicsAnswers({
    required this.dinners,
    required this.servings,
    required this.dietaryFlags,
  });

  final int dinners;
  final int servings;
  final List<String> dietaryFlags;
}
