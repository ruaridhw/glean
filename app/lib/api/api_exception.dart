/// Typed error hierarchy for [GleanApiClient].
///
/// The RN client (`mobile/src/api/client.ts`) had exactly one error type
/// (`ApiError`, a status code + message) and no client timeout at all, so a
/// stalled `fetch` in scan-progress just hung on "Almost done..." forever
/// (FLUTTER_MIGRATION.md §11). The UI needs to tell "you're signed out"
/// apart from "that took too long" apart from "the server rejected it", so
/// every failure this client can produce is exactly one of the five
/// subtypes below — never a bare `Exception`, never swallowed.
library;

/// Base type for every error [GleanApiClient] can throw. Catch this to
/// handle "any API failure"; switch on the concrete subtype (or use a
/// sealed `switch`) to handle them differently.
sealed class ApiException implements Exception {
  const ApiException(this.message);

  /// Human-readable description. Not necessarily fit for direct display —
  /// callers own how they present a given subtype to the user.
  final String message;

  @override
  String toString() => '$runtimeType: $message';
}

/// The request never reached the server, or the connection dropped before a
/// response arrived (DNS failure, connection refused, TLS error, socket
/// reset, ...). Distinct from [ApiTimeoutException]: this is "couldn't
/// connect", not "connected but too slow".
final class ApiNetworkException extends ApiException {
  const ApiNetworkException(super.message);
}

/// The request exceeded [GleanApiClient.timeout] (AC-PAN-14). Every request
/// this client makes has a timeout, so this is always reachable — no
/// endpoint can hang indefinitely the way the RN scan-progress screen did.
final class ApiTimeoutException extends ApiException {
  const ApiTimeoutException(this.path) : super('Request to $path timed out');

  /// The request path that timed out, e.g. `/receipts/scan`.
  final String path;
}

/// The server returned 401 or 403 — the caller has no token, an expired
/// token, or a token the server rejects. The UI's job on catching this is
/// to route to (or surface) sign-in, never to retry silently.
final class ApiAuthException extends ApiException {
  const ApiAuthException({required this.statusCode, required String message})
    : super(message);

  final int statusCode;
}

/// The server returned 422 — it rejected the request body/query as invalid
/// (a FastAPI/Pydantic validation failure). [detail] carries the raw
/// `detail` payload from the response body — either a string or a list of
/// Pydantic error objects — for a caller that wants field-level detail.
final class ApiValidationException extends ApiException {
  const ApiValidationException({required String message, this.detail})
    : super(message);

  final Object? detail;
}

/// Any other non-2xx response: 5xx, or a 4xx not already special-cased
/// above. Treated as "the server rejected or failed the request" — the UI
/// shows a generic failure rather than pretending it's offline or a client
/// bug.
final class ApiServerException extends ApiException {
  const ApiServerException({required this.statusCode, required String message})
    : super(message);

  final int statusCode;
}

/// The response body wasn't shaped the way this client expects — malformed
/// JSON, a missing required field (e.g. a parsed ingredient with no
/// `category`), or a type mismatch. A decode failure must never crash the
/// caller; it always surfaces as this instead.
final class ApiParseException extends ApiException {
  const ApiParseException(super.message);
}
