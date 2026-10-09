import 'package:flutter/material.dart';

/// The "Account" card: just sign-out, a themed [TextButton] tinted with `colorScheme.error`. No confirm dialog;
/// sign-out has no undo, since it deletes and mutates no local data.
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
