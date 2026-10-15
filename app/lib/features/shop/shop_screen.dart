/// The Shop tab. Its two intake entry points ("Describe list" and "Scan receipt") push into the shared intake
/// flow rather than building a second describe/review screen. `ScanArgs.returnToShop`/`ReviewArgs.returnToShop`
/// tells that flow to call `ShoppingRepository.resolveCheckout` on confirm instead of a plain pantry commit; see
/// `intake_params.dart`.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/auth/auth_controller.dart'
    show aiFeaturesAvailableProvider;
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/data/providers/shopping_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

import 'actions.dart';
import 'presentation.dart';
import 'widgets/shop_add_field.dart';
import 'widgets/shop_checkout_bar.dart';
import 'widgets/shop_list_section.dart';

class ShopScreen extends ConsumerStatefulWidget {
  const ShopScreen({super.key});

  @override
  ConsumerState<ShopScreen> createState() => _ShopScreenState();
}

class _ShopScreenState extends ConsumerState<ShopScreen> {
  // Guards "Done shopping" against a double-tap firing the checkout twice.
  bool _completingCheckout = false;

  Future<void> _doneShopping() async {
    if (_completingCheckout) return;
    setState(() => _completingCheckout = true);
    try {
      await completeCheckoutWithoutReceipt(context, ref);
    } finally {
      if (mounted) setState(() => _completingCheckout = false);
    }
  }

  void _scanReceipt() {
    ref.read(hapticsProvider).lightImpact();
    context.pushNamed(
      AppRoutes.intakeScan.name,
      extra: const ScanArgs(returnToShop: true),
    );
  }

  void _describeList() {
    ref.read(hapticsProvider).lightImpact();
    context.pushNamed(AppRoutes.intakeDescribeShop.name);
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final AsyncValue<List<ShoppingListItemView>> itemsAsync = ref.watch(
      shoppingListProvider,
    );
    final List<ShoppingListItemView> items =
        itemsAsync.value ?? const <ShoppingListItemView>[];
    final List<ShoppingListItemView> checkedItems = <ShoppingListItemView>[
      for (final ShoppingListItemView item in items)
        if (item.isChecked) item,
    ];
    final int uncheckedCount = items.length - checkedItems.length;
    // Both "Describe list" and "Scan receipt" call the AI backend, so both are disabled while a session is
    // expired; the [SignedOutBanner] above every tab explains why.
    final bool aiAvailable = ref.watch(aiFeaturesAvailableProvider);

    return Scaffold(
      // So the keyboard never covers the pinned add field.
      resizeToAvoidBottomInset: true,
      appBar: AppBar(
        title: const Text('Shopping'),
        actions: <Widget>[
          IconButton(
            icon: const Icon(Icons.auto_awesome_rounded),
            tooltip: 'Describe list',
            onPressed: aiAvailable ? _describeList : null,
          ),
        ],
      ),
      body: SafeArea(
        top: false,
        child: Column(
          children: <Widget>[
            Expanded(
              child: Padding(
                padding: EdgeInsets.fromLTRB(
                  tokens.spacing.lg,
                  tokens.spacing.md,
                  tokens.spacing.lg,
                  0,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    if (items.isNotEmpty) ...<Widget>[
                      Wrap(
                        spacing: tokens.spacing.sm,
                        children: <Widget>[
                          GleanBadge(
                            label: toBuyCountLabel(uncheckedCount),
                            tone: GleanBadgeTone.primary,
                          ),
                          GleanBadge(
                            label: cartCountLabel(checkedItems.length),
                          ),
                        ],
                      ),
                      SizedBox(height: tokens.spacing.md),
                    ],
                    const ShopAddField(),
                    SizedBox(height: tokens.spacing.md),
                    Expanded(child: ShopListSection(itemsAsync: itemsAsync)),
                  ],
                ),
              ),
            ),
            ShopCheckoutBar(
              checkedCount: checkedItems.length,
              busy: _completingCheckout,
              aiFeaturesAvailable: aiAvailable,
              onScanReceipt: _scanReceipt,
              onDoneShopping: _doneShopping,
            ),
          ],
        ),
      ),
    );
  }
}
