import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';

/// "Glean 1.0.0 (build)" footer. Tapping it is the developer-mode unlock gesture ([onTap]).
class VersionLabel extends StatelessWidget {
  const VersionLabel({super.key, required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<PackageInfo>(
      future: PackageInfo.fromPlatform(),
      builder: (BuildContext context, AsyncSnapshot<PackageInfo> snapshot) {
        final PackageInfo? info = snapshot.data;
        final String text = info == null
            ? 'Glean'
            : 'Glean ${info.version} (${info.buildNumber})';
        return GestureDetector(
          key: const Key('settings.versionLabel'),
          behavior: HitTestBehavior.opaque,
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Center(
              child: Text(text, style: Theme.of(context).textTheme.bodySmall),
            ),
          ),
        );
      },
    );
  }
}
