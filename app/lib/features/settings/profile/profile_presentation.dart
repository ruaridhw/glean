/// Pure rules behind the Profile screen and the Settings summary row: how each list of the household profile is
/// edited, how a removed item is put back exactly where it was, and what one line says about a profile. No
/// Flutter import on purpose, so it is testable without a widget tree.
library;

import 'package:glean/data/models/household_profile.dart';

/// One list in the household profile, with the operations the Profile screen needs on it. Every operation
/// returns a new profile and leaves every other field alone.
class ProfileList<T> {
  const ProfileList({
    required this.title,
    required this.read,
    required this.write,
    required this.label,
    this.fromText,
  });

  /// The heading the Profile screen shows above the list.
  final String title;
  final List<T> Function(HouseholdProfile profile) read;
  final HouseholdProfile Function(HouseholdProfile profile, List<T> items)
  write;

  /// What the item says on its chip; also how two items count as the same.
  final String Function(T item) label;

  /// Builds an item from typed text, given the item it replaces when editing. `null` for lists that are not
  /// edited as plain text.
  final T Function(String text, T? previous)? fromText;

  /// The position of the item whose label is [itemLabel], ignoring case and surrounding space, or -1.
  int indexOf(HouseholdProfile profile, String itemLabel) {
    final String wanted = _key(itemLabel);
    return read(profile).indexWhere((T item) => _key(label(item)) == wanted);
  }

  /// Where [item], last seen at [index], is now: [index] while the item there still says exactly the same,
  /// so the chip that was tapped is the one acted on even beside an equal one; else the first item that says
  /// the same; else -1.
  int locate(HouseholdProfile profile, int index, T item) {
    final List<T> items = read(profile);
    final String wanted = label(item);
    if (index >= 0 && index < items.length && label(items[index]) == wanted) {
      return index;
    }
    return items.indexWhere((T other) => label(other) == wanted);
  }

  /// Whether [itemLabel] repeats an item already there, other than the one at [except] (the item being
  /// changed, which may change case).
  bool isTaken(HouseholdProfile profile, String itemLabel, {int? except}) {
    final int at = indexOf(profile, itemLabel);
    return at != -1 && at != except;
  }

  /// Appends [item], unless an item with the same label is already there.
  HouseholdProfile addItem(HouseholdProfile profile, T item) {
    if (isTaken(profile, label(item))) return profile;
    return write(profile, <T>[...read(profile), item]);
  }

  /// Appends the item [text] describes. Blank text, or text already in the list, changes nothing.
  HouseholdProfile add(HouseholdProfile profile, String text) {
    final String trimmed = text.trim();
    if (trimmed.isEmpty) return profile;
    return addItem(profile, fromText!(trimmed, null));
  }

  /// Replaces the item at [index], unless [item] repeats a different item already there.
  HouseholdProfile replaceAt(HouseholdProfile profile, int index, T item) {
    if (isTaken(profile, label(item), except: index)) return profile;
    return write(profile, <T>[...read(profile)]..[index] = item);
  }

  /// Replaces the item at [index] with what [text] describes. Blank text, or text repeating a different item,
  /// changes nothing.
  HouseholdProfile editAt(HouseholdProfile profile, int index, String text) {
    final String trimmed = text.trim();
    if (trimmed.isEmpty) return profile;
    return replaceAt(profile, index, fromText!(trimmed, read(profile)[index]));
  }

  HouseholdProfile removeAt(HouseholdProfile profile, int index) =>
      write(profile, <T>[...read(profile)]..removeAt(index));

  /// Puts [item] back at [index], or at the end when the list has since become shorter than that. Skipped when
  /// an item with the same label has been added meanwhile, so Undo never makes a second chip.
  HouseholdProfile insertAt(HouseholdProfile profile, int index, T item) {
    if (isTaken(profile, label(item))) return profile;
    final List<T> items = <T>[...read(profile)];
    return write(profile, items..insert(index.clamp(0, items.length), item));
  }
}

String _key(String label) => label.trim().toLowerCase();

