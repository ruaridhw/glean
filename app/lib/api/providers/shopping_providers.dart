import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/shopping.dart';
import 'api_providers.dart';

/// Command controller for `POST /shopping/parse-description`. Returns an
/// ephemeral list of shopping-item proposals (AC-DATA-06) for the shop
/// review screen; nothing is written to drift until the user confirms.
///
/// Wired from `lib/features/intake/shop_describe_screen.dart`, which maps the
/// response into `ReviewArgs` with `ReviewDestination.shop` and passes
/// `clarifyingQuestions` through to the shared review screen.
class ParseShoppingDescriptionController
    extends AsyncNotifier<ShoppingParseResponse?> {
  @override
  FutureOr<ShoppingParseResponse?> build() => null;

  /// See `ScanReceiptController.scan`'s doc comment
  /// (`lib/api/providers/receipts_providers.dart`) for why the
  /// [Ref.keepAlive] hold-and-release is here (FINDINGS.md F-15).
  Future<void> parse(String text) async {
    state = const AsyncLoading();
    final keepAliveLink = ref.keepAlive();
    try {
      final client = ref.read(apiClientProvider);
      state = await AsyncValue.guard(
        () => client.parseShoppingDescription(text),
      );
    } finally {
      keepAliveLink.close();
    }
  }
}

final AsyncNotifierProvider<
  ParseShoppingDescriptionController,
  ShoppingParseResponse?
>
parseShoppingDescriptionControllerProvider = AsyncNotifierProvider.autoDispose(
  ParseShoppingDescriptionController.new,
);
