import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api.dart';
import 'package:glean/diagnostics/diagnostics.dart';

/// The user's backups, prepared ones first and labelled. Pops with the chosen [BackupSummary].
class RestoreBackupSheet extends ConsumerWidget {
  const RestoreBackupSheet({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<BackupSummary>> backups = ref.watch(
      backupListProvider,
    );
    return SafeArea(
      child: backups.when(
        loading: () => const Padding(
          padding: EdgeInsets.all(24),
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (Object error, StackTrace _) => const Padding(
          padding: EdgeInsets.all(24),
          child: Text('Could not load backups. Try again.'),
        ),
        data: (List<BackupSummary> list) => list.isEmpty
            ? const Padding(
                padding: EdgeInsets.all(24),
                child: Text('No backups yet. Export diagnostics first.'),
              )
            : ListView(
                shrinkWrap: true,
                children: <Widget>[
                  for (final BackupSummary backup in list)
                    ListTile(
                      key: Key('restore.backup.${backup.id}'),
                      title: Text(_when(backup.createdAt)),
                      subtitle: Text(
                        <String>[
                          ?backup.label,
                          if (backup.schemaVersion != null)
                            'database v${backup.schemaVersion}',
                        ].join(' · '),
                      ),
                      trailing: backup.prepared
                          ? const Badge(label: Text('Prepared'))
                          : null,
                      onTap: () => Navigator.of(context).pop(backup),
                    ),
                ],
              ),
      ),
    );
  }
}

const List<String> _months = <String>[
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

String _when(DateTime at) {
  final DateTime t = at.toLocal();
  final String hh = t.hour.toString().padLeft(2, '0');
  final String mm = t.minute.toString().padLeft(2, '0');
  return '${t.day} ${_months[t.month - 1]} ${t.year}, $hh:$mm';
}
