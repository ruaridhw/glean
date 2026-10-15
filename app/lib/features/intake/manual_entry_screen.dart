/// Manual pantry entry (FLUTTER_MIGRATION.md §6 Pantry) — dead code in the
/// RN app (nothing routed to it); reachable here from the `+` sheet whether
/// the pantry is empty or full (AC-PAN-03).
///
/// Unlike scan/describe, there is no LLM classification behind a manually
/// typed item, so `PantryRepository.addItem` has nothing to infer a category
/// from — this screen is the one intake surface that must ask for it
/// directly (FINDINGS.md F-07/F-08), which is also what lets expiry
/// inference (AC-PAN-01) fire for a manually-added item at all.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/pantry_repository.dart'
    show PantryUnitMismatchException;
import 'package:glean/data/seed/taxonomy.dart';
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
  String? _category;
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
    final String? category = _category;
    if (name.isEmpty || quantity == null || category == null) return;

    setState(() => _saving = true);
    try {
      await ref
          .read(pantryRepositoryProvider)
          .addItem(
            userId: ref.read(currentUserIdProvider),
            name: name,
            quantity: quantity,
            unit: _unit,
            category: category,
          );
      if (!mounted) return;
      ref.read(hapticsProvider).mediumImpact();
      GleanSnackBar.show(context, 'Added to pantry');
      context.goNamed(AppRoutes.pantry.name);
    } catch (e) {
      if (!mounted) return;
      // R-23: a unit mismatch gets its own targeted message — the generic
      // "try again" below is misleading for it, since retrying the same
      // chosen unit fails identically every time.
      GleanSnackBar.show(
        context,
        e is PantryUnitMismatchException
            ? e.userMessage
            : 'Could not save this item. Try again.',
      );
    } finally {
      // Always clears — an RN bug left the add button permanently disabled
      // on any DB error because `setAdding(true)` had no `try/finally`.
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
    final String? categoryError = _submitted && _category == null
        ? 'Choose a category'
        : null;

    return Scaffold(
      appBar: AppBar(title: const Text('Add item')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.all(tokens.spacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              TextField(
                controller: _nameController,
                autofocus: true,
                decoration: const InputDecoration(labelText: 'Ingredient name'),
              ),
              SizedBox(height: tokens.spacing.md),
              TextField(
                controller: _quantityController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: InputDecoration(
                  labelText: 'Quantity',
                  errorText: quantityError,
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
              DropdownButtonFormField<String>(
                initialValue: _category,
                decoration: InputDecoration(
                  labelText: 'Category',
                  errorText: categoryError,
                ),
                items: <DropdownMenuItem<String>>[
                  for (final CategorySeed seed in ingredientCategorySeeds)
                    DropdownMenuItem<String>(
                      value: seed.category,
                      child: Text(categoryLabel(seed.category)),
                    ),
                ],
                onChanged: (String? value) => setState(() => _category = value),
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
