import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/design_system/design_system.dart';

import '../pantry_presentation.dart';

/// Quantity + unit + expiry, with explicit Save/Cancel and real validation
/// (AC-PAN-07) — replaces RN's inline tap-to-edit-commit-on-blur, which
/// silently discarded invalid input, couldn't change units, and had no
/// expiry path at all.
class QuantityEditSheet extends ConsumerStatefulWidget {
  const QuantityEditSheet({super.key, required this.item});

  final PantryItemView item;

  static Future<void> show(BuildContext context, PantryItemView item) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (BuildContext context) => QuantityEditSheet(item: item),
    );
  }

  @override
  ConsumerState<QuantityEditSheet> createState() => _QuantityEditSheetState();
}

class _QuantityEditSheetState extends ConsumerState<QuantityEditSheet> {
  late final TextEditingController _quantityController = TextEditingController(
    text: formatQuantitySeed(widget.item.quantity),
  );
  late final TextEditingController _unitController = TextEditingController(
    text: widget.item.unit,
  );
  late DateTime? _expiryDate = widget.item.expiryDate;
  bool _submitted = false;
  bool _saving = false;

  @override
  void dispose() {
    _quantityController.dispose();
    _unitController.dispose();
    super.dispose();
  }

  Future<void> _pickExpiry() async {
    final DateTime now = DateTime.now();
    final DateTime? picked = await showDatePicker(
      context: context,
      initialDate: _expiryDate ?? now,
      firstDate: DateTime(now.year - 1),
      lastDate: DateTime(now.year + 5),
    );
    if (picked != null) setState(() => _expiryDate = picked);
  }

  Future<void> _save() async {
    setState(() => _submitted = true);
    final double? quantity = parsePositiveQuantity(_quantityController.text);
    final String unit = _unitController.text.trim();
    if (quantity == null || unit.isEmpty) return;

    setState(() => _saving = true);
    try {
      await ref
          .read(pantryRepositoryProvider)
          .updateItem(
            id: widget.item.id,
            userId: ref.read(currentUserIdProvider),
            quantity: quantity,
            unit: unit,
            expiryDate: _expiryDate,
          );
      ref.read(hapticsProvider).mediumImpact();
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      if (mounted) {
        GleanSnackBar.show(context, 'Could not save changes. Try again.');
      }
    } finally {
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
    final String? unitError = _submitted && _unitController.text.trim().isEmpty
        ? 'Required'
        : null;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        tokens.spacing.lg,
        tokens.spacing.lg,
        tokens.spacing.lg,
        tokens.spacing.lg + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Text(
            widget.item.canonicalName,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          SizedBox(height: tokens.spacing.lg),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Expanded(
                child: TextField(
                  controller: _quantityController,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: InputDecoration(
                    labelText: 'Quantity',
                    errorText: quantityError,
                  ),
                ),
              ),
              SizedBox(width: tokens.spacing.md),
              Expanded(
                child: TextField(
                  controller: _unitController,
                  decoration: InputDecoration(
                    labelText: 'Unit',
                    errorText: unitError,
                  ),
                ),
              ),
            ],
          ),
          SizedBox(height: tokens.spacing.md),
          OutlinedButton.icon(
            onPressed: _pickExpiry,
            icon: const Icon(Icons.calendar_today_rounded),
            label: Text(
              _expiryDate == null
                  ? 'Set expiry date'
                  : 'Expires ${formatDate(_expiryDate!)}',
            ),
          ),
          SizedBox(height: tokens.spacing.xl),
          Row(
            children: <Widget>[
              Expanded(
                child: OutlinedButton(
                  onPressed: _saving ? null : () => Navigator.of(context).pop(),
                  child: const Text('Cancel'),
                ),
              ),
              SizedBox(width: tokens.spacing.md),
              Expanded(
                child: FilledButton(
                  onPressed: _saving ? null : _save,
                  child: _saving
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Save'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
