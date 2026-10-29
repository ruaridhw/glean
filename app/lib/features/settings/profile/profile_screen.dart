import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/household_profile_providers.dart';
import 'package:glean/design_system/design_system.dart';

import 'taste_interview_screen.dart';
import 'widgets/profile_facts.dart';

/// Saved tastes are read-only; revisions belong to a separate, confirmed interview draft.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(householdProfileProvider);
    final tokens = context.tokens;
    return Scaffold(
      appBar: AppBar(title: const Text('Your profile')),
      body: switch (profile) {
        AsyncData(:final HouseholdProfile? value) => Builder(
          builder: (context) {
            final saved = value ?? const HouseholdProfile();
            return ListView(
              padding: EdgeInsets.all(tokens.spacing.lg),
              children: <Widget>[
                Text(
                  saved.isEmpty
                      ? 'A plan that tastes like you.'
                      : 'Your table, at a glance.',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                SizedBox(height: tokens.spacing.lg),
                if (saved.isEmpty)
                  const Text(
                    'Tell Glean what you love, what to avoid and how you eat.',
                  )
                else
                  ProfileFacts(profile: saved),
                SizedBox(height: tokens.spacing.lg),
                FilledButton(
                  onPressed: () =>
                      Navigator.of(context, rootNavigator: true).push<void>(
                        MaterialPageRoute<void>(
                          builder: (_) => TasteInterviewScreen(baseline: saved),
                        ),
                      ),
                  child: Text(
                    saved.isEmpty
                        ? 'Start your taste interview'
                        : 'Retake your taste interview',
                  ),
                ),
                SizedBox(height: tokens.spacing.sm),
                const Text('Review before anything changes.'),
              ],
            );
          },
        ),
        AsyncError() => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Text('Could not load your profile.'),
              TextButton(
                onPressed: () => ref.invalidate(householdProfileProvider),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
        _ => const ListSkeleton(rows: 4, rowHeight: 96),
      },
    );
  }
}
