import '../api/api_exception.dart';
import 'redaction.dart';

const int _maxMessageLength = 200;

/// A bounded, body-free description of [error] that is safe to write to the log.
///
/// Exceptions can carry response bodies (a `FormatException` quotes its source, an `ApiParseException` wraps
/// one), so API and parse errors are described by type, status and field only. Anything else keeps its type plus
/// a short, redacted, single-line message.
String describeError(Object error) {
  return switch (error) {
    ApiParseException(:final field?) =>
      'ApiParseException: field "$field" is missing or invalid',
    ApiParseException(:final reason) =>
      'ApiParseException: ${reason ?? 'response could not be decoded'}',
    ApiAuthException(:final statusCode) ||
    ApiServerException(
      :final statusCode,
    ) => '${error.runtimeType}: HTTP $statusCode',
    ApiValidationException() => 'ApiValidationException: HTTP 422',
    ApiTimeoutException() ||
    ApiNetworkException() => error.runtimeType.toString(),
    FormatException() => 'FormatException: malformed input',
    _ => '${error.runtimeType}: ${_shorten(error.toString())}',
  };
}

String _shorten(String message) {
  final String oneLine = redactSecrets(
    message,
  ).replaceAll(RegExp(r'\s+'), ' ').trim();
  return oneLine.length <= _maxMessageLength
      ? oneLine
      : '${oneLine.substring(0, _maxMessageLength)}…';
}
