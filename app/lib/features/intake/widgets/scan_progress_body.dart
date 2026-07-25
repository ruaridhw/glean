import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// The "honest progress" body (AC-PAN-06): one real indeterminate indicator,
/// no fake staged steps and no artificial delay after the API returns — the
/// RN app's three time-driven steps desynced from the real request and added
/// ~2.3s of guaranteed latency on top of it. A cancel is always reachable, so
/// a slow request never becomes a dead end.
class ScanProgressBody extends StatelessWidget {
  const ScanProgressBody({super.key, required this.onCancel});

  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Center(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const CircularProgressIndicator(),
            SizedBox(height: tokens.spacing.xl),
            Text(
              'Reading your receipt…',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            SizedBox(height: tokens.spacing.sm),
            Text(
              "This won't take long.",
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            SizedBox(height: tokens.spacing.xl),
            TextButton(onPressed: onCancel, child: const Text('Cancel')),
          ],
        ),
      ),
    );
  }
}

/// The error body once the API call fails or times out (AC-PAN-14): a scan
/// failure must never hang forever and must never be silent — the RN
/// `scan-progress` screen had no try/catch and no timeout at all, hanging on
/// "Almost done…" with no way back.
class ScanProgressError extends StatelessWidget {
  const ScanProgressError({
    super.key,
    required this.message,
    required this.onRetry,
    required this.onBack,
  });

  final String message;
  final VoidCallback onRetry;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Center(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(
              Icons.error_outline_rounded,
              size: 40,
              color: Theme.of(context).colorScheme.error,
            ),
            SizedBox(height: tokens.spacing.lg),
            Text(message, textAlign: TextAlign.center),
            SizedBox(height: tokens.spacing.xl),
            FilledButton(onPressed: onRetry, child: const Text('Try again')),
            SizedBox(height: tokens.spacing.sm),
            TextButton(onPressed: onBack, child: const Text('Back')),
          ],
        ),
      ),
    );
  }
}
