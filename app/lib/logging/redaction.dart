/// A named credential and its value: `refresh_token=x`, `"password":"x"`, `Authorization: Basic x`.
final RegExp _namedSecret = RegExp(
  r'''(access_token|refresh_token|id_token|token|secret|client_secret|password|passwd|api[_-]?key|authorization)(["']?\s*[:=]\s*["']?)(?:(?:Bearer|Basic)\s+)?[^\s"',;&}]+''',
  caseSensitive: false,
);

/// A Bearer credential or a compact JWT (three base64url segments, the first two starting `eyJ`).
final RegExp _bearerOrJwt = RegExp(
  r'Bearer\s+\S+|eyJ[\w-]+\.eyJ[\w-]+\.[\w-]*',
  caseSensitive: false,
);

/// An unnamed opaque run: 32 or more hex or base64 characters.
final RegExp _longOpaqueRun = RegExp(r'[A-Za-z0-9+/_-]{32,}={0,2}');

/// Replaces anything that looks like an auth token, named or not, so a log line can never leak one.
String redactSecrets(String text) => text
    .replaceAllMapped(_namedSecret, (m) => '${m[1]}${m[2]}[redacted]')
    .replaceAll(_bearerOrJwt, '[redacted]')
    .replaceAll(_longOpaqueRun, '[redacted]');
