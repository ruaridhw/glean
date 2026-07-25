import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/shopping.dart';
import 'api_providers.dart';

/// Command controller for `POST /shopping/parse-description`. Returns an
/// ephemeral list of shopping-item proposals (AC-DATA-06) for the shop
/// review screen; nothing is written to drift until the user confirms.
///
/// **Not currently wired to any screen** — see the module report for why
/// this is a missing feature, not dead code, and who needs to wire it.
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
