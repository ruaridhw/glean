// The Profile screen and the Settings summary row are thin over these pure rules: which list an edit lands in,
// how a removed item comes back exactly where it was, and what one line says about a profile.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/features/settings/profile/profile_presentation.dart';

const HouseholdProfile _filled = HouseholdProfile(
  favouriteMeals: <FavouriteMeal>[
    FavouriteMeal(text: 'Katsu curry', recipeId: 'rec_1'),
    FavouriteMeal(text: 'Fish pie'),
    FavouriteMeal(text: 'Dal', recipeId: 'rec_3'),
  ],
  lovedIngredients: <String>['miso'],
  dislikedIngredients: <String>['mushrooms', 'olives'],
  cuisinesLiked: <String>['Indian', 'Japanese'],
  cuisinesAvoided: <String>['Thai'],
  proteinTargets: <ProteinTarget>[
    ProteinTarget(protein: 'fish', minPerWeek: 2),
  ],
  spiceTolerance: SpiceTolerance.mild,
  habits: 'Quick weeknights, treat Friday',
  household: 'Two adults, two kids',
  notes: <ProfileNote>[
    ProfileNote(
      date: '2026-10-24',
      text: 'Prefers rice over pasta midweek',
      source: ProfileNoteSource.feedback,
    ),
  ],
);

