/// "Describe your shopping list": the text-only sibling of Shop's receipt scan, reached from Shop's `+` entry
/// point. Always lands on the shared review screen with `destination: shop`, carrying through any clarifying
/// questions the parse couldn't resolve. The form UI is shared with `PantryDescribeScreen` via
/// `widgets/describe_form.dart`.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/shopping.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/data/util/unit_normalization.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

import 'widgets/describe_form.dart';

class ShopDescribeScreen extends ConsumerStatefulWidget {
  const ShopDescribeScreen({super.key});

  @override
  ConsumerState<ShopDescribeScreen> createState() => _ShopDescribeScreenState();
}

class _ShopDescribeScreenState extends ConsumerState<ShopDescribeScreen> {
  String _originalDescription = '';
  bool _pending = false;
  Object? _error;

  Future<void> _submit(String text) async {
    if (_pending) return;
    _originalDescription = text;
    setState(() {
      _pending = true;
      _error = null;
    });
    final ShoppingParseResponse response;
    try {
      response = await ref
          .read(apiClientProvider)
          .parseShoppingDescription(text);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _pending = false;
        _error = error;
      });
      return;
    }
    if (!mounted) return;
    setState(() => _pending = false);
    _onSuccess(response);
  }

  void _onSuccess(ShoppingParseResponse response) {
    final List<ReviewItemDraft> items = <ReviewItemDraft>[
      for (int i = 0; i < response.items.length; i++)
        ReviewItemDraft(
          reviewId: 'shop-describe-$i',
          name: response.items[i].name,
          quantity: response.items[i].quantity,
          unit: acceptedShoppingUnit(response.items[i].unit),
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
        originalDescription: _originalDescription,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
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
            isLoading: _pending,
            errorMessage: switch (_error) {
              null => null,
              final ApiRateLimitException e => e.userMessage,
              _ =>
                'Could not turn that into a list. Try being more specific, '
                    'e.g. "milk, bananas, taco shells".',
            },
            onSubmit: _submit,
          ),
        ),
      ),
    );
  }
}
