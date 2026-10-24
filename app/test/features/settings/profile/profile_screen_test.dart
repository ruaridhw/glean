// The Profile screen is where the household sees and corrects what Glean knows. Every edit saves through the
// repository straight away, and removing anything (a chip or a note) is undone from the snackbar back to exactly
// what was stored before. These tests pump the real route over the real in-memory database and read the stored
// profile back through the repository.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/household_profile_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/household_profile_repository.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/settings/profile/profile_presentation.dart';
import 'package:glean/router/app_routes.dart';

import 'package:riverpod/misc.dart' show Override;

import '../../../support/harness.dart';

const String _userId = 'test-user';

const HouseholdProfile _filled = HouseholdProfile(
  favouriteMeals: <FavouriteMeal>[
    FavouriteMeal(text: 'Katsu curry', recipeId: 'rec_1'),
    FavouriteMeal(text: 'Fish pie'),
  ],
  lovedIngredients: <String>['miso'],
  dislikedIngredients: <String>['mushrooms', 'olives'],
  cuisinesLiked: <String>['Indian'],
  cuisinesAvoided: <String>['Thai'],
  proteinTargets: <ProteinTarget>[
    ProteinTarget(protein: 'fish', minPerWeek: 2),
  ],
  spiceTolerance: SpiceTolerance.mild,
  habits: 'Quick weeknights, treat Friday',
  household: 'Two adults, two kids',
  notes: <ProfileNote>[
    ProfileNote(
      date: '2026-10-20',
      text: 'Asked for no fish on Mondays',
      source: ProfileNoteSource.interview,
    ),
    ProfileNote(
      date: '2026-10-24',
      text: 'Prefers rice over pasta midweek',
      source: ProfileNoteSource.feedback,
    ),
  ],
);

/// Each chip list, the item the filled profile has in it, and a new item to add.
final List<(ProfileList<Object?>, String, String)> _chipLists =
    <(ProfileList<Object?>, String, String)>[
      (ProfileLists.favouriteMeals, 'Fish pie', 'Dal'),
      (ProfileLists.lovedIngredients, 'miso', 'prawns'),
      (ProfileLists.dislikedIngredients, 'mushrooms', 'capers'),
      (ProfileLists.cuisinesLiked, 'Indian', 'Japanese'),
      (ProfileLists.cuisinesAvoided, 'Thai', 'French'),
      (ProfileLists.proteinTargets, 'fish · at least 2 a week', ''),
    ];

