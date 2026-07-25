/// "Describe what you bought" — the text-only sibling of receipt scan
/// (FLUTTER_MIGRATION.md §6 Pantry), reachable from the pantry `+` sheet
/// whether the pantry is empty or full (AC-PAN-03). Always lands on the
/// shared review screen with `destination: pantry` and `returnToShop: false`
/// — this entry point only ever exists inside the Pantry tab.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/receipts.dart';
import 'package:glean/api/providers/receipts_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

class PantryDescribeScreen extends ConsumerStatefulWidget {
  const PantryDescribeScreen({super.key});

  @override
  ConsumerState<PantryDescribeScreen> createState() =>
      _PantryDescribeScreenState();
}

class _PantryDescribeScreenState extends ConsumerState<PantryDescribeScreen> {
  final TextEditingController _controller = TextEditingController();
  bool _navigated = false;

  @override
  void initState() {
    super.initState();
    _controller.addListener(_onTextChanged);
  }

  void _onTextChanged() => setState(() {});

  @override
  void dispose() {
    _controller.removeListener(_onTextChanged);
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final String text = _controller.text.trim();
    if (text.isEmpty) return;
    ref.read(describeReceiptControllerProvider.notifier).describe(text);
  }

  void _onSuccess(ScanResponse response) {
    if (_navigated || !mounted) return;
    _navigated = true;
    final List<ReviewItemDraft> items = <ReviewItemDraft>[
      for (int i = 0; i < response.items.length; i++)
        ReviewItemDraft(
          reviewId: 'describe-$i',
          name: response.items[i].name,
          quantity: response.items[i].quantity,
          unit: response.items[i].unit,
          confidence: response.items[i].confidence,
          unitPrice: response.items[i].unitPrice,
          category: response.items[i].category,
        ),
    ];
    context.goNamed(
      AppRoutes.intakeReview.name,
      extra: ReviewArgs(destination: ReviewDestination.pantry, items: items),
    );
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<AsyncValue<ScanResponse?>>(describeReceiptControllerProvider, (
      AsyncValue<ScanResponse?>? previous,
      AsyncValue<ScanResponse?> next,
    ) {
      final ScanResponse? response = next.value;
      if (response != null) _onSuccess(response);
    });
    final AsyncValue<ScanResponse?> async = ref.watch(
      describeReceiptControllerProvider,
    );
    final AppTokens tokens = context.tokens;
    final bool canSubmit =
        _controller.text.trim().isNotEmpty && !async.isLoading;

    return Scaffold(
      appBar: AppBar(title: const Text('Describe your shop')),
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.all(tokens.spacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Text(
                'e.g. "I bought a kilo of mince and two tins of tomatoes"',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              SizedBox(height: tokens.spacing.md),
              Expanded(
                child: TextField(
                  controller: _controller,
                  autofocus: true,
                  expands: true,
                  maxLines: null,
                  textAlignVertical: TextAlignVertical.top,
                  decoration: const InputDecoration(
                    hintText: 'What did you buy?',
                  ),
                ),
              ),
              if (async.hasError) ...<Widget>[
                SizedBox(height: tokens.spacing.md),
                Text(
                  'Could not understand that. Try being more specific, e.g. '
                  '"500g chicken breast, 2 tins tomatoes".',
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              SizedBox(height: tokens.spacing.lg),
              FilledButton(
                onPressed: canSubmit ? _submit : null,
                child: async.isLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Parse'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
