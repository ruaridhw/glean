/// Pure, dependency-free auth-session logic — the Flutter port of the Expo
/// app's `src/auth/mode.ts` (see git history; FLUTTER_MIGRATION.md §5, §10
/// "auth-mode logic").
///
/// **What changed in the port, deliberately (§5 "structure, not a flag")**:
/// the RN version decided *for itself* whether to bypass real auth by
/// reading `__DEV__`/`EXPO_PUBLIC_AUTH_BYPASS` env vars inline. Flutter moves
/// that decision to *which entrypoint compiled* — `main.dart` never links
/// against anything that can set a bypass identity, so [resolveAuthSession]
/// below takes "is bypass requested" as a plain parameter from its caller
/// rather than reading global/environment state itself. Only
/// `lib/auth/auth_bypass.dart` (isolated; never imported by `main.dart`'s
/// graph) ever passes a non-null [bypassUserId].
library;

/// Where an [AuthSession]'s truth came from.
enum AuthSessionSource {
  /// `main_e2e.dart` installed a fixed identity — see `auth_bypass.dart`.
  bypass,

  /// Derived from whatever is (or isn't) in secure storage.
  tokens,
}

/// The raw, storage-shaped values [resolveAuthSession] decides from —
/// mirrors mobile's `StoredAuthValues`.
class StoredAuthValues {
  const StoredAuthValues({this.accessToken, this.refreshToken, this.userSub});

  final String? accessToken;
  final String? refreshToken;
  final String? userSub;
}

/// The resolved session shape — mirrors mobile's `AuthSession`. Value-equal
/// so tests can assert on it directly, the same way the mobile tests use
/// Jest's `toEqual`.
class AuthSession {
  const AuthSession({
    required this.authenticated,
    required this.accessToken,
    required this.refreshToken,
    required this.userSub,
    required this.source,
  });

  final bool authenticated;
  final String? accessToken;
  final String? refreshToken;
  final String? userSub;
  final AuthSessionSource source;

  @override
  bool operator ==(Object other) =>
      other is AuthSession &&
      other.authenticated == authenticated &&
      other.accessToken == accessToken &&
      other.refreshToken == refreshToken &&
      other.userSub == userSub &&
      other.source == source;

  @override
  int get hashCode =>
      Object.hash(authenticated, accessToken, refreshToken, userSub, source);

  @override
  String toString() =>
      'AuthSession(authenticated: $authenticated, accessToken: $accessToken, '
      'refreshToken: $refreshToken, userSub: $userSub, source: $source)';
}

/// The identity `main_e2e.dart` uses when its caller doesn't supply one —
/// ported from mobile's `AUTH_BYPASS_USER_SUB`.
const String kAuthBypassUserSub = 'e2e-bypass-user-sub';

/// Direct port of mobile's `resolveAuthSession`. If [bypassUserId] is
/// non-null, the session is authenticated as that identity with no tokens at
/// all (mirrors mobile: `accessToken`/`refreshToken` are `null` under
/// bypass — there is nothing to refresh, and every backend LLM router still
/// requires a valid token, so a bypass build simply can't call one). Absent
/// that, authentication is decided the same way mobile's `hasTokens()`-backed
/// resolution does: a present, non-empty access token.
AuthSession resolveAuthSession({
  required StoredAuthValues stored,
  String? bypassUserId,
}) {
  if (bypassUserId != null) {
    return AuthSession(
      authenticated: true,
      accessToken: null,
      refreshToken: null,
      userSub: bypassUserId,
      source: AuthSessionSource.bypass,
    );
  }

  final bool authenticated =
      stored.accessToken != null && stored.accessToken!.isNotEmpty;
  return AuthSession(
    authenticated: authenticated,
    accessToken: stored.accessToken,
    refreshToken: stored.refreshToken,
    userSub: stored.userSub,
    source: AuthSessionSource.tokens,
  );
}

/// Loopback/emulator hosts a local or CI backend can legitimately run on.
/// `10.0.2.2` is the Android emulator's alias for the host machine's
/// `localhost`.
const Set<String> _nonProductionHosts = <String>{
  'localhost',
  '127.0.0.1',
  '10.0.2.2',
  '::1',
};

/// AC-AUTH-06 / §5: is [apiBaseUrl] a production backend? Fails **safe**:
/// anything that doesn't parse, or whose host isn't a recognized
/// local/loopback address, counts as production. This is deliberately
/// broader than "matches our known prod domain" — the point of this guard
/// is that the e2e entrypoint must refuse to run against *any* real
/// deployed backend, staging included, not just a hardcoded production
/// hostname a future environment could rename.
bool isProductionApiBaseUrl(String apiBaseUrl) {
  final Uri? uri = Uri.tryParse(apiBaseUrl);
  if (uri == null || uri.host.isEmpty) return true;
  return !_nonProductionHosts.contains(uri.host.toLowerCase());
}
