import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/auth/auth_controller.dart'
    show aiFeaturesAvailableProvider;
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

/// The single entry point for all three intake modes (AC-PAN-03) — reachable
/// whether the pantry is empty or full, unlike the RN app, where nothing
/// routed to manual entry at all and "Describe" vanished the moment the
/// pantry owned one item.
///
/// R-08/AC-AUTH-04: "Scan receipt" and "Describe purchase" both call the AI
/// backend, so both are disabled while `aiFeaturesAvailableProvider` is
/// false — "Manual entry" is a purely local write and stays available.
class PantryAddSheet extends ConsumerWidget {
  const PantryAddSheet({super.key});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (BuildContext context) => const PantryAddSheet(),
    );
  }

  void _choose(BuildContext context, WidgetRef ref, VoidCallback navigate) {
    ref.read(hapticsProvider).lightImpact();
    Navigator.of(context).pop();
    navigate();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppTokens tokens = context.tokens;
    final bool aiAvailable = ref.watch(aiFeaturesAvailableProvider);
    return SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(
          tokens.spacing.lg,
          0,
          tokens.spacing.lg,
          tokens.spacing.lg,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Padding(
              padding: EdgeInsets.only(bottom: tokens.spacing.sm),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Add to pantry',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
            ),
            ListTile(
              enabled: aiAvailable,
              leading: const Icon(Icons.camera_alt_rounded),
              title: const Text('Scan receipt'),
              subtitle: const Text('Take a photo of your receipt'),
              onTap: () => _choose(
                context,
                ref,
                () => context.pushNamed(
                  AppRoutes.intakeScan.name,
                  extra: const ScanArgs(),
                ),
              ),
            ),
            ListTile(
              enabled: aiAvailable,
              leading: const Icon(Icons.chat_bubble_outline_rounded),
              title: const Text('Describe purchase'),
              subtitle: const Text('Type what you bought'),
              onTap: () => _choose(
                context,
                ref,
                () => context.pushNamed(AppRoutes.intakeDescribePantry.name),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.edit_rounded),
              title: const Text('Manual entry'),
              subtitle: const Text('Add a single item yourself'),
              onTap: () => _choose(
                context,
                ref,
                () => context.pushNamed(AppRoutes.intakeManualEntry.name),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
