import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../router/auth_state.dart';
import 'auth_mode.dart';
import 'cognito_auth_client.dart';
import 'token_storage.dart';
import 'tokens.dart';

/// What AUTH currently believes about the signed-in user. Immutable so
/// `==`/tests can compare snapshots directly.
@immutable
class AuthSessionSnapshot {
  const AuthSessionSnapshot({required this.status, this.userId, this.tokens});

  final AuthStatus status;

  /// The stable Cognito `sub` — non-null whenever [status] is `active` or
  /// `expired` (AC-AUTH-04: expiry must still resolve a user id so local
  /// reads keep working). Only `null` when `signedOut`.
  final String? userId;

  /// Non-null only while `active`. A failed refresh clears this (moving to
  /// `expired`) without touching [userId] — see [AuthController.getValidAccessToken].
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

/// Seeds `lib/router/auth_state.dart`'s [authStatusProvider] from a value
/// computed *before* the widget tree exists — see this file's top doc
/// comment for why that matters. Everything else — the public [setStatus]
/// setter [AuthController] drives afterwards — is inherited unchanged from
/// [AuthStatusNotifier].
class SeededAuthStatusNotifier extends AuthStatusNotifier {
  SeededAuthStatusNotifier(this._seed);

  final AuthStatus _seed;

  @override
  AuthStatus build() => _seed;
}

/// Owns the signed-in session end to end: Cognito sign-in/refresh/sign-out,
/// secure-storage persistence, and keeping the router's [authStatusProvider]
/// synchronized. The `currentUserIdProvider` and `apiAccessTokenProvider`
/// seams (owned by the data/API modules) are thin overrides built on top of
/// this controller — see the wiring doc comment below for the exact
/// `ProviderScope` overrides `main.dart`/`main_e2e.dart` must install.
///
/// **Why this doesn't just override `authStatusProvider`/`currentUserIdProvider`
/// with plain provider expressions**: those two providers must resolve
/// *synchronously* the instant anything reads them — `currentUserIdProvider`
/// is a plain (non-async) `Provider<String>` that every data-layer repository
/// provider depends on, so there must be no "still checking secure storage"
/// state for it to be in by the time the first frame builds. Rather than
/// modelling that as a `FutureProvider`-gated loading screen, the one-time
/// async secure-storage read happens **before** `runApp` (see
/// [loadInitialAuthSnapshot]), and its result seeds both this controller and
/// [SeededAuthStatusNotifier] so every seam is already synchronously correct
/// on the very first read. Sign-in/refresh/sign-out afterwards are ordinary
/// synchronous state transitions on an already-built provider graph.
///
/// ---
///
/// ### Required wiring (for `main.dart`; not part of this module's contract)
///
/// A `List<Override>` literal can't be given an explicit type in this
/// codebase today — `Override` isn't re-exported by `flutter_riverpod`
/// 3.3.2's public surface, and importing it from `package:riverpod` directly
/// would need a direct pubspec dependency this module doesn't own (see
/// `.scratch/flutter-port/FINDINGS.md` F-03). So the list must be written
/// inline, where Dart infers its element type from `ProviderScope`'s
/// parameter type instead of it being spelled out. `main.dart` should read:
///
/// ```dart
/// final storage = SecureTokenStorage();
/// final client = CognitoAuthClient(cognitoDomain: ..., clientId: ...);
/// final snapshot = await loadInitialAuthSnapshot(storage);
///
/// runApp(ProviderScope(
///   overrides: [
///     authControllerProvider.overrideWith(
///       () => AuthController.seeded(snapshot, storage: storage, client: client),
///     ),
///     authStatusProvider.overrideWith(() => SeededAuthStatusNotifier(snapshot.status)),
///     currentUserIdProvider.overrideWith((ref) {
///       final userId = ref.watch(authControllerProvider).userId;
///       if (userId == null) throw StateError('read while signed out');
///       return userId;
///     }),
///     apiAccessTokenProvider.overrideWith(
///       (ref) => ref.watch(authControllerProvider.notifier).getValidAccessToken,
///     ),
///     // Settings' seam (lib/features/settings/providers/sign_out_action.dart)
///     // — its own doc comment names this as a required AUTH follow-up.
///     signOutActionProvider.overrideWith(
///       (ref) => ref.watch(authControllerProvider.notifier).signOut,
///     ),
///   ],
///   child: const GleanApp(),
/// ));
/// ```
///
/// `main_e2e.dart`'s equivalent uses `lib/auth/auth_bypass.dart`'s pieces
/// instead of a loaded snapshot/real client — see that file's doc comment.
/// `test/auth/auth_wiring_test.dart` exercises this exact literal shape
/// end-to-end so a change to any of these four seams' identities is caught
/// even though no test can execute `main.dart` itself.
class AuthController extends Notifier<AuthSessionSnapshot> {
  AuthController() : this.seeded(AuthSessionSnapshot.signedOut);

