import 'package:flutter/material.dart';

import 'legal_page.dart';

/// Terms of Service / Privacy Policy — **real tappable links** (AC-SET-04).
/// RN showed these as a single plain, unlinked sentence
/// (`mobile/app/sign-in.tsx:70-72`); each row here is a themed, tappable
/// `ListTile` that pushes a real destination (see `legal_page.dart` for why
/// that's an in-app page rather than an external URL for now).
class LegalLinksSection extends StatelessWidget {
  const LegalLinksSection({super.key});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Column(
        children: <Widget>[
          ListTile(
            leading: const Icon(Icons.description_outlined),
            title: const Text('Terms of Service'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => _openLegalPage(
              context,
              title: 'Terms of Service',
              body: termsOfServicePlaceholder,
            ),
          ),
          const Divider(height: 1),
          ListTile(
            leading: const Icon(Icons.privacy_tip_outlined),
            title: const Text('Privacy Policy'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => _openLegalPage(
              context,
              title: 'Privacy Policy',
              body: privacyPolicyPlaceholder,
            ),
          ),
        ],
      ),
    );
  }

  void _openLegalPage(
    BuildContext context, {
    required String title,
    required String body,
  }) {
    Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (BuildContext context) => LegalPage(title: title, body: body),
      ),
    );
  }
}
