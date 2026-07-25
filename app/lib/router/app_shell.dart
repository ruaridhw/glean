import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../design_system/haptics.dart';
import '../features/auth/widgets/signed_out_banner.dart';

/// The five-tab shell. Built once by [StatefulShellRoute.indexedStack] and
/// handed a [StatefulNavigationShell] that keeps one independent `Navigator`
/// (and therefore one independent back stack) per tab — the direct analogue
/// of the RN app's per-tab `Stack` navigators (AC-TEST-14).
///
/// Icons are plain Material `Icons` `_rounded` variants per AC-DS-01/AC-DS-06
/// — no Cupertino, no icon package.
///
/// R-08: mounts [SignedOutBanner] once here, above every tab, rather than
/// asking each of the five screens to remember it individually — a token
/// expiry is a cross-cutting concern, not a per-feature one, so this is the
/// one place a user is guaranteed to see it regardless of which tab they're
/// on. It renders nothing while AI features are available.
class AppShell extends ConsumerWidget {
  const AppShell({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  // R-13/AC-DS-06: these previously paired an `_outlined` unselected icon
  // with a `_rounded` `selectedIcon` — a common Material 3 convention, but
  // AC-DS-06's sanctioned exception to "`_rounded` throughout" is a
  // vendored SVG for a glyph with no rounded equivalent, not a different
  // built-in suffix. A rounded equivalent exists for all five, so there is
  // nothing to justify here — `selectedIcon` is simply dropped and `icon`
  // switched to `_rounded`, which `NavigationDestination` then uses for
  // both states. The selection indicator pill plus the label already
  // convey which tab is active.
  static const List<NavigationDestination> _destinations =
      <NavigationDestination>[
        NavigationDestination(icon: Icon(Icons.eco_rounded), label: 'Pantry'),
        NavigationDestination(
          icon: Icon(Icons.restaurant_rounded),
          label: 'Meals',
        ),
        NavigationDestination(
          icon: Icon(Icons.calendar_month_rounded),
          label: 'Plan',
        ),
        NavigationDestination(
          icon: Icon(Icons.shopping_cart_rounded),
          label: 'Shop',
        ),
        NavigationDestination(
          icon: Icon(Icons.settings_rounded),
          label: 'Settings',
        ),
      ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: Column(
        children: <Widget>[
          const SignedOutBanner(),
          Expanded(child: navigationShell),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        destinations: _destinations,
        onDestinationSelected: (int index) {
          ref.read(hapticsProvider).selectionClick();
          navigationShell.goBranch(
            index,
            // Tapping the already-active tab resets it to its initial
            // location; tapping another tab restores that branch's own stack
            // exactly where it was left.
            initialLocation: index == navigationShell.currentIndex,
          );
        },
      ),
    );
  }
}