  /// Production bootstrap and tests both go through this: seed with a
  /// precomputed [AuthSessionSnapshot] (real, from [loadInitialAuthSnapshot];
  /// fixed, in a test) plus the collaborators that back [signIn]/[signOut]/
  /// [getValidAccessToken]. The no-argument default constructor above (what
  /// `NotifierProvider(AuthController.new)` uses before anything overrides
  /// it) has no usable collaborators — calling a mutating method on it is a
  /// wiring bug and throws loudly rather than silently no-op-ing.
  AuthController.seeded(
    this._seed, {
    TokenStorage? storage,
    CognitoAuthClient? client,
  }) {
    // Plain body assignment (not an initializer-list `this.x` shorthand):
    // the external parameter names (`storage`/`client`) deliberately don't
    // match the private field names, so `prefer_initializing_formals`
    // doesn't apply — see the fields' own doc comment.
    _storage = storage;
    _client = client;
  }

  final AuthSessionSnapshot _seed;

  /// `late final` rather than initializer-list-assigned: assigning these in
  /// [AuthController.seeded]'s constructor *body* (not its initializer
  /// list) is what keeps the named parameters `storage`/`client` — matching
  /// this class's own doc comment and every call site — rather than being
  /// forced into `_storage`/`_client` labels a caller would have to spell
  /// with a leading underscore.
  late final TokenStorage? _storage;
  late final CognitoAuthClient? _client;

  TokenStorage get _requireStorage =>
      _storage ??
      (throw UnimplementedError(
        'AuthController has no TokenStorage — construct it via '
        'AuthController.seeded(..., storage: ...) rather than the bare '
        'default constructor.',
      ));

  CognitoAuthClient get _requireClient =>
      _client ??
      (throw UnimplementedError(
        'AuthController has no CognitoAuthClient — construct it via '
        'AuthController.seeded(..., client: ...) rather than the bare '
        'default constructor.',
      ));

  @override
  AuthSessionSnapshot build() => _seed;

  void _publish(AuthSessionSnapshot next) {
    state = next;
    // The hook `lib/router/auth_state.dart`'s own doc comment anticipated:
    // "AUTH will call the real equivalent of this after sign-in/out/refresh"
    // — driving the existing setter, not overriding the notifier a second
    // time, so the router's redirect listener reacts immediately regardless
    // of whether `authStatusProvider` was itself overridden with
    // [SeededAuthStatusNotifier] or left at its built-in default.
    ref.read(authStatusProvider.notifier).setStatus(next.status);
  }

  /// AC-AUTH-08: awaits and consumes [CognitoAuthClient.signIn]'s return
  /// value directly — see that method's doc comment for the RN bug this
  /// avoids reproducing.
  ///
  /// Does **not** fire a haptic itself — `SignInScreen` fires both the tap
  /// acknowledgement and the success commit, mirroring how
  /// `SettingsScreen._handleSignOut` fires sign-out's haptic after awaiting
  /// `signOutActionProvider()` rather than the action itself firing one
  /// (avoids the double-buzz bug, AC-HAP-03).
  Future<void> signIn() async {
    final CognitoTokens tokens = await _requireClient.signIn();
    await _requireStorage.saveTokens(tokens);
    _publish(
      AuthSessionSnapshot(
        status: AuthStatus.active,
        userId: tokens.userSub,
        tokens: tokens,
      ),
    );
  }

