import 'parsed_ingredient.dart';

/// Request body for `POST /receipts/describe`.
class DescribeRequest {
  const DescribeRequest({required this.text});

  final String text;

  Map<String, dynamic> toJson() => {'text': text};
}

/// Response body for both `POST /receipts/scan` and `POST /receipts/describe`
/// — the backend uses one `ScanResponse` Pydantic schema for both routes
/// (`backend/src/glean/receipts/router.py`), so one model here covers both.
class ScanResponse {
  const ScanResponse({required this.items});

  factory ScanResponse.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>;
    return ScanResponse(
      items: rawItems
          .map(
            (item) => ParsedIngredient.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
    );
  }

  final List<ParsedIngredient> items;
}
