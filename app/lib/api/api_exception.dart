/// Typed error hierarchy for [GleanApiClient]. The UI must tell "signed out" from "took too long" from "server
/// rejected it", so every failure is exactly one of the subtypes below, never a bare `Exception`, never swallowed.
library;

/// Base type for every error [GleanApiClient] can throw; switch on the concrete subtype.
sealed class ApiException implements Exception {
  const ApiException(this.message);

  /// Human-readable description; callers own how to present it.
  final String message;

  @override
  String toString() => '$runtimeType: $message';
}

/// The request never reached the server, or the connection dropped before a response (DNS, refused, TLS,
/// reset). Distinct from [ApiTimeoutException].
final class ApiNetworkException extends ApiException {
  const ApiNetworkException(super.message);
}

/// The request exceeded [GleanApiClient.timeout]. Every request has a timeout, so no endpoint can hang.
final class ApiTimeoutException extends ApiException {
  const ApiTimeoutException(this.path) : super('Request to $path timed out');

  final String path;
}

/// The server returned 401 or 403. The UI should route to or surface sign-in, never retry silently.
final class ApiAuthException extends ApiException {
  const ApiAuthException({required this.statusCode, required String message})
    : super(message);

  final int statusCode;
}

/// The server returned 429: this user has used up the hourly allowance for AI requests. Retrying straight away
/// fails identically, so callers show [userMessage] rather than a generic "try again".
final class ApiRateLimitException extends ApiException {
  const ApiRateLimitException(super.message);

  String get userMessage =>
      'You have reached the hourly limit for AI features. '
      'Try again in a little while.';
}

/// The server returned 422 (a FastAPI/Pydantic validation failure). [detail] is the raw `detail` payload: a
/// string or a list of error objects.
final class ApiValidationException extends ApiException {
  const ApiValidationException({required String message, this.detail})
    : super(message);

  final Object? detail;
}

/// Any other non-2xx response; the UI shows a generic failure.
final class ApiServerException extends ApiException {
  const ApiServerException({required this.statusCode, required String message})
    : super(message);

  final int statusCode;
}

/// The response body wasn't shaped as expected (malformed JSON, a missing required field, a type mismatch); a
/// decode failure surfaces as this rather than crashing the caller.
final class ApiParseException extends ApiException {
  const ApiParseException(super.message, {this.field, this.reason});

  /// The JSON key that was missing or invalid, when the decoder could name it.
  final String? field;

  /// A short, body-free reason, safe to log.
  final String? reason;
}
