import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// The Settings loading placeholder, cross-faded into real content via
/// `GleanCrossFade` (AC-TRN-01) — never a bare spinner.
class SettingsSkeleton extends StatelessWidget {
  const SettingsSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return ListView(
      padding: EdgeInsets.all(tokens.spacing.lg),
      physics: const NeverScrollableScrollPhysics(),
      children: <Widget>[
        const SkeletonBox(width: double.infinity, height: 72),
        SizedBox(height: tokens.spacing.md),
        const SkeletonBox(width: double.infinity, height: 120),
        SizedBox(height: tokens.spacing.md),
        const SkeletonBox(width: double.infinity, height: 120),
        SizedBox(height: tokens.spacing.md),
        const SkeletonBox(width: double.infinity, height: 120),
      ],
    );
  }
}

/// Shown if `userConfigProvider` ever surfaces an `AsyncValue.error` (a
/// genuine DB error, distinct from "no row saved yet" — `UserConfigRepository
/// .watch` already resolves that to defaults, not an error).
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
