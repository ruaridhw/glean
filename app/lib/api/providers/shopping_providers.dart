import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/shopping.dart';
import 'api_providers.dart';

/// Command controller for `POST /shopping/parse-description`. Returns an
/// ephemeral list of shopping-item proposals (AC-DATA-06) for the shop
/// review screen; nothing is written to drift until the user confirms.
class ParseShoppingDescriptionController
    extends AsyncNotifier<ShoppingParseResponse?> {
  @override
  FutureOr<ShoppingParseResponse?> build() => null;

  Future<void> parse(String text) async {
    state = const AsyncLoading();
    final client = ref.read(apiClientProvider);
    state = await AsyncValue.guard(() => client.parseShoppingDescription(text));
  }
}

final AsyncNotifierProvider<
  ParseShoppingDescriptionController,
  ShoppingParseResponse?
>
parseShoppingDescriptionControllerProvider = AsyncNotifierProvider.autoDispose(
  ParseShoppingDescriptionController.new,
);
