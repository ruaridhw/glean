import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';

/// Whether the signed-in user has finished or skipped first-run setup. Reads
/// `user_config.onboardingCompleted` directly; completing writes through
/// `UserConfigRepository.markOnboardingCompleted` and this stream re-emits on
/// its own.
final StreamProvider<bool> hasCompletedOnboardingProvider =
    StreamProvider<bool>((Ref ref) {
      final String userId = ref.watch(currentUserIdProvider);
      return ref
          .watch(userConfigRepositoryProvider)
          .watchOnboardingCompleted(userId);
    });
