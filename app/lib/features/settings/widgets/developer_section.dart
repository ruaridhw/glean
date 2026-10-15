import 'package:flutter/material.dart';

/// The "Developer" card, shown once developer mode is unlocked: Export diagnostics and Restore from backup.
class DeveloperSection extends StatelessWidget {
  const DeveloperSection({
    super.key,
    required this.onExportDiagnostics,
    required this.exporting,
    required this.onRestoreBackup,
    required this.restoring,
  });

  final VoidCallback onExportDiagnostics;
  final bool exporting;
  final VoidCallback onRestoreBackup;
  final bool restoring;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Align(
          alignment: Alignment.centerLeft,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              TextButton.icon(
                key: const Key('settings.exportDiagnostics'),
                onPressed: exporting ? null : onExportDiagnostics,
                icon: const Icon(Icons.upload_file_rounded),
                label: Text(exporting ? 'Exporting…' : 'Export diagnostics'),
              ),
              TextButton.icon(
                key: const Key('settings.restoreBackup'),
                onPressed: restoring ? null : onRestoreBackup,
                icon: const Icon(Icons.settings_backup_restore_rounded),
                label: Text(restoring ? 'Restoring…' : 'Restore from backup'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
