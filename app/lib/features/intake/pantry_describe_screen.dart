/// "Describe what you bought": the text-only sibling of receipt scan, reachable from the pantry `+` sheet.
/// Always lands on the shared review screen with `destination: pantry` and `returnToShop: false`. The form UI is
/// shared with `ShopDescribeScreen` via `widgets/describe_form.dart`.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/receipts.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

import 'widgets/describe_form.dart';

class PantryDescribeScreen extends ConsumerStatefulWidget {
  const PantryDescribeScreen({super.key});

  @override
  ConsumerState<PantryDescribeScreen> createState() =>
      _PantryDescribeScreenState();
}

class _PantryDescribeScreenState extends ConsumerState<PantryDescribeScreen> {
  bool _pending = false;
  bool _failed = false;

  Future<void> _submit(String text) async {
    if (_pending) return;
    setState(() {
      _pending = true;
      _failed = false;
    });
    final ScanResponse response;
    try {
      response = await ref.read(apiClientProvider).describeReceipt(text);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _pending = false;
        _failed = true;
      });
      return;
    }
    if (!mounted) return;
    setState(() => _pending = false);
    _onSuccess(response);
  }

  void _onSuccess(ScanResponse response) {
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
    final AppTokens tokens = context.tokens;

    return Scaffold(
      appBar: AppBar(title: const Text('Describe your shop')),
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.all(tokens.spacing.lg),
          child: DescribeForm(
            hintText:
                'e.g. "I bought a kilo of mince and two tins of tomatoes"',
            placeholder: 'What did you buy?',
            buttonLabel: 'Parse',
            isLoading: _pending,
            errorMessage: _failed
                ? 'Could not understand that. Try being more specific, e.g. '
                      '"500g chicken breast, 2 tins tomatoes".'
                : null,
            onSubmit: _submit,
          ),
        ),
      ),
    );
  }
}
