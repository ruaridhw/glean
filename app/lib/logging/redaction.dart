/// Matches a Bearer credential or a compact JWT (three base64url segments, the first two starting `eyJ`).
final RegExp _secrets = RegExp(
  r'Bearer\s+\S+|eyJ[\w-]+\.eyJ[\w-]+\.[\w-]*',
  caseSensitive: false,
);

/// Replaces anything that looks like an auth token, so a log line can never leak one.
String redactSecrets(String text) => text.replaceAll(_secrets, '[redacted]');
