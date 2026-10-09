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

/// Token persistence: six key/value pairs in `flutter_secure_storage`
/// (iOS Keychain / Android Keystore). Tests run it for real over
/// `FlutterSecureStorage.setMockInitialValues`.
class TokenStorage {
  TokenStorage({FlutterSecureStorage? secureStorage})
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

  /// Clears **every** stored value, including identity (`userSub`/`email`).
  /// The only sign-out path: iOS Keychain items survive an
  /// uninstall/reinstall, so "reinstall == signed out" is never a valid
  /// assumption — this explicit clear is the sole mechanism.
  Future<void> clearAll() =>
      _deleteKeys(<String>[..._tokenKeys, ..._identityKeys]);

  /// Clears the access/refresh/id tokens and their expiry, but **keeps**
  /// `userSub`/`email`. Used when a refresh fails: the session can no longer
  /// call AI-backed endpoints, but `currentUserIdProvider` must keep
  /// resolving so local reads stay unaffected.
  Future<void> clearTokensKeepIdentity() => _deleteKeys(_tokenKeys);

  Future<void> _deleteKeys(List<String> keys) async {
    await Future.wait<void>(
      keys.map((String key) => _secureStorage.delete(key: key)),
    );
  }
}
