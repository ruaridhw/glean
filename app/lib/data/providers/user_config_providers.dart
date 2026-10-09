// User-config reads for the current user.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/user_config_view.dart';
import 'database_providers.dart';
import 'repository_providers.dart';

final StreamProvider<UserConfigView> userConfigProvider =
    StreamProvider<UserConfigView>((ref) {
      final userId = ref.watch(currentUserIdProvider);
      return ref.watch(userConfigRepositoryProvider).watch(userId);
    });
