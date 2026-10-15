import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../design_system/haptics.dart';
import '../features/auth/widgets/signed_out_banner.dart';
import '../features/auth/widgets/offline_banner.dart';

/// The five-tab shell, built by [StatefulShellRoute.indexedStack]; each tab keeps its own back stack.
/// Mounts [SignedOutBanner] once above every tab, since token expiry is cross-cutting. It renders nothing
/// while AI features are available. Icons are Material `_rounded` variants.
class AppShell extends ConsumerWidget {
  const AppShell({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  // Only `icon` is set (`_rounded`, used for both states); the indicator pill and label show the active tab.
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
          const OfflineBanner(),
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