/// The lists the Profile screen edits, in the order it shows them.
abstract final class ProfileLists {
  static const ProfileList<FavouriteMeal> favouriteMeals =
      ProfileList<FavouriteMeal>(
        title: 'Favourite dinners',
        read: _favouriteMeals,
        write: _writeFavouriteMeals,
        label: _favouriteLabel,
        fromText: _favouriteFromText,
      );
  static const ProfileList<String> lovedIngredients = ProfileList<String>(
    title: 'Ingredients you love',
    read: _lovedIngredients,
    write: _writeLovedIngredients,
    label: _same,
    fromText: _text,
  );
  static const ProfileList<String> dislikedIngredients = ProfileList<String>(
    title: 'Never on the plan',
    read: _dislikedIngredients,
    write: _writeDislikedIngredients,
    label: _same,
    fromText: _text,
  );
  static const ProfileList<String> cuisinesLiked = ProfileList<String>(
    title: 'Cuisines you like',
    read: _cuisinesLiked,
    write: _writeCuisinesLiked,
    label: _same,
    fromText: _text,
  );
  static const ProfileList<String> cuisinesAvoided = ProfileList<String>(
    title: 'Cuisines you avoid',
    read: _cuisinesAvoided,
    write: _writeCuisinesAvoided,
    label: _same,
    fromText: _text,
  );
  static const ProfileList<ProteinTarget> proteinTargets =
      ProfileList<ProteinTarget>(
        title: 'How often each protein',
        read: _proteinTargets,
        write: _writeProteinTargets,
        label: proteinTargetLabel,
      );
  static const ProfileList<ProfileNote> notes = ProfileList<ProfileNote>(
    title: 'Things Glean noted',
    read: _notes,
    write: _writeNotes,
    label: _noteLabel,
  );

  /// The plain-text lists, edited as chips.
  static const List<ProfileList<String>> textLists = <ProfileList<String>>[
    lovedIngredients,
    dislikedIngredients,
    cuisinesLiked,
    cuisinesAvoided,
  ];
}

List<FavouriteMeal> _favouriteMeals(HouseholdProfile p) => p.favouriteMeals;
HouseholdProfile _writeFavouriteMeals(
  HouseholdProfile p,
  List<FavouriteMeal> items,
) => p.copyWith(favouriteMeals: items);
String _favouriteLabel(FavouriteMeal meal) => meal.text;

/// An edit that changes only case or spacing keeps the matched recipe; new words no longer match it.
FavouriteMeal _favouriteFromText(String text, FavouriteMeal? previous) =>
    FavouriteMeal(
      text: text,
      recipeId: previous != null && _key(previous.text) == _key(text)
          ? previous.recipeId
          : null,
    );

List<String> _lovedIngredients(HouseholdProfile p) => p.lovedIngredients;
HouseholdProfile _writeLovedIngredients(
  HouseholdProfile p,
  List<String> items,
) => p.copyWith(lovedIngredients: items);
List<String> _dislikedIngredients(HouseholdProfile p) => p.dislikedIngredients;
HouseholdProfile _writeDislikedIngredients(
  HouseholdProfile p,
  List<String> items,
) => p.copyWith(dislikedIngredients: items);
List<String> _cuisinesLiked(HouseholdProfile p) => p.cuisinesLiked;
HouseholdProfile _writeCuisinesLiked(HouseholdProfile p, List<String> items) =>
    p.copyWith(cuisinesLiked: items);
List<String> _cuisinesAvoided(HouseholdProfile p) => p.cuisinesAvoided;
HouseholdProfile _writeCuisinesAvoided(
  HouseholdProfile p,
  List<String> items,
) => p.copyWith(cuisinesAvoided: items);
List<ProteinTarget> _proteinTargets(HouseholdProfile p) => p.proteinTargets;
HouseholdProfile _writeProteinTargets(
  HouseholdProfile p,
  List<ProteinTarget> items,
) => p.copyWith(proteinTargets: items);
List<ProfileNote> _notes(HouseholdProfile p) => p.notes;
HouseholdProfile _writeNotes(HouseholdProfile p, List<ProfileNote> items) =>
    p.copyWith(notes: items);
String _noteLabel(ProfileNote note) => '${note.date} ${note.text}';
String _same(String value) => value;
String _text(String text, String? _) => text;

/// The corpus `main_protein` values a target can name, in the order the picker shows them. `mixed` and `none`
/// are left out: neither is a protein a household would want more or less of.
const List<String> mainProteins = <String>[
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
];

/// How a `main_protein` value reads, e.g. `turkey or duck`. A value this build does not know reads as stored.
String proteinName(String protein) => switch (protein) {
  'vegetarian_other' => 'other vegetarian',
  _ => protein.replaceAll('_', ' '),
};

/// The most dinners a week, so the most times one protein can appear.
const int maxPerWeekCap = 7;

