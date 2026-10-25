// WeekFeedbackStore over a slow secure-storage boundary: a read that prunes past weeks must never write back a
// map that a newer write has already replaced.
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/plan/week_feedback.dart';

/// The plugin's in-memory store, with every read and write taking [delay], so operations can overlap. The very
/// first read takes [firstRead], so a slow first read (a launch's restore) can be overtaken by a later write.
class SlowStorage extends FlutterSecureStorage {
  SlowStorage(
    this.values, {
    this.delay = const Duration(milliseconds: 20),
    this.firstRead = const Duration(milliseconds: 20),
  });

  final Map<String, String> values;
  final Duration delay;
  final Duration firstRead;
  var _reads = 0;

  @override
  Future<String?> read({
    required String key,
    AppleOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    AppleOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    final String? value = values[key];
    await Future<void>.delayed(_reads++ == 0 ? firstRead : delay);
    return value;
  }

  @override
  Future<void> write({
    required String key,
    required String? value,
    AppleOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    AppleOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    await Future<void>.delayed(delay);
    if (value == null) {
      values.remove(key);
    } else {
      values[key] = value;
    }
  }

  @override
  Future<void> delete({
    required String key,
    AppleOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    AppleOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    await Future<void>.delayed(delay);
    values.remove(key);
  }
}

void main() {
  const String user = 'user-1';
  final DateTime now = DateTime(2026, 10, 27, 9);
  final DateTime thisWeek = DateTime(2026, 10, 26);

  test('a prune on read never overwrites a write that came after it', () async {
    final SlowStorage storage = SlowStorage(
      firstRead: const Duration(milliseconds: 80),
      <String, String>{
        WeekFeedbackStore.keyFor(user): jsonEncode(<String, dynamic>{
          '2026-10-19': <String, dynamic>{
            'chips': <String>['guests'],
            'note': '',
            'note_unused': false,
          },
          '2026-10-26': <String, dynamic>{
            'chips': <String>['lighter'],
            'note': '',
            'note_unused': false,
          },
        }),
      },
    );
    final WeekFeedbackStore store = WeekFeedbackStore(
      clock: () => now,
      storage: storage,
    );

    // The restore's read (which prunes last week) and a tap's write, started back to back.
    final Future<WeekFeedback?> restored = store.read(user, thisWeek);
    final Future<void> tapped = store.write(
      user,
      thisWeek,
      const WeekFeedback(chips: <FeedbackChip>{FeedbackChip.healthier}),
    );
    await Future.wait<Object?>(<Future<Object?>>[restored, tapped]);

    expect((await restored)?.chips, <FeedbackChip>{FeedbackChip.lighter});
    expect(
      jsonDecode(storage.values[WeekFeedbackStore.keyFor(user)]!),
      <String, dynamic>{
        '2026-10-26': <String, dynamic>{
          'chips': <String>['healthier'],
          'note': '',
          'note_unused': false,
        },
      },
    );
  });

  test('two weeks written at once both survive', () async {
    final SlowStorage storage = SlowStorage(<String, String>{});
    final WeekFeedbackStore store = WeekFeedbackStore(
      clock: () => now,
      storage: storage,
    );

    await Future.wait<void>(<Future<void>>[
      store.write(
        user,
        thisWeek,
        const WeekFeedback(chips: <FeedbackChip>{FeedbackChip.lighter}),
      ),
      store.write(
        user,
        DateTime(2026, 11, 2),
        const WeekFeedback(chips: <FeedbackChip>{FeedbackChip.guests}),
      ),
    ]);

    final Map<String, dynamic> saved =
        jsonDecode(storage.values[WeekFeedbackStore.keyFor(user)]!)
            as Map<String, dynamic>;
    expect(saved.keys, unorderedEquals(<String>['2026-10-26', '2026-11-02']));
  });
}
