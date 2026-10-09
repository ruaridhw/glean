import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'tokens.dart';

/// Everything [TokenStorage] can read back — the raw, possibly-partial
/// strings backing a [CognitoTokens], plus the identity fields
/// ([userSub]/[email]) that survive a token-only clear (see
/// [TokenStorage.clearTokensKeepIdentity]).
class StoredTokenValues {
  const StoredTokenValues({
    this.accessToken,
    this.refreshToken,
    this.idToken,
    this.userSub,
    this.email,
    this.expiresAt,
  });

  final String? accessToken;
  final String? refreshToken;
  final String? idToken;
  final String? userSub;
  final String? email;
  final DateTime? expiresAt;
}

/// Token persistence — the Flutter analogue of the Expo app's
/// `src/auth/storage.ts`'s `SecureStore` wrapper (see git history).
///
/// An interface (not a set of static functions) so tests substitute
/// `InMemoryTokenStorage` (`test/auth/support/fakes.dart`) instead of
/// touching a real platform channel — `flutter_secure_storage` has no
/// in-memory test mode, the same reason `Haptics` is an interface rather
/// than a direct `HapticFeedback` call.
abstract class TokenStorage {
  Future<StoredTokenValues> readTokens();

  Future<void> saveTokens(CognitoTokens tokens);

  /// Clears **every** stored value, including identity (`userSub`/`email`).
  /// The only sign-out path (AC-AUTH-03): iOS Keychain items survive an
  /// uninstall/reinstall, so "reinstall == signed out" is never a valid
  /// assumption — this explicit clear is the sole mechanism.
  Future<void> clearAll();

  /// Clears the access/refresh/id tokens and their expiry, but **keeps**
  /// `userSub`/`email`. Used when a refresh fails: the session can no longer
  /// call AI-backed endpoints, but `currentUserIdProvider` must keep
  /// resolving so local reads stay unaffected (AC-AUTH-04) — this is what
  /// makes that possible at the storage layer.
  Future<void> clearTokensKeepIdentity();
}

/// Production [TokenStorage]: five ordinary key/value pairs in
/// `flutter_secure_storage` (iOS Keychain / Android Keystore-backed).
class SecureTokenStorage implements TokenStorage {
  SecureTokenStorage({FlutterSecureStorage? secureStorage})
    : _secureStorage = secureStorage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _secureStorage;

  static const String _keyAccess = 'glean_access_token';
  static const String _keyRefresh = 'glean_refresh_token';
  static const String _keyId = 'glean_id_token';
  static const String _keyExpiresAt = 'glean_token_expires_at';
  static const String _keyUserSub = 'glean_user_sub';
  static const String _keyEmail = 'glean_email';

  static const List<String> _tokenKeys = <String>[
    _keyAccess,
    _keyRefresh,
    _keyId,
    _keyExpiresAt,
  ];
  static const List<String> _identityKeys = <String>[_keyUserSub, _keyEmail];

  @override
  Future<StoredTokenValues> readTokens() async {
    final List<String?> values = await Future.wait<String?>(<Future<String?>>[
      _secureStorage.read(key: _keyAccess),
      _secureStorage.read(key: _keyRefresh),
      _secureStorage.read(key: _keyId),
      _secureStorage.read(key: _keyUserSub),
      _secureStorage.read(key: _keyEmail),
      _secureStorage.read(key: _keyExpiresAt),
    ]);
    final String? expiresAtRaw = values[5];
    return StoredTokenValues(
      accessToken: values[0],
      refreshToken: values[1],
      idToken: values[2],
      userSub: values[3],
      email: values[4],
      expiresAt: expiresAtRaw == null ? null : DateTime.tryParse(expiresAtRaw),
    );
  }

  @override
  Future<void> saveTokens(CognitoTokens tokens) async {
    await Future.wait<void>(<Future<void>>[
      _secureStorage.write(key: _keyAccess, value: tokens.accessToken),
      _secureStorage.write(key: _keyRefresh, value: tokens.refreshToken),
      _secureStorage.write(key: _keyId, value: tokens.idToken),
      _secureStorage.write(key: _keyUserSub, value: tokens.userSub),
      _secureStorage.write(key: _keyEmail, value: tokens.email),
      _secureStorage.write(
        key: _keyExpiresAt,
        value: tokens.expiresAt.toIso8601String(),
      ),
    ]);
  }

  @override
  Future<void> clearAll() =>
      _deleteKeys(<String>[..._tokenKeys, ..._identityKeys]);

  @override
  Future<void> clearTokensKeepIdentity() => _deleteKeys(_tokenKeys);

  Future<void> _deleteKeys(List<String> keys) async {
    await Future.wait<void>(
      keys.map((String key) => _secureStorage.delete(key: key)),
    );
  }
}
