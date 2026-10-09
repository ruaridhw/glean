import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../router/auth_state.dart';
import 'cognito_auth_client.dart';
import 'token_storage.dart';
import 'tokens.dart';

/// What the app currently believes about the signed-in user. Immutable so
/// `==`/tests can compare snapshots directly.
@immutable
class AuthSessionSnapshot {
  const AuthSessionSnapshot({required this.status, this.userId, this.tokens});

  final AuthStatus status;

  /// The stable Cognito `sub` — non-null whenever [status] is `active` or
  /// `expired` (expiry must still resolve a user id so local reads keep
  /// working). Only `null` when `signedOut`.
  final String? userId;

  /// Non-null only while `active` with a real session. A failed refresh
  /// clears this (moving to `expired`) without touching [userId] — see
  /// [AuthController.getValidAccessToken].
  final CognitoTokens? tokens;

  static const AuthSessionSnapshot signedOut = AuthSessionSnapshot(
    status: AuthStatus.signedOut,
  );

  @override
  bool operator ==(Object other) =>
      other is AuthSessionSnapshot &&
      other.status == status &&
      other.userId == userId &&
      other.tokens == tokens;

  @override
  int get hashCode => Object.hash(status, userId, tokens);
}

/// Owns the signed-in session end to end: Cognito sign-in/refresh/sign-out
/// and its secure-storage persistence. It is the only place session state is
/// held — [authStatusProvider], `currentUserIdProvider` and
/// `apiAccessTokenProvider` all derive from [authControllerProvider].
///
/// Seeded with a snapshot computed **before** `runApp`
/// ([loadInitialAuthSnapshot]): `currentUserIdProvider` is a synchronous
/// `Provider<String>` every repository depends on, so it must be correct on
/// its very first read, with no "still checking secure storage" state.
///
/// Every await is guarded by a session epoch: sign-out (or a new sign-in)
/// bumps it, so a refresh or storage write that completes afterwards neither
/// republishes state nor persists stale tokens. Storage writes run one at a
/// time, and sign-out's clear always runs.
class AuthController extends Notifier<AuthSessionSnapshot> {
  AuthController(this._seed, {required this._storage, required this._client});

  final AuthSessionSnapshot _seed;
  final TokenStorage _storage;
  final CognitoAuthClient _client;
  int _sessionEpoch = 0;
  Future<String?>? _refreshing;
  Future<void> _storageWrites = Future.value();

  Future<void> _write(int? epoch, Future<void> Function() operation) {
    return _storageWrites = _storageWrites.catchError((Object _) {}).then((
      _,
    ) async {
      if (epoch == null || epoch == _sessionEpoch) await operation();
    });
  }

  @override
  AuthSessionSnapshot build() => _seed;

  /// Replaces the session outright, for tests that flip status on a live
  /// app (e.g. `active` to `expired`) without driving a real refresh.
  @visibleForTesting
  void debugSetSnapshot(AuthSessionSnapshot snapshot) => state = snapshot;

  /// Awaits and consumes [CognitoAuthClient.signIn]'s return value directly.
  ///
  /// Fires no haptic itself — `SignInScreen` fires both the tap
  /// acknowledgement and the success commit, so a sign-in never buzzes
  /// twice.
  Future<void> signIn() async {
    final epoch = ++_sessionEpoch;
    _refreshing = null;
    final CognitoTokens tokens = await _client.signIn();
    await _write(epoch, () => _storage.saveTokens(tokens));
    if (epoch != _sessionEpoch) return;
    state = AuthSessionSnapshot(
      status: AuthStatus.active,
      userId: tokens.userSub,
      tokens: tokens,
    );
  }

  /// Clears every stored value explicitly — iOS Keychain items survive an
  /// app uninstall/reinstall, so this, not "reinstall == signed out", is
  /// the only reliable sign-out. Deliberately touches no drift table: a
  /// different user simply sees their own (empty) data next time.
  Future<void> signOut() async {
    ++_sessionEpoch;
    _refreshing = null;
    state = AuthSessionSnapshot.signedOut;
    // The destructive clear stays ahead of any later session write, even
    // if a later sign-in fails before it can persist a replacement.
    await _write(null, _storage.clearAll);
  }

