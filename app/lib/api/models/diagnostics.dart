import 'package:json_annotation/json_annotation.dart';

part 'diagnostics.g.dart';

/// Response body for `POST /dev/export-db`: where the export landed in the receipts bucket.
@JsonSerializable(createToJson: false)
class DiagnosticsExportResponse {
  const DiagnosticsExportResponse({required this.prefix});

  factory DiagnosticsExportResponse.fromJson(Map<String, dynamic> json) =>
      _$DiagnosticsExportResponseFromJson(json);

  /// `db-exports/<user id>/<UTC timestamp>/`, holding `glean.db` and `app.log`.
  final String prefix;
}

/// One backup in `GET /dev/backups`: an export (or an agent-prepared copy of one) the signed-in user can restore.
@JsonSerializable(createToJson: false)
class BackupSummary {
  const BackupSummary({
    required this.id,
    required this.createdAt,
    required this.prepared,
    required this.size,
    required this.downloadUrl,
    this.label,
    this.schemaVersion,
  });

  factory BackupSummary.fromJson(Map<String, dynamic> json) =>
      _$BackupSummaryFromJson(json);

  /// The S3 prefix the backup lives under, e.g. `db-exports/<user id>/<UTC timestamp>/`.
  final String id;

  @JsonKey(name: 'created_at')
  final DateTime createdAt;

  /// Produced by an agent from another backup, rather than exported by the app.
  final bool prepared;

  /// What the agent said it changed; only on prepared backups.
  final String? label;

  /// The database schema version recorded in the file; `null` when the file is not a SQLite database.
  @JsonKey(name: 'schema_version')
  final int? schemaVersion;

  final int size;

  /// A short-lived signed link; it carries its own authorisation.
  @JsonKey(name: 'download_url')
  final String downloadUrl;
}

/// Response body for `GET /dev/backups`: prepared backups first, then newest first.
@JsonSerializable(createToJson: false)
class BackupListResponse {
  const BackupListResponse({required this.backups});

  factory BackupListResponse.fromJson(Map<String, dynamic> json) =>
      _$BackupListResponseFromJson(json);

  final List<BackupSummary> backups;
}
