import 'package:json_annotation/json_annotation.dart';

import 'parsed_ingredient.dart';

part 'receipts.g.dart';

/// Request body for `POST /receipts/describe`.
@JsonSerializable(createFactory: false)
class DescribeRequest {
  const DescribeRequest({required this.text});

  final String text;

  Map<String, dynamic> toJson() => _$DescribeRequestToJson(this);
}

/// Response body for both `POST /receipts/scan` and `POST /receipts/describe`
/// — the backend uses one `ScanResponse` Pydantic schema for both routes
/// (`backend/src/glean/receipts/router.py`), so one model here covers both.
@JsonSerializable(createToJson: false)
class ScanResponse {
  const ScanResponse({required this.items});

  factory ScanResponse.fromJson(Map<String, dynamic> json) =>
      _$ScanResponseFromJson(json);

  final List<ParsedIngredient> items;
}
