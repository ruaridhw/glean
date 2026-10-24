// Settings shows the household profile as one summary row that opens the Profile screen. The row has to say
// something true whatever the profile holds (nothing, a little, everything), follow edits without a reload,
// and stay one tidy line on a narrow phone at large text.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/household_profile_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/household_profile_repository.dart';
import 'package:glean/features/settings/profile/profile_screen.dart';
import 'package:glean/router/app_routes.dart';

import 'package:riverpod/misc.dart' show Override;

import '../../../support/harness.dart';

const String _userId = 'test-user';
const Key _row = Key('settings.profileRow');

void main() {
  late AppTestHarness harness;

  setUp(() => harness = AppTestHarness());
  tearDown(() => harness.dispose());

  HouseholdProfileRepository profiles() =>
      harness.container.read(householdProfileRepositoryProvider);

  Future<void> pumpSettings(
    WidgetTester tester, {
    HouseholdProfile? seed,
    Size size = const Size(420, 2000),
    double textScale = 1,
  }) async {
    tester.platformDispatcher.textScaleFactorTestValue = textScale;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.binding.setSurfaceSize(size);
    addTearDown(() => tester.binding.setSurfaceSize(null));
    if (seed != null) {
      await profiles().save(userId: _userId, profile: seed);
    }
    await harness.pumpAt(tester, AppRoutes.settings.path);
    await pumpPastSkeleton(tester);
    await tester.pumpAndSettle();
  }

  Finder rowText(String text) =>
      find.descendant(of: find.byKey(_row), matching: find.text(text));

  gleanWidgetTest('with no profile the row says nothing is set yet', (
    tester,
  ) async {
    await pumpSettings(tester);

    expect(rowText('Your profile'), findsOneWidget);
    expect(
      rowText('Nothing yet: tell Glean what you love and avoid'),
      findsOneWidget,
    );
  });

  gleanWidgetTest('a partial profile is summarised by what is set', (
    tester,
  ) async {
    await pumpSettings(
      tester,
      seed: const HouseholdProfile(
        favouriteMeals: <FavouriteMeal>[FavouriteMeal(text: 'Dal')],
        dislikedIngredients: <String>['olives', 'capers'],
      ),
    );

    expect(rowText('1 favourite · 2 never'), findsOneWidget);
  });

  gleanWidgetTest('a full profile leads with its counts and how the weeks go', (
    tester,
  ) async {
    await pumpSettings(
      tester,
      seed: const HouseholdProfile(
        favouriteMeals: <FavouriteMeal>[
          FavouriteMeal(text: 'Katsu curry'),
          FavouriteMeal(text: 'Fish pie'),
          FavouriteMeal(text: 'Dal'),
        ],
        dislikedIngredients: <String>['mushrooms', 'olives'],
        cuisinesLiked: <String>['Indian'],
        habits: 'Quick weeknights, treat Friday',
        household: 'Two adults, two kids',
        spiceTolerance: SpiceTolerance.mild,
      ),
    );

    expect(
      find.descendant(
        of: find.byKey(_row),
        matching: find.textContaining(
          '3 favourites · 2 never · Quick weeknights',
        ),
      ),
      findsOneWidget,
    );
  });

  gleanWidgetTest('the row follows the stored profile without a reload', (
    tester,
  ) async {
    await pumpSettings(tester);

    await tester.runAsync(
      () => profiles().save(
        userId: _userId,
        profile: const HouseholdProfile(cuisinesAvoided: <String>['Thai']),
      ),
    );
    await tester.pumpAndSettle();

    expect(rowText('1 never'), findsOneWidget);
  });

  gleanWidgetTest('a profile that cannot be read gives a neutral line, not a '
      'blank or an empty profile', (tester) async {
    final AppTestHarness failing = AppTestHarness(
      overrides: <Override>[
        householdProfileProvider.overrideWith(
          (ref) => Stream<HouseholdProfile?>.error(StateError('unreadable')),
        ),
      ],
    );
    addTearDown(failing.dispose);
    await tester.binding.setSurfaceSize(const Size(420, 2000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await failing.pumpAt(tester, AppRoutes.settings.path);
    await pumpPastSkeleton(tester);
    await tester.pumpAndSettle();

    expect(rowText('Could not load your profile'), findsOneWidget);
  });

  gleanWidgetTest('tapping the row opens the Profile screen, and Back returns '
      'to Settings', (tester) async {
    await pumpSettings(tester);

    await tester.ensureVisible(find.byKey(_row));
    await tester.tap(find.byKey(_row));
    await pumpPastSkeleton(tester);
    await tester.pumpAndSettle();

    expect(find.byType(ProfileScreen), findsOneWidget);

    await tester.pageBack();
    await pumpPastSkeleton(tester);
    await tester.pumpAndSettle();
    expect(find.byType(ProfileScreen), findsNothing);
    expect(find.byKey(_row), findsOneWidget);
  });

  for (final double scale in <double>[1, 2]) {
    gleanWidgetTest('the row stays one line on a 320-wide phone at ${scale}x '
        'text', (tester) async {
      await pumpSettings(
        tester,
        size: const Size(320, 844),
        textScale: scale,
        seed: const HouseholdProfile(
          favouriteMeals: <FavouriteMeal>[FavouriteMeal(text: 'Dal')],
          dislikedIngredients: <String>['mushrooms', 'olives'],
          habits: 'Quick weeknights, a batch cook at the weekend',
          household: 'Two adults, two kids and a dog who begs',
        ),
      );
      // Step the list rather than drag it: a drag at this size lands on a slider.
      final ScrollPosition position = tester
          .state<ScrollableState>(find.byType(Scrollable).first)
          .position;
      while (find.byKey(_row).evaluate().isEmpty &&
          position.pixels < position.maxScrollExtent) {
        position.jumpTo(
          (position.pixels + 200).clamp(0, position.maxScrollExtent),
        );
        await tester.pump();
      }
      await tester.ensureVisible(find.byKey(_row));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      final Text summary = tester.widget<Text>(
        find.descendant(
          of: find.byKey(_row),
          matching: find.textContaining('1 favourite'),
        ),
      );
      expect(summary.maxLines, 1);
      expect(summary.overflow, TextOverflow.ellipsis);
    });
  }
}