void main() {
  group('profileSummary', () {
    test('no profile and an empty one both read as not set up yet', () {
      const String empty = 'Nothing yet: tell Glean what you love and avoid';
      expect(profileSummary(null), empty);
      expect(profileSummary(const HouseholdProfile()), empty);
    });

    test('a partial profile names only what is set', () {
      expect(
        profileSummary(
          const HouseholdProfile(
            favouriteMeals: <FavouriteMeal>[FavouriteMeal(text: 'Dal')],
          ),
        ),
        '1 favourite',
      );
      expect(
        profileSummary(const HouseholdProfile(habits: 'Leftovers on Monday')),
        'leftovers on Monday',
      );
      expect(
        profileSummary(
          const HouseholdProfile(
            notes: <ProfileNote>[
              ProfileNote(
                date: '2026-10-24',
                text: 'Likes rice',
                source: ProfileNoteSource.feedback,
              ),
            ],
          ),
        ),
        '1 note',
      );
    });

    test('a full profile leads with counts, then how the weeks go', () {
      expect(
        profileSummary(_filled),
        startsWith('3 favourites · 3 never · 3 loved · quick weeknights'),
      );
    });
  });

  group('ProfileList', () {
    test('every editable list reads and writes its own field', () {
      for (final ProfileList<String> list in <ProfileList<String>>[
        ProfileLists.lovedIngredients,
        ProfileLists.dislikedIngredients,
        ProfileLists.cuisinesLiked,
        ProfileLists.cuisinesAvoided,
      ]) {
        final HouseholdProfile added = list.add(_filled, 'new thing');
        expect(list.read(added).last, 'new thing', reason: list.title);
        final int changed = <List<String>>[
          added.lovedIngredients,
          added.dislikedIngredients,
          added.cuisinesLiked,
          added.cuisinesAvoided,
        ].where((List<String> l) => l.contains('new thing')).length;
        expect(changed, 1, reason: '${list.title} touched another list');
      }
    });

    test('adding trims, and skips blanks and anything already there', () {
      const ProfileList<String> list = ProfileLists.dislikedIngredients;
      expect(list.read(list.add(_filled, '  capers ')).last, 'capers');
      expect(list.add(_filled, '   '), same(_filled));
      expect(list.add(_filled, 'Olives'), same(_filled));
    });

    test('editing a favourite keeps its recipe when the text is unchanged '
        'and drops it when the text changes', () {
      const ProfileList<FavouriteMeal> list = ProfileLists.favouriteMeals;
      final FavouriteMeal kept = list
          .read(list.editAt(_filled, 0, 'Katsu curry'))
          .first;
      expect(kept.recipeId, 'rec_1');

      final FavouriteMeal renamed = list
          .read(list.editAt(_filled, 0, 'Chicken katsu'))
          .first;
      expect(renamed.text, 'Chicken katsu');
      expect(renamed.recipeId, isNull);
    });

    test('a removed item comes back at the same place with everything it '
        'carried', () {
      const ProfileList<FavouriteMeal> list = ProfileLists.favouriteMeals;
      final FavouriteMeal dal = list.read(_filled)[2];
      final FavouriteMeal pie = list.read(_filled)[1];

      final HouseholdProfile removed = list.removeAt(_filled, 1);
      expect(list.read(removed).map((FavouriteMeal m) => m.text), <String>[
        'Katsu curry',
        'Dal',
      ]);
      final HouseholdProfile restored = list.insertAt(removed, 1, pie);
      expect(restored.toJson(), _filled.toJson());
      expect(list.read(restored)[2].recipeId, dal.recipeId);
    });

    test('a note removed and restored is the same note in the same place', () {
      const ProfileList<ProfileNote> list = ProfileLists.notes;
      final ProfileNote note = list.read(_filled).single;
      final HouseholdProfile restored = list.insertAt(
        list.removeAt(_filled, 0),
        0,
        note,
      );
      expect(restored.toJson(), _filled.toJson());
    });

    test('restoring past the end of a list that shrank meanwhile appends', () {
      const ProfileList<String> list = ProfileLists.dislikedIngredients;
      final HouseholdProfile restored = list.insertAt(
        const HouseholdProfile(),
        3,
        'olives',
      );
      expect(list.read(restored), <String>['olives']);
    });

    test('indexOf finds an item by what it says, ignoring case', () {
      expect(ProfileLists.dislikedIngredients.indexOf(_filled, 'OLIVES'), 1);
      expect(ProfileLists.dislikedIngredients.indexOf(_filled, 'capers'), -1);
    });
  });

  group('no duplicate chips', () {
    const ProfileList<String> never = ProfileLists.dislikedIngredients;

    test(
      'putting an item back skips it when the same label is there again',
      () {
        final HouseholdProfile removed = never.removeAt(_filled, 1);
        final HouseholdProfile readded = never.add(removed, 'Olives');
        final HouseholdProfile undone = never.insertAt(readded, 1, 'olives');
        expect(never.read(undone), <String>['mushrooms', 'Olives']);
      },
    );

    test('an edit into another item already there is refused', () {
      expect(never.editAt(_filled, 0, ' OLIVES '), same(_filled));
      expect(never.replaceAt(_filled, 0, 'olives'), same(_filled));
    });

    test('an edit that only changes case is allowed, and a favourite keeps '
        'its recipe', () {
      expect(never.read(never.editAt(_filled, 1, 'Olives'))[1], 'Olives');
      const ProfileList<FavouriteMeal> favourites = ProfileLists.favouriteMeals;
      final FavouriteMeal edited = favourites
          .read(favourites.editAt(_filled, 0, 'katsu curry'))
          .first;
      expect(edited.text, 'katsu curry');
      expect(edited.recipeId, 'rec_1');
    });

    test('locate prefers the tapped position, so the second of two equal '
        'chips is the one acted on', () {
      const ProfileList<FavouriteMeal> favourites = ProfileLists.favouriteMeals;
      const HouseholdProfile twins = HouseholdProfile(
        favouriteMeals: <FavouriteMeal>[
          FavouriteMeal(text: 'Dal', recipeId: 'rec_3'),
          FavouriteMeal(text: 'Dal'),
        ],
      );
      final FavouriteMeal second = favourites.read(twins)[1];
      expect(favourites.locate(twins, 1, second), 1);
      final HouseholdProfile left = favourites.removeAt(
        twins,
        favourites.locate(twins, 1, second),
      );
      expect(favourites.read(left).single.recipeId, 'rec_3');
    });

    test('locate falls back to the label when the list moved, and gives -1 '
        'when the item is gone', () {
      expect(never.locate(_filled, 0, 'olives'), 1);
      expect(never.locate(_filled, 0, 'capers'), -1);
      expect(never.locate(_filled, 9, 'mushrooms'), 0);
    });
  });

  group('protein targets', () {
    test('are picked from the main-protein values, without mixed or none', () {
      expect(mainProteins, <String>[
        'chicken',
        'turkey_or_duck',
        'beef',
        'pork',
        'lamb',
        'fish',
        'seafood',
        'beans_and_pulses',
        'tofu_or_plant_protein',
        'vegetarian_other',
      ]);
      expect(proteinName('turkey_or_duck'), 'turkey or duck');
      expect(proteinName('vegetarian_other'), 'other vegetarian');
    });

    test('there is one target per protein: setting one that exists replaces '
        'it in place', () {
      final HouseholdProfile twice = setProteinTarget(
        _filled.copyWith(
          proteinTargets: const <ProteinTarget>[
            ProteinTarget(protein: 'chicken', maxPerWeek: 2),
            ProteinTarget(protein: 'fish', minPerWeek: 2),
          ],
        ),
        const ProteinTarget(protein: 'fish', maxPerWeek: 1),
      );
      expect(twice.proteinTargets.map(proteinTargetLabel), <String>[
        'chicken · at most 2 a week',
        'fish · at most 1 a week',
      ]);
    });

    test('changing a target to another protein that has one leaves one '
        'target for it, where the changed one was', () {
      final HouseholdProfile changed = setProteinTarget(
        _filled.copyWith(
          proteinTargets: const <ProteinTarget>[
            ProteinTarget(protein: 'chicken', maxPerWeek: 2),
            ProteinTarget(protein: 'beef', maxPerWeek: 1),
            ProteinTarget(protein: 'fish', minPerWeek: 2),
          ],
        ),
        const ProteinTarget(protein: 'fish', minPerWeek: 3),
        replacing: 'chicken',
      );
      expect(changed.proteinTargets.map(proteinTargetLabel), <String>[
        'fish · at least 3 a week',
        'beef · at most 1 a week',
      ]);
    });

    test('a target needs a bound, counts run 1 to 7, and at least is not '
        'above at most', () {
      expect(proteinTargetError(null, null), 'Give at least or at most');
      expect(proteinTargetError(0, null), 'Use a number from 1 to 7');
      expect(proteinTargetError(null, 0), 'Use a number from 1 to 7');
      expect(proteinTargetError(8, null), 'Use a number from 1 to 7');
      expect(
        proteinTargetError(3, 1),
        'At least must not be more than at most',
      );
      expect(proteinTargetError(1, 7), isNull);
      expect(proteinTargetError(null, 2), isNull);
    });

    test('a stored target of at most 0 reads as never', () {
      expect(
        proteinTargetLabel(const ProteinTarget(protein: 'beef', maxPerWeek: 0)),
        'beef · never',
      );
    });
  });

  group('labels', () {
    test('protein targets say how often', () {
      expect(
        proteinTargetLabel(
          const ProteinTarget(protein: 'fish', minPerWeek: 2, maxPerWeek: 3),
        ),
        'fish · 2–3 a week',
      );
      expect(
        proteinTargetLabel(const ProteinTarget(protein: 'fish', minPerWeek: 2)),
        'fish · at least 2 a week',
      );
      expect(
        proteinTargetLabel(
          const ProteinTarget(protein: 'red meat', maxPerWeek: 1),
        ),
        'red meat · at most 1 a week',
      );
      expect(
        proteinTargetLabel(
          const ProteinTarget(protein: 'fish', minPerWeek: 2, maxPerWeek: 2),
        ),
        'fish · 2 a week',
      );
      expect(proteinTargetLabel(const ProteinTarget(protein: 'tofu')), 'tofu');
    });

    test('a note says when and where it came from', () {
      expect(
        noteMeta(
          const ProfileNote(
            date: '2026-10-04',
            text: 'x',
            source: ProfileNoteSource.interview,
          ),
        ),
        '4 Oct 2026 · from the interview',
      );
      expect(
        noteMeta(
          const ProfileNote(
            date: 'someday',
            text: 'x',
            source: ProfileNoteSource.feedback,
          ),
        ),
        'someday · from your feedback',
      );
    });
  });
}
