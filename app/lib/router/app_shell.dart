import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// The five-tab shell. Built once by [StatefulShellRoute.indexedStack] and
/// handed a [StatefulNavigationShell] that keeps one independent `Navigator`
/// (and therefore one independent back stack) per tab — the direct analogue
/// of the RN app's per-tab `Stack` navigators (AC-TEST-14).
///
/// Icons are plain Material `Icons` (`_rounded`/`_outlined` variants) per
/// AC-DS-01/AC-DS-06 — no Cupertino, no icon package.
class AppShell extends StatelessWidget {
  const AppShell({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  static const List<NavigationDestination> _destinations =
      <NavigationDestination>[
        NavigationDestination(
          icon: Icon(Icons.eco_outlined),
          selectedIcon: Icon(Icons.eco_rounded),
          label: 'Pantry',
        ),
        NavigationDestination(
          icon: Icon(Icons.restaurant_outlined),
          selectedIcon: Icon(Icons.restaurant_rounded),
          label: 'Meals',
        ),
        NavigationDestination(
          icon: Icon(Icons.calendar_month_outlined),
          selectedIcon: Icon(Icons.calendar_month_rounded),
          label: 'Plan',
        ),
        NavigationDestination(
          icon: Icon(Icons.shopping_cart_outlined),
          selectedIcon: Icon(Icons.shopping_cart_rounded),
          label: 'Shop',
        ),
        NavigationDestination(
          icon: Icon(Icons.settings_outlined),
          selectedIcon: Icon(Icons.settings_rounded),
          label: 'Settings',
        ),
      ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        destinations: _destinations,
        onDestinationSelected: (int index) => navigationShell.goBranch(
          index,
          // Tapping the already-active tab resets it to its initial
          // location; tapping another tab restores that branch's own stack
          // exactly where it was left.
          initialLocation: index == navigationShell.currentIndex,
        ),
      ),
    );
  }
}
