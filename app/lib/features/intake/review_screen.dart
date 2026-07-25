/// The shared intake review screen (AC-PAN-05) — one screen, one look, one
/// set of verbs and one numeric fallback rule for both pantry and shop
/// intake, parameterised by [ReviewArgs.destination]. Fixes three RN defects
/// at once (§11): decimal quantities are freely typeable (AC-PAN-08), an
/// invalid quantity blocks Confirm rather than silently falling back to `1`
/// or `0` (AC-PAN-09), and the commit is atomic (AC-PAN-10).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/pantry_repository.dart'
    show PantryItemInput, PantryUnitMismatchException;
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

import 'review_row.dart';
import 'widgets/clarifying_questions_card.dart';
import 'widgets/review_item_row.dart';

class ReviewScreen extends ConsumerStatefulWidget {
  const ReviewScreen({required this.args, super.key});

  final ReviewArgs args;

  @override
  ConsumerState<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends ConsumerState<ReviewScreen> {
  late List<ReviewRow> _rows;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _rows = <ReviewRow>[
      for (final ReviewItemDraft item in widget.args.items) ReviewRow(item),
    ];
    for (final ReviewRow row in _rows) {
      row.nameController.addListener(_onRowChanged);
      row.quantityController.addListener(_onRowChanged);
    }
  }

  void _onRowChanged() => setState(() {});

  @override
  void dispose() {
    for (final ReviewRow row in _rows) {
      row.nameController.removeListener(_onRowChanged);
      row.quantityController.removeListener(_onRowChanged);
      row.dispose();
    }
    super.dispose();
  }

  void _removeRow(int index) {
    setState(() {
      final ReviewRow row = _rows.removeAt(index);
      row.nameController.removeListener(_onRowChanged);
      row.quantityController.removeListener(_onRowChanged);
      row.dispose();
    });
  }

  bool get _isPantry => widget.args.destination == ReviewDestination.pantry;

  /// A pantry row additionally needs a category — expiry inference has no
  /// basis without one (FINDINGS.md F-07/F-08) and
  /// `PantryRepository.addItem` requires it. Shop rows never need this.
  bool _rowIsValid(ReviewRow row) {
    if (row.parsedQuantity == null) return false;
    if (_isPantry && row.category == null) return false;
    return true;
  }

  List<ReviewRow> get _activeRows =>
      _rows.where((ReviewRow r) => r.isActive).toList();

  bool get _canConfirm =>
      !_saving && _activeRows.isNotEmpty && _activeRows.every(_rowIsValid);

  Future<void> _confirm() async {
    if (!_canConfirm) return;
    ref.read(hapticsProvider).mediumImpact();
    setState(() => _saving = true);

    final String userId = ref.read(currentUserIdProvider);
    final List<ReviewRow> accepted = _activeRows;
    try {
      if (_isPantry) {
        await _confirmPantry(userId, accepted);
      } else {
        await _confirmShop(userId, accepted);
      }
    } catch (e) {
      if (!mounted) return;
      // R-23: a unit mismatch gets its own targeted message — the generic
      // "try again" below is actively misleading for it, since retrying the
      // same incoming unit fails identically every time.
      GleanSnackBar.show(
        context,
        e is PantryUnitMismatchException
            ? e.userMessage
            : 'Could not save. Please try again.',
      );
      setState(() => _saving = false);
      return;
    }

    if (!mounted) return;
    final int count = accepted.length;
    GleanSnackBar.show(context, 'Added $count item${count == 1 ? '' : 's'}');
    context.goNamed(
      _isPantry && !widget.args.returnToShop
          ? AppRoutes.pantry.name
          : AppRoutes.shop.name,
    );
  }

  /// AC-PAN-10: one transaction via `PantryRepository.addItems` — a failure
  /// partway through persists nothing, so a retry can't double quantities.
  /// AC-PAN-11: the shopping list is only ever touched when this pantry
  /// review was reached via Shop's "scan receipt" (`returnToShop`), and even
  /// then only the ingredients this batch actually resolved are checked off
  /// (AC-SHOP-01) — never an unconditional `completeCheckout`.
  /// R-23: passes the row's unit text **raw** (trimmed, but not defaulted)
  /// to the repository, rather than pre-substituting `'units'` for a blank
  /// field here. `PantryRepository.addItem`/`ShoppingRepository.addAiItems`
  /// each apply that same `'units'` default for the row itself, but — unlike
  /// this screen previously did — never let it seed the ingredient's
  /// canonical unit; only an explicitly typed one does that. Applying the
  /// fallback here would erase the "was this typed or defaulted" distinction
  /// before it ever reached the one place that needs it.
  Future<void> _confirmPantry(String userId, List<ReviewRow> accepted) async {
    final List<PantryItemInput> items = <PantryItemInput>[
      for (final ReviewRow row in accepted)
        PantryItemInput(
          name: row.nameController.text.trim(),
          quantity: row.parsedQuantity!,
          unit: row.unitController.text.trim(),
          category: row.category!,
          unitPrice: row.unitPrice,
        ),
    ];
    final List<int> ingredientIds = await ref
        .read(pantryRepositoryProvider)
        .addItems(userId: userId, items: items);

    if (widget.args.returnToShop) {
      await ref
          .read(shoppingRepositoryProvider)
          .resolveCheckout(
            userId: userId,
            resolvedIngredientIds: ingredientIds,
          );
    }
  }

  Future<void> _confirmShop(String userId, List<ReviewRow> accepted) async {
    final List<AiShoppingItem> items = <AiShoppingItem>[
      for (final ReviewRow row in accepted)
        AiShoppingItem(
          name: row.nameController.text.trim(),
          quantity: row.parsedQuantity!,
          unit: row.unitController.text.trim(),
          category: row.category,
        ),
    ];
    await ref
        .read(shoppingRepositoryProvider)
        .addAiItems(userId: userId, items: items);
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final int acceptedCount = _activeRows.length;

    return Scaffold(
      appBar: AppBar(title: const Text('Review items')),
      body: SafeArea(
        child: Column(
          children: <Widget>[
            if (widget.args.clarifyingQuestions.isNotEmpty)
              ClarifyingQuestionsCard(
                questions: widget.args.clarifyingQuestions,
              ),
            Expanded(
              child: _rows.isEmpty
                  ? const Center(child: Text('Nothing left to review.'))
                  : ListView.separated(
                      padding: EdgeInsets.all(tokens.spacing.lg),
                      itemCount: _rows.length,
                      separatorBuilder: (BuildContext context, int index) =>
                          SizedBox(height: tokens.spacing.sm),
                      itemBuilder: (BuildContext context, int index) {
                        final ReviewRow row = _rows[index];
                        return ReviewItemRow(
                          key: ValueKey<String>(row.reviewId),
                          nameController: row.nameController,
                          quantityController: row.quantityController,
                          unitController: row.unitController,
                          confidence: row.confidence,
                          quantityErrorText:
                              row.isActive && row.parsedQuantity == null
                              ? 'Enter a quantity greater than 0'
                              : null,
                          requiresCategory: _isPantry && row.category == null,
                          selectedCategory: row.category,
                          onCategoryChanged: (String? value) =>
                              setState(() => row.category = value),
                          onRemove: () => _removeRow(index),
                        );
                      },
                    ),
            ),
            Padding(
              padding: EdgeInsets.all(tokens.spacing.lg),
              child: FilledButton(
                onPressed: _canConfirm ? _confirm : null,
                child: _saving
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(
                        'Add $acceptedCount item${acceptedCount == 1 ? '' : 's'}',
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
