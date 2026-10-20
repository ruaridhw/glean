/// Manual pantry entry, reachable from the `+` sheet whether the pantry is empty or full. With no LLM
/// classification behind a typed item, this is the one intake surface that must ask for an ingredient group directly,
/// which is also what lets expiry inference fire.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/seed/ingredient_groups.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/pantry_repository.dart'
    show PantryUnitMismatchException;
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';

import '../pantry/pantry_presentation.dart';

const List<String> _commonUnits = <String>['g', 'ml', 'units', 'kg', 'l'];

class ManualEntryScreen extends ConsumerStatefulWidget {
  const ManualEntryScreen({super.key});

  @override
  ConsumerState<ManualEntryScreen> createState() => _ManualEntryScreenState();
}

class _ManualEntryScreenState extends ConsumerState<ManualEntryScreen> {
  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _quantityController = TextEditingController();
  String _unit = _commonUnits.first;
  String? _groupId;
  bool _saving = false;
  bool _submitted = false;

  @override
  void dispose() {
    _nameController.dispose();
    _quantityController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _submitted = true);
    final String name = _nameController.text.trim();
    final double? quantity = parsePositiveQuantity(_quantityController.text);
    final String? groupId = _groupId;
    if (name.isEmpty || quantity == null || groupId == null) return;

    setState(() => _saving = true);
    try {
      await ref
          .read(pantryRepositoryProvider)
          .addItem(
            userId: ref.read(currentUserIdProvider),
            name: name,
            quantity: quantity,
            unit: _unit,
            groupId: groupId,
          );
      if (!mounted) return;
      ref.read(hapticsProvider).mediumImpact();
      GleanSnackBar.show(context, 'Added to pantry');
      context.goNamed(AppRoutes.pantry.name);
    } catch (e) {
      if (!mounted) return;
      // A unit mismatch gets its own targeted message: the generic "try again" below is misleading, since retrying
      // the same unit fails identically.
      GleanSnackBar.show(
        context,
        e is PantryUnitMismatchException
            ? e.userMessage
            : 'Could not save this item. Try again.',
      );
    } finally {
      // Always clears, so a DB error can't leave the add button permanently disabled.
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final String? quantityError =
        _submitted && parsePositiveQuantity(_quantityController.text) == null
        ? 'Enter a quantity greater than 0'
        : null;
    final String? groupError = _submitted && _groupId == null
        ? 'Choose an ingredient group'
        : null;

    return Scaffold(
      appBar: AppBar(title: const Text('Add item')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.all(tokens.spacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              GleanField(
                label: 'Ingredient name',
                child: TextField(controller: _nameController, autofocus: true),
              ),
              SizedBox(height: tokens.spacing.md),
              GleanField(
                label: 'Quantity',
                child: TextField(
                  controller: _quantityController,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: InputDecoration(errorText: quantityError),
                ),
              ),
              SizedBox(height: tokens.spacing.md),
              Text('Unit', style: Theme.of(context).textTheme.titleMedium),
              SizedBox(height: tokens.spacing.sm),
              Wrap(
                spacing: tokens.spacing.sm,
                children: <Widget>[
                  for (final String unit in _commonUnits)
                    ChoiceChip(
                      label: Text(unit),
                      selected: _unit == unit,
                      onSelected: (bool _) {
                        ref.read(hapticsProvider).selectionClick();
                        setState(() => _unit = unit);
                      },
                    ),
                ],
              ),
              SizedBox(height: tokens.spacing.md),
              GleanField(
                label: 'Ingredient group',
                child: DropdownButtonFormField<String>(
                  isExpanded: true,
                  initialValue: _groupId,
                  decoration: InputDecoration(errorText: groupError),
                  items: <DropdownMenuItem<String>>[
                    for (final IngredientGroupSeed seed in selectableGroupSeeds)
                      DropdownMenuItem<String>(
                        value: seed.id,
                        child: Text(seed.name),
                      ),
                  ],
                  onChanged: (String? value) =>
                      setState(() => _groupId = value),
                ),
              ),
              SizedBox(height: tokens.spacing.xl),
              FilledButton(
                onPressed: _saving ? null : _save,
                child: _saving
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Add to pantry'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
