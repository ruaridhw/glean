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
