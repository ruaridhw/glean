/// "Describe what you bought" — the text-only sibling of receipt scan
/// (FLUTTER_MIGRATION.md §6 Pantry), reachable from the pantry `+` sheet
/// whether the pantry is empty or full (AC-PAN-03). Always lands on the
/// shared review screen with `destination: pantry` and `returnToShop: false`
/// — this entry point only ever exists inside the Pantry tab.
///
/// The form UI itself is shared with `ShopDescribeScreen` via
/// `widgets/describe_form.dart` — see that file's doc comment for why.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/receipts.dart';
import 'package:glean/api/providers/receipts_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

import 'widgets/describe_form.dart';

class PantryDescribeScreen extends ConsumerWidget {
  const PantryDescribeScreen({super.key});

  void _onSuccess(BuildContext context, ScanResponse response) {
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
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen<AsyncValue<ScanResponse?>>(describeReceiptControllerProvider, (
      AsyncValue<ScanResponse?>? previous,
      AsyncValue<ScanResponse?> next,
    ) {
      final ScanResponse? response = next.value;
      if (response != null) _onSuccess(context, response);
    });
    final AsyncValue<ScanResponse?> async = ref.watch(
      describeReceiptControllerProvider,
    );
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
            isLoading: async.isLoading,
            errorMessage: async.hasError
                ? 'Could not understand that. Try being more specific, e.g. '
                      '"500g chicken breast, 2 tins tomatoes".'
                : null,
            onSubmit: (String text) => ref
                .read(describeReceiptControllerProvider.notifier)
                .describe(text),
          ),
        ),
      ),
    );
  }
}
