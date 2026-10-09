import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';

/// Network presence, not an Internet-reachability promise. Mirrors Expo's
/// isConnected banner; unknown/plugin failure is not claimed to be offline.
final offlineProvider = StreamProvider<bool>((ref) async* {
  final network = Connectivity();
  yield (await network.checkConnectivity()).contains(ConnectivityResult.none);
  yield* network.onConnectivityChanged
      .map((types) => types.contains(ConnectivityResult.none))
      .distinct();
});

class OfflineBanner extends ConsumerWidget {
  const OfflineBanner({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (ref.watch(offlineProvider).value != true) {
      return const SizedBox.shrink();
    }
    final tokens = context.tokens;
    return SafeArea(
      bottom: false,
      child: ColoredBox(
        color: tokens.warningLight,
        child: Padding(
          padding: EdgeInsets.symmetric(
            vertical: tokens.spacing.sm,
            horizontal: tokens.spacing.lg,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.cloud_off_rounded, size: 14, color: tokens.warning),
              SizedBox(width: tokens.spacing.sm),
              Flexible(
                child: Text(
                  "You're offline. Some features need internet.",
                  style: Theme.of(
                    context,
                  ).textTheme.labelMedium?.copyWith(color: tokens.warning),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
