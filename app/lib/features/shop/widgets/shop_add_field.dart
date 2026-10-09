/// The pinned manual-add field. `ShopScreen` places it above the scrollable list, never inside it, so it can't
/// scroll away.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/text_input.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/design_system/design_system.dart';

class ShopAddField extends ConsumerStatefulWidget {
  const ShopAddField({super.key});

  @override
  ConsumerState<ShopAddField> createState() => _ShopAddFieldState();
}

class _ShopAddFieldState extends ConsumerState<ShopAddField> {
  late final TextEditingController _controller;
  bool _adding = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
    _controller.addListener(_onChanged);
  }

  @override
  void dispose() {
    _controller.removeListener(_onChanged);
    _controller.dispose();
    super.dispose();
  }

  void _onChanged() => setState(() {});

  bool get _canAdd => toRequiredSubmittedText(_controller.text) != null;

  /// Every exit path here (success, thrown error, early return) resets `_adding`, and a failure surfaces inline
  /// instead of vanishing, so a DB error can't leave the add button permanently disabled.
  Future<void> _submit() async {
    final String? name = toRequiredSubmittedText(_controller.text);
    if (name == null || _adding) return;

    setState(() {
      _adding = true;
      _error = null;
    });
    try {
      await ref
          .read(shoppingRepositoryProvider)
          .addManualItem(userId: ref.read(currentUserIdProvider), name: name);
      if (!mounted) return;
      ref.read(hapticsProvider).mediumImpact(); // data commit.
      _controller.clear();
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Could not add "$name". Try again.');
    } finally {
      if (mounted) setState(() => _adding = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: TextField(
                controller: _controller,
                textInputAction: TextInputAction.done,
                onSubmitted: (String _) => _submit(),
                decoration: const InputDecoration(hintText: 'Add item…'),
              ),
            ),
            SizedBox(width: tokens.spacing.sm),
            IconButton(
              onPressed: (_adding || !_canAdd) ? null : _submit,
              tooltip: 'Add item',
              style: IconButton.styleFrom(
                backgroundColor: colorScheme.primary,
                foregroundColor: colorScheme.onPrimary,
                disabledBackgroundColor: colorScheme.surfaceContainerHighest,
              ),
              icon: _adding
                  ? SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: colorScheme.onPrimary,
                      ),
                    )
                  : const Icon(Icons.add_rounded),
            ),
          ],
        ),
        if (_error != null) ...<Widget>[
          SizedBox(height: tokens.spacing.xs),
          Text(
            _error!,
            style: Theme.of(
              context,
            ).textTheme.bodySmall?.copyWith(color: tokens.warning),
          ),
        ],
      ],
    );
  }
}
