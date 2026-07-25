/// "Describe your shopping list" — the text-only sibling of Shop's own
/// receipt-scan capture (FLUTTER_MIGRATION.md §6), reached from Shop's `+`
/// entry point. Always lands on the shared review screen with
/// `destination: shop`, carrying through any clarifying questions the parse
/// couldn't resolve on its own.
///
/// This screen was the one gap in the intake surface (FINDINGS.md F-16):
/// Shop's brief said "route into the shared intake screens, don't build a
/// second review screen" — correct, and everything downstream (the review
/// screen, `ReviewArgs.clarifyingQuestions`,
/// `parseShoppingDescriptionControllerProvider`) was already built and
/// waiting — but no brief named *this* screen, so it stayed the router
/// wave's placeholder. The form UI itself is shared with
/// `PantryDescribeScreen` via `widgets/describe_form.dart` — see that
/// file's doc comment for why.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/shopping.dart';
import 'package:glean/api/providers/shopping_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

import 'widgets/describe_form.dart';

class ShopDescribeScreen extends ConsumerWidget {
  const ShopDescribeScreen({super.key});

  void _onSuccess(BuildContext context, ShoppingParseResponse response) {
    final List<ReviewItemDraft> items = <ReviewItemDraft>[
      for (int i = 0; i < response.items.length; i++)
        ReviewItemDraft(
          reviewId: 'shop-describe-$i',
          name: response.items[i].name,
          quantity: response.items[i].quantity,
          unit: response.items[i].unit,
          confidence: response.items[i].confidence,
          category: response.items[i].category,
          // `unitPrice` stays unset: it's pantry-only (see
          // `ReviewItemDraft.unitPrice`'s doc comment) — shop drafts never
          // carry a per-unit price even though `ShoppingProposalItem`
          // inherits the field from `ParsedIngredient`.
        ),
    ];
    context.goNamed(
      AppRoutes.intakeReview.name,
      extra: ReviewArgs(
        destination: ReviewDestination.shop,
        items: items,
        clarifyingQuestions: response.clarifyingQuestions,
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen<AsyncValue<ShoppingParseResponse?>>(
      parseShoppingDescriptionControllerProvider,
      (
        AsyncValue<ShoppingParseResponse?>? previous,
        AsyncValue<ShoppingParseResponse?> next,
      ) {
        final ShoppingParseResponse? response = next.value;
        if (response != null) _onSuccess(context, response);
      },
    );
    final AsyncValue<ShoppingParseResponse?> async = ref.watch(
      parseShoppingDescriptionControllerProvider,
    );
    final AppTokens tokens = context.tokens;

    return Scaffold(
      appBar: AppBar(title: const Text('Describe list')),
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.all(tokens.spacing.lg),
          child: DescribeForm(
            hintText:
                'Type what you need now. Dictation can feed the same text later.',
            placeholder: 'Stuff for tacos, milk, bananas, and lunchbox snacks',
            buttonLabel: 'Review items',
            isLoading: async.isLoading,
            errorMessage: async.hasError
                ? 'Could not turn that into a list. Try being more specific, '
                      'e.g. "milk, bananas, taco shells".'
                : null,
            onSubmit: (String text) => ref
                .read(parseShoppingDescriptionControllerProvider.notifier)
                .parse(text),
          ),
        ),
      ),
    );
  }
}