/// Why a target with these bounds cannot be saved, or `null` when it can: it needs at least one bound, each
/// from 1 to [maxPerWeekCap], and at least may not exceed at most.
String? proteinTargetError(int? min, int? max) {
  if (min == null && max == null) return 'Give at least or at most';
  bool outOfRange(int? n) => n != null && (n < 1 || n > maxPerWeekCap);
  if (outOfRange(min) || outOfRange(max)) {
    return 'Use a number from 1 to $maxPerWeekCap';
  }
  if (min != null && max != null && min > max) {
    return 'At least must not be more than at most';
  }
  return null;
}

/// Stores [target] as its protein's one target. It takes the place of the target for [replacing] (the protein
/// being changed) when given, else of the protein's existing target, else goes at the end; any other target for
/// the same protein is dropped.
HouseholdProfile setProteinTarget(
  HouseholdProfile profile,
  ProteinTarget target, {
  String? replacing,
}) {
  final List<ProteinTarget> targets = profile.proteinTargets;
  int at = replacing == null
      ? -1
      : targets.indexWhere((ProteinTarget t) => t.protein == replacing);
  if (at == -1) {
    at = targets.indexWhere((ProteinTarget t) => t.protein == target.protein);
  }
  final List<ProteinTarget> next = <ProteinTarget>[
    for (final (int i, ProteinTarget t) in targets.indexed)
      if (i == at) target else if (t.protein != target.protein) t,
  ];
  if (at == -1) next.add(target);
  return profile.copyWith(proteinTargets: next);
}

/// e.g. `fish · 2–3 a week`, `fish · at least 2 a week`, or just `fish` with no bounds.
String proteinTargetLabel(ProteinTarget target) {
  final int? min = target.minPerWeek;
  final int? max = target.maxPerWeek;
  final String? often = switch ((min, max)) {
    (_, 0) => 'never',
    (final int lo, final int hi) when lo == hi => '$lo a week',
    (final int lo, final int hi) => '$lo–$hi a week',
    (final int lo, null) => 'at least $lo a week',
    (null, final int hi) => 'at most $hi a week',
    (null, null) => null,
  };
  final String name = proteinName(target.protein);
  return often == null ? name : '$name · $often';
}

/// How the spice choice reads on its chip.
String spiceLabel(SpiceTolerance value) => switch (value) {
  SpiceTolerance.none => 'Not at all',
  SpiceTolerance.mild => 'Mild',
  SpiceTolerance.medium => 'Medium',
  SpiceTolerance.hot => 'Hot',
};

const List<String> _months = <String>[
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

/// When a note was kept and where it came from, e.g. `4 Oct 2026 · from the interview`. A date that is not
/// `YYYY-MM-DD` shows as written.
String noteMeta(ProfileNote note) {
  final DateTime? date = DateTime.tryParse(note.date);
  final String when = date == null
      ? note.date
      : '${date.day} ${_months[date.month - 1]} ${date.year}';
  final String from = switch (note.source) {
    ProfileNoteSource.interview => 'from the interview',
    ProfileNoteSource.feedback => 'from your feedback',
  };
  return '$when · $from';
}

/// The one line Settings shows for the profile: favourites and nevers first, then how the weeks go, then the
/// rest. Loved things are not counted, as in the design, so the habits stay in view.
String profileSummary(HouseholdProfile? profile) {
  if (profile == null || profile.isEmpty) {
    return 'Nothing yet: tell Glean what you love and avoid';
  }
  String count(int n, String one, [String? many]) =>
      '$n ${n == 1 ? one : (many ?? '${one}s')}';
  final int never =
      profile.dislikedIngredients.length + profile.cuisinesAvoided.length;
  return <String>[
    if (profile.favouriteMeals.isNotEmpty)
      count(profile.favouriteMeals.length, 'favourite'),
    if (never > 0) '$never never',
    if (profile.habits.isNotEmpty) _firstClause(profile.habits),
    if (profile.household.isNotEmpty) _firstClause(profile.household),
    if (profile.proteinTargets.isNotEmpty)
      count(profile.proteinTargets.length, 'protein target'),
    if (profile.spiceTolerance case final SpiceTolerance spice)
      'spice: ${spiceLabel(spice).toLowerCase()}',
    if (profile.notes.isNotEmpty) count(profile.notes.length, 'note'),
  ].join(' · ');
}

/// The first non-empty clause of [text]: up to a comma, full stop, semicolon or line break, as written.
String _firstClause(String text) => text
    .split(RegExp(r'[,.;\n]'))
    .map((String clause) => clause.trim())
    .firstWhere((String clause) => clause.isNotEmpty, orElse: text.trim);
