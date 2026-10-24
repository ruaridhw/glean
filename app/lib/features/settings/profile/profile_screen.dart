/// The household profile: what Glean knows about how the household eats, opened from Settings' "Your profile"
/// row. Auto-save, no Save button: every add, change and pick writes through
/// [HouseholdProfileRepository.update], and the screen redraws from the watched profile. Removing a chip or a
/// note is undone from the snackbar, which puts the same item back where it was.
///
/// The taste interview in first run fills this in; retaking it from here is not offered yet.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/household_profile_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/household_profile_repository.dart';
import 'package:glean/design_system/design_system.dart';

import 'profile_presentation.dart';
import 'widgets/profile_chip_list.dart';
import 'widgets/profile_entry_dialog.dart';
import 'widgets/profile_notes_card.dart';
import 'widgets/profile_text_field.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<HouseholdProfile?> asyncProfile = ref.watch(
      householdProfileProvider,
    );
    return Scaffold(
      appBar: AppBar(title: const Text('Your profile')),
      body: switch (asyncProfile) {
        AsyncData(:final HouseholdProfile? value) => _ProfileContent(
          profile: value ?? const HouseholdProfile(),
        ),
        AsyncError() => Center(
          child: Text(
            'Could not load your profile. Try again.',
            style: Theme.of(context).textTheme.bodyMedium,
            textAlign: TextAlign.center,
          ),
        ),
        _ => const ListSkeleton(rows: 4, rowHeight: 96),
      },
    );
  }
}

class _ProfileContent extends ConsumerStatefulWidget {
  const _ProfileContent({required this.profile});

  final HouseholdProfile profile;

  @override
  ConsumerState<_ProfileContent> createState() => _ProfileContentState();
}

class _ProfileContentState extends ConsumerState<_ProfileContent> {
  // Captured once: a free-text field still saves while this screen is being popped, when `ref` is gone.
  late final HouseholdProfileRepository _profiles = ref.read(
    householdProfileRepositoryProvider,
  );
  late final String _userId = ref.read(currentUserIdProvider);

  Future<void> _change(
    HouseholdProfile Function(HouseholdProfile current) change,
  ) async {
    try {
      await _profiles.update(userId: _userId, change: change);
    } catch (_) {
      if (!mounted) return;
      GleanSnackBar.show(context, 'Could not save your profile. Try again.');
    }
  }

  Future<void> _add<T>(ProfileList<T> list) async {
    final String? text = await showDialog<String>(
      context: context,
      builder: (BuildContext _) => ProfileEntryDialog(
        title: 'Add to ${list.title.toLowerCase()}',
        saveLabel: 'Add',
      ),
    );
    if (text == null || !mounted) return;
    if (list.isTaken(widget.profile, text)) {
      GleanSnackBar.show(context, '$text is already there');
      return;
    }
    await _change((HouseholdProfile p) => list.add(p, text));
    if (mounted) ref.read(hapticsProvider).mediumImpact();
  }

  Future<void> _edit<T>(ProfileList<T> list, int index) async {
    final T item = list.read(widget.profile)[index];
    final String current = list.label(item);
    final String? text = await showDialog<String>(
      context: context,
      builder: (BuildContext _) => ProfileEntryDialog(
        title: 'Change ${list.title.toLowerCase()}',
        saveLabel: 'Save',
        initial: current,
      ),
    );
    if (text == null || !mounted) return;
    if (list.isTaken(widget.profile, text, except: index)) {
      GleanSnackBar.show(context, '$text is already there');
      return;
    }
    await _change((HouseholdProfile p) {
      final int at = list.locate(p, index, item);
      return at == -1 ? p : list.editAt(p, at, text);
    });
    if (mounted) ref.read(hapticsProvider).mediumImpact();
  }

  Future<void> _editProteinTarget([int? index]) async {
    const ProfileList<ProteinTarget> list = ProfileLists.proteinTargets;
    final ProteinTarget? current = index == null
        ? null
        : list.read(widget.profile)[index];
    final ProteinTarget? target = await showDialog<ProteinTarget>(
      context: context,
      builder: (BuildContext _) => ProteinTargetDialog(
        title: current == null ? 'Add a protein' : 'Change how often',
        saveLabel: current == null ? 'Add' : 'Save',
        initial: current,
      ),
    );
    if (target == null || !mounted) return;
    await _change(
      (HouseholdProfile p) =>
          setProteinTarget(p, target, replacing: current?.protein),
    );
    if (mounted) ref.read(hapticsProvider).mediumImpact();
  }

  /// Removes the item at [index] of [list] with an Undo that puts the same item back at the same place.
  Future<void> _remove<T>(
    ProfileList<T> list,
    int index, {
    String? message,
    String? failureMessage,
  }) {
    final T item = list.read(widget.profile)[index];
    final String label = list.label(item);
    // Read before the write: the screen may be gone by the time it lands, and the snackbar must still show.
    final Haptics haptics = ref.read(hapticsProvider);
    return GleanSnackBar.runUndoable<int>(
      context,
      perform: () async {
        int removedAt = -1;
        await _profiles.update(
          userId: _userId,
          change: (HouseholdProfile p) {
            removedAt = list.locate(p, index, item);
            return removedAt == -1 ? p : list.removeAt(p, removedAt);
          },
        );
        return removedAt;
      },
      undo: (int removedAt) async {
        if (removedAt == -1) return;
        await _profiles.update(
          userId: _userId,
          change: (HouseholdProfile p) => list.insertAt(p, removedAt, item),
        );
      },
      message: message ?? 'Removed $label',
      failureMessage: failureMessage ?? 'Could not remove $label. Try again.',
      undoFailureMessage: 'Could not put $label back. Try again.',
      onSuccess: haptics.mediumImpact,
    );
  }

