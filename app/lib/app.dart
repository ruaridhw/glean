/// Root widget; each entrypoint wraps it in a `ProviderScope` and calls `runApp`.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'design_system/design_system.dart';
import 'router/router.dart';

/// `theme` exists only so a test can substitute one. There is deliberately no bare-Material fallback:
/// a theme without the `AppTokens` extension crashes any widget reading `context.tokens`.
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
