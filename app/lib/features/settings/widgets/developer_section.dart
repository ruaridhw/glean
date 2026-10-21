import 'package:flutter/material.dart';

import '../../../design_system/design_system.dart';

/// The "Developer" card, shown once developer mode is unlocked: Export diagnostics and Restore from backup.
class DeveloperSection extends StatelessWidget {
  const DeveloperSection({
    super.key,
    required this.onExportDiagnostics,
    required this.exporting,
    required this.onRestoreBackup,
    required this.restoring,
    this.restoreUnavailable = false,
  });

  final VoidCallback onExportDiagnostics;
  final bool exporting;
  final VoidCallback onRestoreBackup;
  final bool restoring;

  /// True where a restore cannot work at all (the web dev loop, which has no database file of its own). The
  /// action stays visible, disabled, with [restoreUnavailableReason] under it.
  final bool restoreUnavailable;

  static const String restoreUnavailableReason =
      'Restore from backup is not available in the web build: it replaces the '
      'database file the app keeps on the device.';

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Card(
      child: Padding(
        padding: EdgeInsets.symmetric(
          horizontal: tokens.spacing.sm,
          vertical: tokens.spacing.xs,
        ),
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
                onPressed: (restoring || restoreUnavailable)
                    ? null
                    : onRestoreBackup,
                icon: const Icon(Icons.settings_backup_restore_rounded),
                label: Text(restoring ? 'Restoring…' : 'Restore from backup'),
              ),
              if (restoreUnavailable)
                Padding(
                  padding: EdgeInsets.only(
                    left: tokens.spacing.sm,
                    right: tokens.spacing.sm,
                    bottom: tokens.spacing.sm,
                  ),
                  child: Text(
                    restoreUnavailableReason,
                    key: const Key('settings.restoreUnavailable'),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
