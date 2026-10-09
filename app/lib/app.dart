/// Root widget. `lib/main.dart` and `lib/main_e2e.dart` (orchestrator-owned,
/// per the module contract) each wrap this in a `ProviderScope` and call
/// `runApp`.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'design_system/design_system.dart';
import 'router/router.dart';

/// `theme` exists only so a test can substitute one. It defaults to
/// [gleanLightTheme] and there is deliberately **no** bare-Material fallback:
/// an earlier revision defaulted to `ColorScheme.fromSeed`, which registers no
/// `AppTokens` extension, so every widget reading `context.tokens` asserted at
/// build time. A theme without the brand tokens is never a useful degradation
/// here — it is a crash one frame later — so the only default is the real one.
class GleanApp extends ConsumerWidget {
  const GleanApp({this.theme, super.key});

  final ThemeData? theme;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final GoRouter router = ref.watch(goRouterProvider);
    return MaterialApp.router(
      title: 'Glean',
      debugShowCheckedModeBanner: false,
      theme: theme ?? gleanLightTheme,
      routerConfig: router,
    );
  }
}
