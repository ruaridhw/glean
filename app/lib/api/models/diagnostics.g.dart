// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'diagnostics.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

DiagnosticsExportResponse _$DiagnosticsExportResponseFromJson(
  Map<String, dynamic> json,
) => $checkedCreate('DiagnosticsExportResponse', json, ($checkedConvert) {
  final val = DiagnosticsExportResponse(
    prefix: $checkedConvert('prefix', (v) => v as String),
  );
  return val;
});

BackupSummary _$BackupSummaryFromJson(Map<String, dynamic> json) =>
    $checkedCreate(
      'BackupSummary',
      json,
      ($checkedConvert) {
        final val = BackupSummary(
          id: $checkedConvert('id', (v) => v as String),
          createdAt: $checkedConvert(
            'created_at',
            (v) => DateTime.parse(v as String),
          ),
          prepared: $checkedConvert('prepared', (v) => v as bool),
          size: $checkedConvert('size', (v) => (v as num).toInt()),
          downloadUrl: $checkedConvert('download_url', (v) => v as String),
          label: $checkedConvert('label', (v) => v as String?),
          schemaVersion: $checkedConvert(
            'schema_version',
            (v) => (v as num?)?.toInt(),
          ),
        );
        return val;
      },
      fieldKeyMap: const {
        'createdAt': 'created_at',
        'downloadUrl': 'download_url',
        'schemaVersion': 'schema_version',
      },
    );

BackupListResponse _$BackupListResponseFromJson(Map<String, dynamic> json) =>
    $checkedCreate('BackupListResponse', json, ($checkedConvert) {
      final val = BackupListResponse(
        backups: $checkedConvert(
          'backups',
          (v) => (v as List<dynamic>)
              .map((e) => BackupSummary.fromJson(e as Map<String, dynamic>))
              .toList(),
        ),
      );
      return val;
    });