void main() {
  late AppTestHarness harness;

  setUp(() => harness = AppTestHarness());
  tearDown(() => harness.dispose());

  HouseholdProfileRepository profiles() =>
      harness.container.read(householdProfileRepositoryProvider);

  Future<HouseholdProfile?> stored(WidgetTester tester) =>
      tester.runAsync<HouseholdProfile?>(() => profiles().get(_userId));

  Future<void> pumpProfile(
    WidgetTester tester, {
    HouseholdProfile? seed,
    Size size = const Size(420, 2600),
    double textScale = 1,
  }) async {
    tester.platformDispatcher.textScaleFactorTestValue = textScale;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.binding.setSurfaceSize(size);
    addTearDown(() => tester.binding.setSurfaceSize(null));
    if (seed != null) {
      await profiles().save(userId: _userId, profile: seed);
    }
    await harness.pumpAt(tester, AppRoutes.settingsProfile.path);
    await pumpPastSkeleton(tester);
    await tester.pumpAndSettle();
  }

  /// Steps the profile list until [finder] is built (a drag can land on a text field and scroll that instead).
  Future<void> scrollToBuild(WidgetTester tester, Finder finder) async {
    final ScrollPosition position = tester
        .state<ScrollableState>(find.byType(Scrollable).first)
        .position;
    while (finder.evaluate().isEmpty &&
        position.pixels < position.maxScrollExtent) {
      position.jumpTo(
        (position.pixels + 200).clamp(0, position.maxScrollExtent),
      );
      await tester.pump();
    }
    await tester.ensureVisible(finder);
    await tester.pumpAndSettle();
  }

  Future<void> enterInDialog(WidgetTester tester, String text) async {
    await tester.enterText(find.byKey(const Key('profile.entry')), text);
    await tester.tap(find.byKey(const Key('profile.entry.save')));
    await tester.pumpAndSettle();
  }

  gleanWidgetTest('an empty profile says so, says how the interview fills '
      'it, and still offers every list to fill in by hand', (tester) async {
    await pumpProfile(tester);

    expect(find.text("Glean doesn't know your tastes yet"), findsOneWidget);
    expect(find.textContaining('first set up Glean'), findsOneWidget);
    for (final (ProfileList<Object?> list, _, _) in _chipLists) {
      expect(find.byKey(Key('profile.add.${list.title}')), findsOneWidget);
    }
    expect(find.text('Nothing yet.'), findsNothing);
  });

  gleanWidgetTest('a filled profile shows every list, the free text and the '
      'notes Glean kept with their date and source', (tester) async {
    await pumpProfile(tester, seed: _filled);

    expect(find.text("Glean doesn't know your tastes yet"), findsNothing);
    for (final (_, String existing, _) in _chipLists) {
      expect(find.widgetWithText(InputChip, existing), findsOneWidget);
    }
    expect(find.text('Quick weeknights, treat Friday'), findsOneWidget);
    expect(find.text('Two adults, two kids'), findsOneWidget);
    expect(
      tester
          .widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'Mild'))
          .selected,
      isTrue,
    );
    expect(find.text('Prefers rice over pasta midweek'), findsOneWidget);
    expect(find.text('24 Oct 2026 · from your feedback'), findsOneWidget);
    expect(find.text('20 Oct 2026 · from the interview'), findsOneWidget);
  });

  for (final (ProfileList<Object?> list, String existing, String added)
      in _chipLists.where((e) => e.$3.isNotEmpty)) {
    gleanWidgetTest('${list.title}: an added item saves', (tester) async {
      await pumpProfile(tester, seed: _filled);

      await tester.tap(find.byKey(Key('profile.add.${list.title}')));
      await tester.pumpAndSettle();
      await enterInDialog(tester, '  $added ');

      expect(find.widgetWithText(InputChip, added), findsOneWidget);
      final HouseholdProfile after = (await stored(tester))!;
      expect(list.indexOf(after, added), list.read(_filled).length);
      expect(list.read(after).length, list.read(_filled).length + 1);
    });

    gleanWidgetTest('${list.title}: an edited item saves in place', (
      tester,
    ) async {
      await pumpProfile(tester, seed: _filled);

      await tester.tap(find.widgetWithText(InputChip, existing));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<TextField>(find.byKey(const Key('profile.entry')))
            .controller!
            .text,
        existing,
      );
      await enterInDialog(tester, '$existing (edited)');

      final HouseholdProfile after = (await stored(tester))!;
      final int at = list.indexOf(_filled, existing);
      expect(list.indexOf(after, '$existing (edited)'), at);
      expect(list.read(after).length, list.read(_filled).length);
    });
  }

  for (final (ProfileList<Object?> list, String existing, _) in _chipLists) {
    gleanWidgetTest('${list.title}: a removed item comes back exactly on '
        'Undo', (tester) async {
      await pumpProfile(tester, seed: _filled);

      await tester.tap(find.byTooltip('Remove $existing'));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(InputChip, existing), findsNothing);
      expect(find.text('Removed $existing'), findsOneWidget);
      expect(list.indexOf((await stored(tester))!, existing), -1);
      expect(harness.hapticCalls, <HapticWeight>[HapticWeight.medium]);

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(InputChip, existing), findsOneWidget);
      expect((await stored(tester))!.toJson(), _filled.toJson());
    });
  }

  gleanWidgetTest('editing a favourite without changing its text keeps the '
      'recipe it matched; new text drops the match', (tester) async {
    await pumpProfile(tester, seed: _filled);

    await tester.tap(find.widgetWithText(InputChip, 'Katsu curry'));
    await tester.pumpAndSettle();
    await enterInDialog(tester, 'Katsu curry');
    expect((await stored(tester))!.favouriteMeals.first.recipeId, 'rec_1');

    await tester.tap(find.widgetWithText(InputChip, 'Katsu curry'));
    await tester.pumpAndSettle();
    await enterInDialog(tester, 'Chicken katsu');
    final FavouriteMeal edited = (await stored(tester))!.favouriteMeals.first;
    expect(edited.text, 'Chicken katsu');
    expect(edited.recipeId, isNull);
  });

  gleanWidgetTest('Undo after the same item was added again does not make a '
      'second chip', (tester) async {
    await pumpProfile(tester, seed: _filled);

    await tester.tap(find.byTooltip('Remove olives'));
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(Key('profile.add.${ProfileLists.dislikedIngredients.title}')),
    );
    await tester.pumpAndSettle();
    await enterInDialog(tester, 'Olives');
    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();

    expect((await stored(tester))!.dislikedIngredients, <String>[
      'mushrooms',
      'Olives',
    ]);
  });

  gleanWidgetTest('adding or changing an item into one already there is '
      'refused, and says why', (tester) async {
    await pumpProfile(tester, seed: _filled);

    await tester.tap(find.widgetWithText(InputChip, 'mushrooms'));
    await tester.pumpAndSettle();
    await enterInDialog(tester, 'Olives');
    expect(find.text('Olives is already there'), findsOneWidget);

    await tester.tap(
      find.byKey(Key('profile.add.${ProfileLists.dislikedIngredients.title}')),
    );
    await tester.pumpAndSettle();
    await enterInDialog(tester, 'MUSHROOMS');
    expect(find.text('MUSHROOMS is already there'), findsOneWidget);

    expect((await stored(tester))!.toJson(), _filled.toJson());
  });

  gleanWidgetTest('a favourite edited only in case keeps its recipe', (
    tester,
  ) async {
    await pumpProfile(tester, seed: _filled);

    await tester.tap(find.widgetWithText(InputChip, 'Katsu curry'));
    await tester.pumpAndSettle();
    await enterInDialog(tester, 'katsu curry');

    final FavouriteMeal edited = (await stored(tester))!.favouriteMeals.first;
    expect(edited.text, 'katsu curry');
    expect(edited.recipeId, 'rec_1');
  });

  gleanWidgetTest('removing the second of two equal favourites removes that '
      'one, so the first keeps its recipe', (tester) async {
    await pumpProfile(
      tester,
      seed: const HouseholdProfile(
        favouriteMeals: <FavouriteMeal>[
          FavouriteMeal(text: 'Dal', recipeId: 'rec_3'),
          FavouriteMeal(text: 'Dal'),
        ],
      ),
    );

    await tester.tap(find.byTooltip('Remove Dal').at(1));
    await tester.pumpAndSettle();

    final FavouriteMeal left = (await stored(tester))!.favouriteMeals.single;
    expect(left.recipeId, 'rec_3');
  });

  gleanWidgetTest('cancelling the entry dialog changes nothing', (
    tester,
  ) async {
    await pumpProfile(tester, seed: _filled);

    await tester.tap(find.widgetWithText(InputChip, 'olives'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('profile.entry')), 'capers');
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect((await stored(tester))!.toJson(), _filled.toJson());
  });

  Future<void> openProteinDialog(WidgetTester tester, {String? editing}) async {
    await tester.tap(
      editing == null
          ? find.byKey(Key('profile.add.${ProfileLists.proteinTargets.title}'))
          : find.widgetWithText(InputChip, editing),
    );
    await tester.pumpAndSettle();
  }

  Future<void> fillProtein(
    WidgetTester tester, {
    String? protein,
    String min = '',
    String max = '',
  }) async {
    if (protein != null) {
      await tester.tap(find.byKey(Key('profile.protein.$protein')));
      await tester.pump();
    }
    await tester.enterText(find.byKey(const Key('profile.protein.min')), min);
    await tester.enterText(find.byKey(const Key('profile.protein.max')), max);
  }

  gleanWidgetTest('a protein target is picked from the main proteins, and the '
      'keyboard Done key adds it', (tester) async {
    await pumpProfile(tester, seed: _filled);

    await openProteinDialog(tester);
    expect(find.byKey(const Key('profile.protein.name')), findsNothing);
    for (final String protein in mainProteins) {
      expect(find.byKey(Key('profile.protein.$protein')), findsOneWidget);
    }
    expect(find.byKey(const Key('profile.protein.mixed')), findsNothing);
    expect(find.byKey(const Key('profile.protein.none')), findsNothing);

    await fillProtein(tester, protein: 'turkey_or_duck', max: '2');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();

    expect(
      find.widgetWithText(InputChip, 'turkey or duck · at most 2 a week'),
      findsOneWidget,
    );
    final ProteinTarget target = (await stored(tester))!.proteinTargets.last;
    expect(target.protein, 'turkey_or_duck');
    expect(target.minPerWeek, isNull);
    expect(target.maxPerWeek, 2);
  });

  gleanWidgetTest('adding a protein that already has a target replaces it, so '
      'each protein has one', (tester) async {
    await pumpProfile(tester, seed: _filled);

    await openProteinDialog(tester);
    await fillProtein(tester, protein: 'fish', max: '3');
    await tester.tap(find.byKey(const Key('profile.entry.save')));
    await tester.pumpAndSettle();

    final List<ProteinTarget> targets = (await stored(tester))!.proteinTargets;
    expect(targets.single.protein, 'fish');
    expect(targets.single.minPerWeek, isNull);
    expect(targets.single.maxPerWeek, 3);
  });

  gleanWidgetTest('changing a target opens with its protein and counts and '
      'saves in place', (tester) async {
    await pumpProfile(tester, seed: _filled);

    await openProteinDialog(tester, editing: 'fish · at least 2 a week');
    expect(
      tester
          .widget<ChoiceChip>(
            find.descendant(
              of: find.byKey(const Key('profile.protein.fish')),
              matching: find.byType(ChoiceChip),
              matchRoot: true,
            ),
          )
          .selected,
      isTrue,
    );
    await fillProtein(tester, min: '1', max: '2');
    await tester.tap(find.byKey(const Key('profile.entry.save')));
    await tester.pumpAndSettle();

    final ProteinTarget target = (await stored(tester))!.proteinTargets.single;
    expect(proteinTargetLabel(target), 'fish · 1–2 a week');
  });

  gleanWidgetTest('the protein dialog fits a 320-wide phone at 2x text', (
    tester,
  ) async {
    await pumpProfile(
      tester,
      seed: _filled,
      size: const Size(320, 844),
      textScale: 2,
    );
    await scrollToBuild(
      tester,
      find.byKey(Key('profile.add.${ProfileLists.proteinTargets.title}')),
    );
    await openProteinDialog(tester);
    expect(tester.takeException(), isNull);
    await tester.ensureVisible(find.byKey(const Key('profile.protein.max')));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  for (final (String why, String? protein, String min, String max, String error)
      in <(String, String?, String, String, String)>[
        ('no protein', null, '', '2', 'Pick a protein'),
        ('no bound', 'beef', '', '', 'Give at least or at most'),
        ('more than seven', 'beef', '8', '', 'Use a number from 1 to 7'),
        ('at most nought', 'beef', '', '0', 'Use a number from 1 to 7'),
        (
          'least above most',
          'beef',
          '3',
          '1',
          'At least must not be more than at most',
        ),
      ]) {
    gleanWidgetTest('a protein target with $why is refused with a reason', (
      tester,
    ) async {
      await pumpProfile(tester, seed: _filled);

      await openProteinDialog(tester);
      await fillProtein(tester, protein: protein, min: min, max: max);
      await tester.tap(find.byKey(const Key('profile.entry.save')));
      await tester.pumpAndSettle();

      expect(find.text(error), findsOneWidget);
      expect((await stored(tester))!.toJson(), _filled.toJson());
    });
  }

  gleanWidgetTest('a deleted note comes back exactly on Undo', (tester) async {
    await pumpProfile(tester, seed: _filled);

    await tester.tap(
      find.byTooltip('Delete note: Asked for no fish on Mondays'),
    );
    await tester.pumpAndSettle();

    expect(find.text('Asked for no fish on Mondays'), findsNothing);
    expect(find.text('Note deleted'), findsOneWidget);
    expect((await stored(tester))!.notes.single.text, contains('rice'));

    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();

    expect(find.text('Asked for no fish on Mondays'), findsOneWidget);
    expect((await stored(tester))!.toJson(), _filled.toJson());
  });

  gleanWidgetTest(
    'spice is picked by tapping a chip, and cleared by tapping it '
    'again with an Undo',
    (tester) async {
      await pumpProfile(tester, seed: _filled);

      await tester.tap(find.widgetWithText(ChoiceChip, 'Hot'));
      await tester.pumpAndSettle();
      expect((await stored(tester))!.spiceTolerance, SpiceTolerance.hot);

      await tester.tap(find.widgetWithText(ChoiceChip, 'Hot'));
      await tester.pumpAndSettle();
      expect((await stored(tester))!.spiceTolerance, isNull);
      expect(find.text('Spice cleared'), findsOneWidget);

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect((await stored(tester))!.spiceTolerance, SpiceTolerance.hot);
    },
  );

  gleanWidgetTest('the free text saves as it is typed', (tester) async {
    await pumpProfile(tester, seed: _filled);

    await tester.enterText(
      labeledTextField('How your weeks go'),
      'Batch cook on Sunday',
    );
    await tester.enterText(labeledTextField("Who's at the table"), 'Just me');
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    final HouseholdProfile after = (await stored(tester))!;
    expect(after.habits, 'Batch cook on Sunday');
    expect(after.household, 'Just me');
  });

  gleanWidgetTest('free text still saves when the screen is left before typing '
      'pauses', (tester) async {
    await tester.binding.setSurfaceSize(const Size(420, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await profiles().save(userId: _userId, profile: _filled);
    await harness.pumpAt(tester, AppRoutes.settings.path);
    await pumpPastSkeleton(tester);
    unawaited(harness.router.pushNamed(AppRoutes.settingsProfile.name));
    await pumpPastSkeleton(tester);
    await tester.pumpAndSettle();

    await tester.enterText(labeledTextField("Who's at the table"), 'Just me');
    await tester.pump();
    await tester.pageBack();
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect((await stored(tester))!.household, 'Just me');
  });

  gleanWidgetTest('edits made on an empty profile are there when the screen '
      'is opened again', (tester) async {
    await pumpProfile(tester);

    await tester.tap(
      find.byKey(Key('profile.add.${ProfileLists.dislikedIngredients.title}')),
    );
    await tester.pumpAndSettle();
    await enterInDialog(tester, 'olives');
    await tester.tap(find.widgetWithText(ChoiceChip, 'Medium'));
    await tester.enterText(labeledTextField('How your weeks go'), 'Leftovers');
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    await releaseDriftTree(tester);
    await harness.pumpAt(tester, AppRoutes.settingsProfile.path);
    await pumpPastSkeleton(tester);
    await tester.pumpAndSettle();

    expect(find.widgetWithText(InputChip, 'olives'), findsOneWidget);
    expect(
      tester
          .widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'Medium'))
          .selected,
      isTrue,
    );
    expect(find.text('Leftovers'), findsOneWidget);
    expect(find.text("Glean doesn't know your tastes yet"), findsNothing);
  });

  gleanWidgetTest('leaving straight after a removal still saves it and still '
      'offers Undo', (tester) async {
    await tester.binding.setSurfaceSize(const Size(420, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await profiles().save(userId: _userId, profile: _filled);
    await harness.pumpAt(tester, AppRoutes.settings.path);
    await pumpPastSkeleton(tester);
    unawaited(harness.router.pushNamed(AppRoutes.settingsProfile.name));
    await pumpPastSkeleton(tester);
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Remove olives'));
    harness.router.pop();
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.text('Removed olives'), findsOneWidget);
    expect((await stored(tester))!.dislikedIngredients, <String>['mushrooms']);

    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();
    expect((await stored(tester))!.toJson(), _filled.toJson());
  });

  gleanWidgetTest('a free-text save that fails after the screen is left is '
      'still reported, on Settings', (tester) async {
    await tester.binding.setSurfaceSize(const Size(420, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await profiles().save(userId: _userId, profile: _filled);
    await harness.pumpAt(tester, AppRoutes.settings.path);
    await pumpPastSkeleton(tester);
    unawaited(harness.router.pushNamed(AppRoutes.settingsProfile.name));
    await pumpPastSkeleton(tester);
    await tester.pumpAndSettle();
    await tester.runAsync(
      () => harness.db.customStatement(
        'CREATE TRIGGER fail_profile_update BEFORE UPDATE ON household_profiles '
        "BEGIN SELECT RAISE(ABORT, 'test failure'); END",
      ),
    );

    await tester.enterText(labeledTextField("Who's at the table"), 'Just me');
    harness.router.pop();
    await tester.pumpAndSettle();

    expect(
      find.text('Could not save your profile. Try again.'),
      findsOneWidget,
    );
    expect((await stored(tester))!.household, 'Two adults, two kids');
  });

  gleanWidgetTest('a failed save says so and leaves the profile as it was', (
    tester,
  ) async {
    await pumpProfile(tester, seed: _filled);
    await tester.runAsync(
      () => harness.db.customStatement(
        'CREATE TRIGGER fail_profile_update BEFORE UPDATE ON household_profiles '
        "BEGIN SELECT RAISE(ABORT, 'test failure'); END",
      ),
    );

    await tester.tap(find.byTooltip('Remove olives'));
    await tester.pumpAndSettle();

    expect(find.text('Could not remove olives. Try again.'), findsOneWidget);
    expect(find.widgetWithText(InputChip, 'olives'), findsOneWidget);
    expect((await stored(tester))!.toJson(), _filled.toJson());
  });

  gleanWidgetTest('a profile that cannot be read says so, and Retry reads it '
      'again', (tester) async {
    int reads = 0;
    final AppTestHarness failing = AppTestHarness(
      overrides: <Override>[
        householdProfileProvider.overrideWith((ref) {
          reads++;
          return reads == 1
              ? Stream<HouseholdProfile?>.error(StateError('unreadable'))
              : Stream<HouseholdProfile?>.value(null);
        }),
      ],
    );
    addTearDown(failing.dispose);
    await failing.pumpAt(tester, AppRoutes.settingsProfile.path);
    await tester.pumpAndSettle();

    expect(find.text('Could not load your profile.'), findsOneWidget);
    await tester.tap(find.widgetWithText(TextButton, 'Retry'));
    await pumpPastSkeleton(tester);
    await tester.pumpAndSettle();

    expect(find.text("Glean doesn't know your tastes yet"), findsOneWidget);
  });

  for (final double scale in <double>[1, 2]) {
    gleanWidgetTest('a filled profile fits a 320-wide phone at ${scale}x text, '
        'down to the last note', (tester) async {
      await pumpProfile(
        tester,
        seed: _filled,
        size: const Size(320, 844),
        textScale: scale,
      );
      expect(tester.takeException(), isNull);

      // Step through the whole list so every row is built and laid out.
      final ScrollPosition position = tester
          .state<ScrollableState>(find.byType(Scrollable).first)
          .position;
      while (position.pixels < position.maxScrollExtent) {
        position.jumpTo(
          (position.pixels + 200).clamp(0, position.maxScrollExtent),
        );
        await tester.pump();
        expect(tester.takeException(), isNull, reason: 'at ${position.pixels}');
      }
      await tester.pumpAndSettle();
      expect(find.text('Prefers rice over pasta midweek'), findsOneWidget);

      await tester.tap(
        find.byTooltip('Delete note: Prefers rice over pasta midweek'),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull, reason: 'the undo snackbar');
    });
  }
}
