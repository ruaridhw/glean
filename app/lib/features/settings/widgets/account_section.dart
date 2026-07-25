import 'package:flutter/material.dart';

/// The "Account" card — just sign-out. Uses a themed [TextButton] (via
/// `textButtonTheme`) tinted with `colorScheme.error`, not a hand-rolled
/// pill (AC-DS-05); no confirm dialog, matching every other destructive
/// action in this app being one tap plus recovery rather than a gate
/// (§6) — though sign-out itself has no "undo", since it neither deletes
/// nor mutates any local data (AC-DATA-09).
class AccountSection extends StatelessWidget {
  const AccountSection({super.key, required this.onSignOut});

  final VoidCallback onSignOut;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: onSignOut,
            style: TextButton.styleFrom(foregroundColor: colorScheme.error),
            icon: const Icon(Icons.logout_rounded),
            label: const Text('Sign out'),
          ),
        ),
      ),
    );
  }
}
