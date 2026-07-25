import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_providers.dart';

/// `GET /health` — a plain connectivity/liveness check, not tied to any
/// screen's lifecycle, so it isn't `autoDispose`.
final FutureProvider<bool> healthProvider = FutureProvider<bool>((ref) {
  return ref.watch(apiClientProvider).health();
});