  /// AC-AUTH-03: clears every stored value explicitly. iOS Keychain items
  /// survive an app uninstall/reinstall, so this explicit clear — not
  /// "reinstall == signed out" — is the only reliable sign-out. Deliberately
  /// does not touch any drift table (AC-DATA-09): a different user simply
  /// sees their own (empty) data next time.
  ///
  /// This is what `lib/features/settings/providers/sign_out_action.dart`'s
  /// `signOutActionProvider` must be overridden with — see this class's top
  /// doc comment for the exact override.
  Future<void> signOut() async {
    await _requireStorage.clearAll();
    _publish(AuthSessionSnapshot.signedOut);
  }

  /// The `apiAccessTokenProvider` seam's implementation: returns a
  /// currently-valid access token, refreshing first if the cached one has
  /// expired. Returns `null` if there is no session, or if a refresh attempt
  /// fails — never a token known to be invalid.
  Future<String?> getValidAccessToken() async {
    final AuthSessionSnapshot snapshot = state;
    final CognitoTokens? tokens = snapshot.tokens;
    if (tokens == null) return null;
    if (!tokens.isExpired) return tokens.accessToken;

    final CognitoTokens? refreshed = await _requireClient.refresh(
      tokens.refreshToken,
    );
    if (refreshed == null) {
      // AC-AUTH-05: never write a partial/empty token, and never leave
      // storage disagreeing with "no longer authenticated". AC-AUTH-04:
      // keep the user id — local reads must keep working.
      await _requireStorage.clearTokensKeepIdentity();
      _publish(
        AuthSessionSnapshot(
          status: AuthStatus.expired,
          userId: snapshot.userId,
        ),
      );
      return null;
    }

    await _requireStorage.saveTokens(refreshed);
    _publish(
      AuthSessionSnapshot(
        status: AuthStatus.active,
        userId: refreshed.userSub,
        tokens: refreshed,
      ),
    );
    return refreshed.accessToken;
  }
}

final NotifierProvider<AuthController, AuthSessionSnapshot>
authControllerProvider = NotifierProvider<AuthController, AuthSessionSnapshot>(
  AuthController.new,
);

/// Reads local secure storage once to compute the [AuthSessionSnapshot]
/// `main.dart`/`main_e2e.dart` must seed [AuthController.seeded] and
/// [SeededAuthStatusNotifier] with, **before** `runApp` — see
/// [AuthController]'s top doc comment for why.
///
/// Reuses [resolveAuthSession] (mobile's ported `mode.ts` logic) for the
/// "is there a usable access token" decision, so cold-start hydration and
/// the pure unit-tested predicate can never disagree.
Future<AuthSessionSnapshot> loadInitialAuthSnapshot(
  TokenStorage storage,
) async {
  final StoredTokenValues stored = await storage.readTokens();
  final AuthSession resolved = resolveAuthSession(
    stored: StoredAuthValues(
      accessToken: stored.accessToken,
      refreshToken: stored.refreshToken,
      userSub: stored.userSub,
    ),
  );

  if (!resolved.authenticated) return AuthSessionSnapshot.signedOut;

  // A record with *some* access token but a missing id token, refresh
  // token, expiry, or user sub is corrupt/partial (should not happen via
  // this module's own writes, but storage is external state) — degrade to
  // signed out rather than construct unusable tokens.
  if (stored.idToken == null ||
      stored.refreshToken == null ||
      stored.userSub == null ||
      stored.expiresAt == null) {
    return AuthSessionSnapshot.signedOut;
  }

  final CognitoTokens tokens = CognitoTokens(
    accessToken: stored.accessToken!,
    refreshToken: stored.refreshToken!,
    idToken: stored.idToken!,
    userSub: stored.userSub!,
    email: stored.email ?? '',
    expiresAt: stored.expiresAt!,
  );
  return AuthSessionSnapshot(
    status: AuthStatus.active,
    userId: tokens.userSub,
    tokens: tokens,
  );
}

/// "Are AI-backed features usable right now?" — the predicate other feature
/// modules (Meals/Plan/Pantry) should gate Scan/Describe/Import/Generate on,
/// instead of re-deriving it from [authStatusProvider] themselves. `false`
/// for both `expired` and `signedOut` — the latter is unreachable in
/// practice (the router redirects away first) but is included defensively.
final Provider<bool> aiFeaturesAvailableProvider = Provider<bool>((Ref ref) {
  return ref.watch(authStatusProvider) == AuthStatus.active;
});
