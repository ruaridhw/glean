// Household-profile reads for the current user.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/household_profile.dart';
import 'database_providers.dart';
import 'repository_providers.dart';

/// The current user's profile, or `null` before the interview or any edit has stored one.
final StreamProvider<HouseholdProfile?> householdProfileProvider =
    StreamProvider<HouseholdProfile?>((ref) {
      final userId = ref.watch(currentUserIdProvider);
      return ref.watch(householdProfileRepositoryProvider).watch(userId);
    });
