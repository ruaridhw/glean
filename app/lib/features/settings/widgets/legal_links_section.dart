import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';

import '../providers/link_opener.dart';

/// **Placeholder URLs.** No hosted Terms of Service / Privacy Policy page
/// exists anywhere for Glean yet — it is pre-launch, and the RN app only
/// ever showed a single unlinked sentence (the Expo app's
/// `app/sign-in.tsx:70-72`, see git history).
/// These two constants are the *only* place that placeholder lives; swap
/// them for the real hosted URLs once they exist and nothing else in this
/// file needs to change.
const String termsOfServiceUrl = 'https://glean.app/legal/terms-of-service';
const String privacyPolicyUrl = 'https://glean.app/legal/privacy-policy';

/// Terms of Service / Privacy Policy — **real tappable links** (AC-SET-04).
/// RN showed these as a single plain, unlinked sentence; each row here is a
/// themed, tappable `ListTile` that opens a real URL via [linkOpenerProvider]
/// (`url_launcher` under the hood).
class LegalLinksSection extends ConsumerWidget {
  const LegalLinksSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: Column(
        children: <Widget>[
          ListTile(
            leading: const Icon(Icons.description_outlined),
            title: const Text('Terms of Service'),
            trailing: const Icon(Icons.open_in_new_rounded),
            onTap: () => _open(context, ref, termsOfServiceUrl),
          ),
          const Divider(height: 1),
          ListTile(
            leading: const Icon(Icons.privacy_tip_outlined),
            title: const Text('Privacy Policy'),
            trailing: const Icon(Icons.open_in_new_rounded),
            onTap: () => _open(context, ref, privacyPolicyUrl),
          ),
        ],
      ),
    );
  }

  Future<void> _open(BuildContext context, WidgetRef ref, String url) async {
    final bool opened = await ref.read(linkOpenerProvider)(Uri.parse(url));
    if (!opened && context.mounted) {
      GleanSnackBar.show(context, 'Could not open the link.');
    }
  }
}