  /// Returns a currently valid access token, refreshing first if the cached
  /// one has expired. Returns `null` if there is no session, or if a
  /// refresh attempt fails — never a token known to be invalid. Concurrent
  /// callers share one in-flight refresh.
  Future<String?> getValidAccessToken() async {
    final AuthSessionSnapshot snapshot = state;
    final CognitoTokens? tokens = snapshot.tokens;
    if (tokens == null) return null;
    if (!tokens.isExpired) return tokens.accessToken;

    if (_refreshing != null) return _refreshing;
    final operation = _refresh(snapshot, _sessionEpoch);
    _refreshing = operation;
    try {
      return await operation;
    } finally {
      if (identical(_refreshing, operation)) _refreshing = null;
    }
  }

  Future<String?> _refresh(AuthSessionSnapshot snapshot, int epoch) async {
    final CognitoTokens? refreshed = await _client.refresh(
      snapshot.tokens!.refreshToken,
    );
    if (epoch != _sessionEpoch) return null;
    if (refreshed == null) {
      // Never leave storage disagreeing with "no longer authenticated", but
      // keep the user id: local reads must keep working.
      await _write(epoch, _storage.clearTokensKeepIdentity);
      if (epoch != _sessionEpoch) return null;
      state = AuthSessionSnapshot(
        status: AuthStatus.expired,
        userId: snapshot.userId,
      );
      return null;
    }

    await _write(epoch, () => _storage.saveTokens(refreshed));
    if (epoch != _sessionEpoch) return null;
    state = AuthSessionSnapshot(
      status: AuthStatus.active,
      userId: refreshed.userSub,
      tokens: refreshed,
    );
    return refreshed.accessToken;
  }
}

/// The session. Has no default: `main.dart`, `main_e2e.dart` and the test
/// harness each override it with an [AuthController] seeded for their
/// context.
final NotifierProvider<AuthController, AuthSessionSnapshot>
authControllerProvider = NotifierProvider<AuthController, AuthSessionSnapshot>(
  () => throw UnimplementedError(
    'authControllerProvider has no default — override it from main.dart / '
    'main_e2e.dart / the test harness with a seeded AuthController.',
  ),
);

/// Reads secure storage once to compute the [AuthSessionSnapshot]
/// `main.dart` seeds [AuthController] with, **before** `runApp` — see
/// [AuthController]'s doc comment for why.
Future<AuthSessionSnapshot> loadInitialAuthSnapshot(
  TokenStorage storage,
) async {
  final StoredTokenValues(
    :accessToken,
    :refreshToken,
    :idToken,
    :userSub,
    :email,
    :expiresAt,
  ) = await storage
      .readTokens();

  // No usable access token: an identity left behind by a failed refresh
  // reopens as `expired` (local data readable), otherwise signed out.
  if (accessToken == null || accessToken.isEmpty) {
    return userSub == null || userSub.isEmpty
        ? AuthSessionSnapshot.signedOut
        : AuthSessionSnapshot(status: AuthStatus.expired, userId: userSub);
  }

  // An access token with a missing id token, refresh token, expiry, or user
  // sub is a corrupt/partial record (this class never writes one, but
  // storage is external state) — degrade to signed out rather than build
  // unusable tokens.
  if (idToken == null ||
      refreshToken == null ||
      userSub == null ||
      expiresAt == null) {
    return AuthSessionSnapshot.signedOut;
  }

  return AuthSessionSnapshot(
    status: AuthStatus.active,
    userId: userSub,
    tokens: CognitoTokens(
      accessToken: accessToken,
      refreshToken: refreshToken,
      idToken: idToken,
      userSub: userSub,
      email: email ?? '',
      expiresAt: expiresAt,
    ),
  );
}

/// "Are AI-backed features usable right now?" — what Meals/Plan/Pantry/Shop
/// gate Scan/Describe/Import/Generate on. `false` for both `expired` and
/// `signedOut` — the latter is unreachable in practice (the router redirects
/// away first) but is included defensively.
final Provider<bool> aiFeaturesAvailableProvider = Provider<bool>((Ref ref) {
  return ref.watch(authStatusProvider) == AuthStatus.active;
});
