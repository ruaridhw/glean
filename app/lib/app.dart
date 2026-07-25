/// Root widget. `lib/main.dart` and `lib/main_e2e.dart` (orchestrator-owned,
/// per the module contract) each wrap this in a `ProviderScope` and call
/// `runApp`.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'router/router.dart';

/// `theme` defaults to a bare Material fallback: `lib/design_system/**`
/// (a parallel wave) didn't exist yet when this was written. Once it does,
/// wire `gleanLightTheme` in here — see the Router agent's report for this
/// follow-up. Accepting it as a parameter (rather than hard-coding a theme
/// in this file) is the seam: `main.dart` can start passing it the moment
/// it exists, with no change needed on this side.
class GleanApp extends ConsumerWidget {
  const GleanApp({this.theme, super.key});

  final ThemeData? theme;

  static final ThemeData _fallbackTheme = ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2E7D32)),
  );

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final GoRouter router = ref.watch(goRouterProvider);
    return MaterialApp.router(
      title: 'Glean',
      debugShowCheckedModeBanner: false,
      theme: theme ?? _fallbackTheme,
      routerConfig: router,
    );
  }
}
