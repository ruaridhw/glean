/// The Pantry tab (FLUTTER_MIGRATION.md §6 Pantry) — the landing tab
/// (AC-SET-05).
///
/// Reads are a `StreamProvider` over drift `.watch()` (AC-DATA-04): there is
/// no on-focus reload and no manual `loading` flag, so — unlike the RN
/// screen, which set `loading = true` unconditionally on every focus — the
/// skeleton is structurally impossible to re-flash on a tab switch; it can
/// only ever show before the very first stream event.
library;

import 'dart:async' show unawaited;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/data/providers/pantry_providers.dart';
import 'package:glean/design_system/design_system.dart';

import 'actions.dart';
import 'widgets/pantry_add_sheet.dart';
import 'widgets/pantry_body.dart';
import 'widgets/pantry_skeleton.dart';

class PantryScreen extends ConsumerStatefulWidget {
  const PantryScreen({super.key});

  @override
  ConsumerState<PantryScreen> createState() => _PantryScreenState();
}

class _PantryScreenState extends ConsumerState<PantryScreen> {
  String? _filterKey;

  @override
  Widget build(BuildContext context) {
    final AsyncValue<List<PantryItemView>> async = ref.watch(
      pantryItemsProvider,
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Pantry'),
        actions: <Widget>[
          IconButton(
            icon: const Icon(Icons.add_rounded),
            tooltip: 'Add to pantry',
            onPressed: () => PantryAddSheet.show(context),
          ),
        ],
      ),
      body: GleanCrossFade(
        showSkeleton: !async.hasValue,
        skeleton: const PantrySkeleton(),
        content: async.maybeWhen(
          data: (List<PantryItemView> items) => PantryBody(
            items: items,
            filterKey: _filterKey,
            onFilterChanged: (String? key) => setState(() => _filterKey = key),
            onDelete: (PantryItemView item) =>
                unawaited(deletePantryItemWithUndo(context, ref, item)),
          ),
          orElse: () => const _PantryLoadError(),
        ),
      ),
    );
  }
}

class _PantryLoadError extends StatelessWidget {
  const _PantryLoadError();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: EdgeInsets.all(context.tokens.spacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(
              Icons.error_outline_rounded,
              color: Theme.of(context).colorScheme.error,
            ),
            SizedBox(height: context.tokens.spacing.sm),
            const Text('Could not load your pantry.'),
          ],
        ),
      ),
    );
  }
}
