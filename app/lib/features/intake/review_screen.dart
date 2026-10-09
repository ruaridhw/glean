/// The shared intake review screen (AC-PAN-05) — one screen, one look, one
/// set of verbs and one numeric fallback rule for both pantry and shop
/// intake, parameterised by [ReviewArgs.destination]. Fixes three RN defects
/// at once (§11): decimal quantities are freely typeable (AC-PAN-08), an
/// invalid quantity blocks Confirm rather than silently falling back to `1`
/// or `0` (AC-PAN-09), and the commit is atomic (AC-PAN-10).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/providers/shopping_providers.dart';
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
    final command = ref.read(
      parseShoppingDescriptionControllerProvider.notifier,
    );
    await command.parse(text);
    if (!mounted) return;
    final result = ref.read(parseShoppingDescriptionControllerProvider);
    if (result.hasError || result.value == null) {
      setState(() => _reparsing = false);
      GleanSnackBar.show(context, 'Could not update suggestions. Try again.');
      return;
    }
    final previous = {for (final row in _rows) row.originalName: row};
    final next = <ReviewRow>[];
    for (final item in result.value!.items) {
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
      _questions = result.value!.clarifyingQuestions;
      _reparsing = false;
    });
  }

  Future<void> _confirm() async {
    if (!_canConfirm) return;
    ref.read(hapticsProvider).mediumImpact();
    setState(() => _saving = true);

    final String userId = ref.read(currentUserIdProvider);
    final List<ReviewRow> accepted = _activeRows;
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
  /// Pass raw units: repositories default blanks without seeding the
  /// ingredient's canonical unit from an implicit value (R-23).
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
    ref.watch(parseShoppingDescriptionControllerProvider);
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
