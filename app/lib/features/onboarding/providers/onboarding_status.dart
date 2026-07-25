/// Whether the signed-in user has already been through (or skipped) the
/// first-run setup (FLUTTER_MIGRATION.md §6, AC-UX-04). Must be **robust to
/// app restarts**, per this wave's brief, which explicitly directs deciding
/// persistence via `user_config`.
///
/// R-04 (.scratch/flutter-port/REMEDIATION.md): the original version of this
/// file wrote completed user ids to a standalone `onboarding_completed.txt`
/// via `path_provider`, because `user_config` (`lib/data/tables.dart`) had no
/// "has completed onboarding" column yet and that table was outside this
/// wave's ownership. That column now exists (`UserConfig.onboardingCompleted`)
/// and [UserConfigOnboardingStatusStore] backs this interface with it, so
/// SQLite is once again the sole source of truth for user data (§3) — no
/// text file, no `path_provider` read here. Only [OnboardingStatusStore]'s
/// production instance in [onboardingStatusStoreProvider] changed; every
/// call site ([OnboardingGate], `onboarding_screen.dart`) is untouched.
///
/// Modelled the same way as every drift-backed read in this app: a mutation
/// ([markCompleted]) just writes, and [watch] is a stream that re-emits on
/// its own — no `ref.invalidate` anywhere (AC-DATA-04/05).
library;

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/user_config_repository.dart';

abstract class OnboardingStatusStore {
  /// Emits the current "has completed" value for [userId] immediately, then
  /// again every time [markCompleted] is called for that user.
  Stream<bool> watch(String userId);

  Future<void> markCompleted(String userId);
}

/// Production [OnboardingStatusStore]: a thin adapter over
/// [UserConfigRepository]'s `onboardingCompleted` column (R-04).
class UserConfigOnboardingStatusStore implements OnboardingStatusStore {
  UserConfigOnboardingStatusStore(this._repository);

  final UserConfigRepository _repository;

  @override
  Stream<bool> watch(String userId) =>
      _repository.watchOnboardingCompleted(userId);

  @override
  Future<void> markCompleted(String userId) =>
      _repository.markOnboardingCompleted(userId);
}

/// A fake [OnboardingStatusStore] for widget/unit tests — avoids exercising
/// real file IO (which has no plugin channel registered under plain
/// `flutter test`) the same way `RecordingHaptics` avoids a real platform
/// channel for haptics.
class InMemoryOnboardingStatusStore implements OnboardingStatusStore {
  InMemoryOnboardingStatusStore({Set<String>? initiallyCompleted})
    : _completed = <String>{...(initiallyCompleted ?? const <String>{})};

  final Set<String> _completed;
  final Map<String, StreamController<bool>> _controllers =
      <String, StreamController<bool>>{};

  StreamController<bool> _controllerFor(String userId) => _controllers
      .putIfAbsent(userId, () => StreamController<bool>.broadcast());

  @override
  Stream<bool> watch(String userId) async* {
    yield _completed.contains(userId);
    yield* _controllerFor(userId).stream;
  }

  @override
  Future<void> markCompleted(String userId) async {
    _completed.add(userId);
    _controllerFor(userId).add(true);
  }
}

final Provider<OnboardingStatusStore> onboardingStatusStoreProvider =
    Provider<OnboardingStatusStore>(
      (Ref ref) => UserConfigOnboardingStatusStore(
        ref.watch(userConfigRepositoryProvider),
      ),
    );

final StreamProvider<bool> hasCompletedOnboardingProvider =
    StreamProvider<bool>((Ref ref) {
      final String userId = ref.watch(currentUserIdProvider);
      return ref.watch(onboardingStatusStoreProvider).watch(userId);
    });
