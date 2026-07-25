/// Trim/validate wrapper for free-text API request bodies.
///
/// Ported from `mobile/src/normalization/text-input.ts`, which — per the
/// API module brief — was the only logic in the RN `api/hooks.ts` its own
/// tests actually exercised. Behaviour, not structure: outer whitespace is
/// trimmed, intentional internal newlines/spacing (a multi-line shopping
/// description) are preserved, and text that is empty after trimming is
/// rejected before anything is sent over the wire.
library;

/// Thrown by [requireSubmittedText] when a piece of user-submitted text is
/// empty (or all whitespace) after trimming.
final class EmptyTextInputException implements Exception {
  const EmptyTextInputException([this.message = 'Text input cannot be empty']);

  final String message;

  @override
  String toString() => 'EmptyTextInputException: $message';
}

/// Trims only the outer whitespace of [value], preserving any internal
/// newlines or spacing the user typed intentionally.
String normalizeSubmittedText(String value) => value.trim();

/// Returns [value] trimmed, or `null` if nothing remains once trimmed.
String? toRequiredSubmittedText(String value) {
  final normalized = normalizeSubmittedText(value);
  return normalized.isEmpty ? null : normalized;
}

/// Returns [value] trimmed, or throws [EmptyTextInputException] if nothing
/// remains once trimmed. Used at the point a describe/parse request body is
/// built, so an empty submission never reaches the network.
String requireSubmittedText(String value) {
  final normalized = toRequiredSubmittedText(value);
  if (normalized == null) {
    throw const EmptyTextInputException();
  }
  return normalized;
}
