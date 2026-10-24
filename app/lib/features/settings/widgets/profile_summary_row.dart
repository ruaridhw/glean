import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/household_profile_providers.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';

import '../profile/profile_presentation.dart';

/// Settings' one-line view of the household profile; tapping it opens the Profile screen.
class ProfileSummaryRow extends ConsumerWidget {
  const ProfileSummaryRow({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<HouseholdProfile?> profile = ref.watch(
      householdProfileProvider,
    );
    return Card(
      child: ListTile(
        key: const Key('settings.profileRow'),
        title: const Text('Your profile'),
        // Nothing until the read lands, rather than flashing the empty line at someone who has a profile.
        subtitle: Text(
          switch (profile) {
            AsyncData(:final HouseholdProfile? value) => profileSummary(value),
            AsyncError() => 'Could not load your profile',
            _ => '',
          },
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        trailing: const Icon(Icons.chevron_right_rounded),
        onTap: () => context.pushNamed(AppRoutes.settingsProfile.name),
      ),
    );
  }
}
