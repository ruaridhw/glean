// Pantry reads for the current user. Screens watch [pantryItemsProvider] rather than calling the
// repository's reads; the stream re-emits on every write, so there is no on-focus reload.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/pantry_item_view.dart';
import 'database_providers.dart';
import 'repository_providers.dart';

final StreamProvider<List<PantryItemView>> pantryItemsProvider =
    StreamProvider<List<PantryItemView>>((ref) {
      final userId = ref.watch(currentUserIdProvider);
      return ref.watch(pantryRepositoryProvider).watchAll(userId);
    });
