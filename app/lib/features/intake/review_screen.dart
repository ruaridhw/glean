/// The shared intake review screen: one screen and one numeric fallback rule for both pantry and shop intake,
/// parameterised by [ReviewArgs.destination]. Decimal quantities are freely typeable, an invalid quantity
/// blocks Confirm rather than falling back to `1` or `0`, and the commit is atomic.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/shopping.dart';
import 'package:glean/api/providers/api_providers.dart';
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
import 'widgets/review_items_list.dart';

class ReviewScreen extends ConsumerStatefulWidget {
  const ReviewScreen({required this.args, super.key});

  final ReviewArgs args;

  @override
  ConsumerState<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends ConsumerState<ReviewScreen> {
  late List<ReviewRow> _rows;
  bool _saving = false;
  bool _reparsing = false;
  late List<String> _questions;
  final Map<String, String> _answers = {};
  final Set<String> _removedNames = {};

  @override
  void initState() {
    super.initState();
    _questions = widget.args.clarifyingQuestions;
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
      _removedNames.add(row.originalName);
      row.nameController.removeListener(_onRowChanged);
      row.quantityController.removeListener(_onRowChanged);
      row.dispose();
    });
  }

  bool get _isPantry => widget.args.destination == ReviewDestination.pantry;

  /// A pantry row's category is optional: without one the Pantry item is stored uncategorised (no expiry is
  /// inferred), which must never block confirming a row that came from the shopping list.
  bool _rowIsValid(ReviewRow row) => row.parsedQuantity != null;

  List<ReviewRow> get _activeRows =>
      _rows.where((ReviewRow r) => r.isActive).toList();

  bool get _canConfirm =>
      !_saving &&
      !_reparsing &&
      _activeRows.isNotEmpty &&
      _activeRows.every(_rowIsValid);

  Future<void> _answerQuestions(Map<String, String> answers) async {
    if (_reparsing || _saving) return;
    _answers.addAll(answers.map((key, value) => MapEntry(key, value.trim())));
    final text =
        '${widget.args.originalDescription}\n\nAnswers: ${_answers.entries.where((e) => e.value.isNotEmpty).map((e) => '${e.key}: ${e.value}').join('; ')}';
    setState(() => _reparsing = true);
    final ShoppingParseResponse result;
    try {
      result = await ref.read(apiClientProvider).parseShoppingDescription(text);
    } catch (error) {
      if (!mounted) return;
      setState(() => _reparsing = false);
      GleanSnackBar.show(
        context,
        error is ApiRateLimitException
            ? error.userMessage
            : 'Could not update suggestions. Try again.',
      );
      return;
    }
    if (!mounted) return;
    final previous = {for (final row in _rows) row.originalName: row};
    final next = <ReviewRow>[];
    for (final item in result.items) {
      final key = item.name.trim().toLowerCase();
      if (_removedNames.contains(key)) continue;
      final existing = previous.remove(key);
      final proposal = ReviewItemDraft(
        reviewId: existing?.reviewId ?? 'refined-$key',
        name: item.name,
        quantity: item.quantity,
        unit: item.unit,
        confidence: item.confidence,
        category: item.category,
      );
      if (existing != null) {
        existing.refine(proposal);
        next.add(existing);
      } else {
        final row = ReviewRow(proposal);
        row.nameController.addListener(_onRowChanged);
        row.quantityController.addListener(_onRowChanged);
        next.add(row);
      }
    }
    for (final row in previous.values) {
      row.nameController.removeListener(_onRowChanged);
      row.quantityController.removeListener(_onRowChanged);
      row.dispose();
    }
    setState(() {
      _rows = next;
      _questions = result.clarifyingQuestions;
      _reparsing = false;
    });
  }

  Future<void> _confirm() async {
    if (!_canConfirm) return;
    ref.read(hapticsProvider).mediumImpact();
    setState(() => _saving = true);

    final String userId = ref.read(currentUserIdProvider);
    final List<ReviewRow> accepted = _activeRows;
    if (widget.args.fromCheckedItems) {
      await _confirmCheckout(userId, accepted);
      return;
    }
    try {
      if (_isPantry) {
        await ref
            .read(gleanDatabaseProvider)
            .transaction(() => _confirmPantry(userId, accepted));
      } else {
        await _confirmShop(userId, accepted);
      }
    } catch (e) {
      if (!mounted) return;
      // A unit mismatch gets its own targeted message: the generic "try again" below is misleading, since retrying
      // the same unit fails identically.
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

  /// "Done shopping": adds the rows to the pantry and clears the checked Shopping items they came from in one
  /// transaction, then offers one Undo that reverses both.
  Future<void> _confirmCheckout(String userId, List<ReviewRow> accepted) async {
    final pantry = ref.read(pantryRepositoryProvider);
    final shopping = ref.read(shoppingRepositoryProvider);
    final db = ref.read(gleanDatabaseProvider);
    final int count = accepted.length;
    final bool done = await GleanSnackBar.runUndoable(
      context,
      perform: () => db.transaction(() async {
        final receipt = await pantry.addItemsWithReceipt(
          userId: userId,
          items: _pantryInputs(accepted),
        );
        final cleared = await shopping.deleteRowsWithSnapshot(
          userId: userId,
          ids: <int>[for (final row in accepted) ...row.sourceRowIds],
        );
        return (receipt: receipt, cleared: cleared);
      }),
      undo: (checkout) => db.transaction(() async {
        await pantry.undoAdditions(userId: userId, receipt: checkout.receipt);
        await shopping.restoreRows(rows: checkout.cleared, userId: userId);
      }),
      message: 'Added $count item${count == 1 ? '' : 's'} to your pantry',
      failureMessage: 'Could not save. Please try again.',
      undoFailureMessage: 'Could not undo. Please try again.',
      describeError: (Object e) => e is PantryUnitMismatchException
          ? e.userMessage
          : 'Could not save. Please try again.',
      onSuccess: ref.read(hapticsProvider).mediumImpact,
    );
    if (!mounted) return;
    if (!done) {
      setState(() => _saving = false);
      return;
    }
    context.goNamed(AppRoutes.shop.name);
  }

  List<PantryItemInput> _pantryInputs(List<ReviewRow> accepted) =>
      <PantryItemInput>[
        for (final ReviewRow row in accepted)
          PantryItemInput(
            name: row.nameController.text.trim(),
            quantity: row.parsedQuantity!,
            unit: row.unitController.text.trim(),
            category: row.category,
            unitPrice: row.unitPrice,
          ),
      ];

  /// One transaction via `PantryRepository.addItems`: a failure partway persists nothing, so a retry can't double
  /// quantities. The shopping list is only touched when this pantry review was reached via Shop's "scan receipt"
  /// (`returnToShop`), and then only the ingredients this batch resolved are checked off. Pass raw units:
  /// repositories default blanks without seeding the ingredient's canonical unit from an implicit value.
  Future<void> _confirmPantry(String userId, List<ReviewRow> accepted) async {
    final List<int> ingredientIds = await ref
        .read(pantryRepositoryProvider)
        .addItems(userId: userId, items: _pantryInputs(accepted));

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
      appBar: AppBar(
        title: const Text('Review items'),
        leading: IconButton(
          tooltip: 'Cancel',
          icon: const Icon(Icons.close_rounded),
          onPressed: _saving
              ? null
              : () {
                  ref.read(hapticsProvider).lightImpact();
                  context.goNamed(
                    !_isPantry || widget.args.returnToShop
                        ? AppRoutes.shop.name
                        : AppRoutes.pantry.name,
                  );
                },
        ),
      ),
      body: SafeArea(
        child: Column(
          children: <Widget>[
            Expanded(
              child: ReviewItemsList(
                rows: _rows,
                questions: _questions,
                isPantry: _isPantry,
                pending: _reparsing || _saving,
                onChanged: _onRowChanged,
                onRemove: _removeRow,
                onAnswer: !_isPantry && widget.args.originalDescription != null
                    ? _answerQuestions
                    : null,
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
