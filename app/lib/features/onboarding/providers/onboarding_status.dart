/// Whether the signed-in user has already been through (or skipped) the
/// first-run setup (FLUTTER_MIGRATION.md §6, AC-UX-04). Must be **robust to
/// app restarts**, per this wave's brief, which explicitly directs deciding
/// persistence via `user_config`.
///
/// **Required follow-up for the Data module**: `user_config`
/// (`lib/data/tables.dart`) has no "has completed onboarding" column today,
/// and `lib/data/**` is outside this wave's ownership (IMPLEMENTATION.md's
/// module contract; that module is being actively edited in parallel).
/// [FileOnboardingStatusStore] below is a deliberately small, fully
/// self-contained substitute using `path_provider` (already a declared
/// dependency — no `pubspec.yaml` change needed): a plain text file of user
/// ids who have finished or skipped setup, one per line. It is designed to
/// be swapped for a `UserConfigRepository`-backed implementation later
/// without any call site changing — only [OnboardingStatusStore]'s
/// production instance in [onboardingStatusStoreProvider] would need to
/// change.
///
/// Modelled the same way as every drift-backed read in this app: a mutation
/// ([markCompleted]) just writes, and [watch] is a stream that re-emits on
/// its own — no `ref.invalidate` anywhere (mirrors AC-DATA-04/05's rule for
/// `lib/data/**`, applied here on principle even though this file sits
/// outside that module).
library;

import 'dart:async';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:path_provider/path_provider.dart';

abstract class OnboardingStatusStore {
  /// Emits the current "has completed" value for [userId] immediately, then
  /// again every time [markCompleted] is called for that user.
  Stream<bool> watch(String userId);

  Future<void> markCompleted(String userId);
}

class FileOnboardingStatusStore implements OnboardingStatusStore {
  final Map<String, StreamController<bool>> _controllers =
      <String, StreamController<bool>>{};

  Future<File> _file() async {
    final Directory dir = await getApplicationDocumentsDirectory();
    return File('${dir.path}/onboarding_completed.txt');
  }

  Future<Set<String>> _readCompletedIds() async {
    final File file = await _file();
    if (!await file.exists()) return <String>{};
    final List<String> lines = await file.readAsLines();
    return lines.where((String line) => line.trim().isNotEmpty).toSet();
  }

  StreamController<bool> _controllerFor(String userId) => _controllers
      .putIfAbsent(userId, () => StreamController<bool>.broadcast());

  @override
  Stream<bool> watch(String userId) async* {
    yield (await _readCompletedIds()).contains(userId);
    yield* _controllerFor(userId).stream;
  }

  @override
  Future<void> markCompleted(String userId) async {
    final Set<String> completed = await _readCompletedIds();
    if (!completed.contains(userId)) {
      final File file = await _file();
      await file.writeAsString('$userId\n', mode: FileMode.append);
    }
    _controllerFor(userId).add(true);
  }
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
    Provider<OnboardingStatusStore>((Ref ref) => FileOnboardingStatusStore());

final StreamProvider<bool> hasCompletedOnboardingProvider =
    StreamProvider<bool>((Ref ref) {
      final String userId = ref.watch(currentUserIdProvider);
      return ref.watch(onboardingStatusStoreProvider).watch(userId);
    });