  /// Clears the spice answer with an Undo that restores it, unless another answer was picked meanwhile.
  Future<void> _clearSpice() {
    return GleanSnackBar.runUndoable<SpiceTolerance?>(
      context,
      perform: () async {
        SpiceTolerance? previous;
        await _profiles.update(
          userId: _userId,
          change: (HouseholdProfile p) {
            previous = p.spiceTolerance;
            return p.withSpiceTolerance(null);
          },
        );
        return previous;
      },
      undo: (SpiceTolerance? previous) => _profiles.update(
        userId: _userId,
        change: (HouseholdProfile p) =>
            p.spiceTolerance == null ? p.withSpiceTolerance(previous) : p,
      ),
      message: 'Spice cleared',
      failureMessage: 'Could not clear spice. Try again.',
      undoFailureMessage: 'Could not put spice back. Try again.',
    );
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final HouseholdProfile profile = widget.profile;
    final TextTheme text = Theme.of(context).textTheme;

    Widget section(String title, Widget child) => Padding(
      padding: EdgeInsets.only(top: tokens.spacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          _SectionLabel(title),
          SizedBox(height: tokens.spacing.sm),
          child,
        ],
      ),
    );

    Widget chips<T>(ProfileList<T> list) => section(
      list.title,
      ProfileChipList(
        title: list.title,
        labels: list.read(profile).map(list.label).toList(),
        onAdd: () => unawaited(_add(list)),
        onEdit: (int i) => unawaited(_edit(list, i)),
        onRemove: (int i) => unawaited(_remove(list, i)),
      ),
    );

    return ListView(
      padding: EdgeInsets.all(tokens.spacing.lg),
      children: <Widget>[
        if (profile.isEmpty)
          Card(
            child: Padding(
              padding: EdgeInsets.all(tokens.spacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    "Glean doesn't know your tastes yet",
                    style: text.titleMedium,
                  ),
                  SizedBox(height: tokens.spacing.xs),
                  Text(
                    'The taste questions when you first set up Glean fill '
                    'this in. You can also add things yourself below.',
                    style: text.bodyMedium,
                  ),
                ],
              ),
            ),
          )
        else
          Text(
            'What Glean knows about how you eat. Tap anything to change it.',
            style: text.bodyMedium,
          ),
        chips(ProfileLists.favouriteMeals),
        for (final ProfileList<String> list in ProfileLists.textLists)
          chips(list),
        section(
          ProfileLists.proteinTargets.title,
          ProfileChipList(
            title: ProfileLists.proteinTargets.title,
            labels: profile.proteinTargets.map(proteinTargetLabel).toList(),
            onAdd: () => unawaited(_editProteinTarget()),
            onEdit: (int i) => unawaited(_editProteinTarget(i)),
            onRemove: (int i) =>
                unawaited(_remove(ProfileLists.proteinTargets, i)),
          ),
        ),
        section(
          'How spicy',
          Card(
            child: Padding(
              padding: EdgeInsets.all(tokens.spacing.md),
              child: Wrap(
                spacing: tokens.spacing.sm,
                runSpacing: tokens.spacing.sm,
                children: <Widget>[
                  for (final SpiceTolerance spice in SpiceTolerance.values)
                    ChoiceChip(
                      label: Text(spiceLabel(spice)),
                      selected: profile.spiceTolerance == spice,
                      onSelected: (bool selected) {
                        ref.read(hapticsProvider).selectionClick();
                        unawaited(
                          selected
                              ? _change(
                                  (HouseholdProfile p) =>
                                      p.withSpiceTolerance(spice),
                                )
                              : _clearSpice(),
                        );
                      },
                    ),
                ],
              ),
            ),
          ),
        ),
        SizedBox(height: tokens.spacing.lg),
        ProfileTextField(
          label: 'How your weeks go',
          hint: 'e.g. quick weeknights, batch cook on Sunday',
          value: profile.habits,
          onSave: (String habits) => unawaited(
            _change((HouseholdProfile p) => p.copyWith(habits: habits)),
          ),
        ),
        SizedBox(height: tokens.spacing.md),
        ProfileTextField(
          label: "Who's at the table",
          hint: 'e.g. two adults, two kids',
          value: profile.household,
          onSave: (String household) => unawaited(
            _change((HouseholdProfile p) => p.copyWith(household: household)),
          ),
        ),
        section(
          ProfileLists.notes.title,
          ProfileNotesCard(
            notes: profile.notes,
            onDelete: (int i) => unawaited(
              _remove(
                ProfileLists.notes,
                i,
                message: 'Note deleted',
                failureMessage: 'Could not delete the note. Try again.',
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// A small uppercase section heading, as in Settings.
class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: Theme.of(context).textTheme.labelSmall,
    );
  }
}
