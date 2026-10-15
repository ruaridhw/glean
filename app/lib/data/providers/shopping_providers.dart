// Shopping-list reads for the current user.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/shopping_list_item_view.dart';
import 'database_providers.dart';
import 'repository_providers.dart';

final StreamProvider<List<ShoppingListItemView>> shoppingListProvider =
    StreamProvider<List<ShoppingListItemView>>((ref) {
      final userId = ref.watch(currentUserIdProvider);
      return ref.watch(shoppingRepositoryProvider).watchAll(userId);
    });
