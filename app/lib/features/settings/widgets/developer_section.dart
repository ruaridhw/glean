import 'package:flutter/material.dart';

/// The "Developer" card, shown once developer mode is unlocked: just Export diagnostics.
class DeveloperSection extends StatelessWidget {
  const DeveloperSection({
    super.key,
    required this.onExportDiagnostics,
    required this.exporting,
  });

  final VoidCallback onExportDiagnostics;
  final bool exporting;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            key: const Key('settings.exportDiagnostics'),
            onPressed: exporting ? null : onExportDiagnostics,
            icon: const Icon(Icons.upload_file_rounded),
            label: Text(exporting ? 'Exporting…' : 'Export diagnostics'),
          ),
        ),
      ),
    );
  }
}
