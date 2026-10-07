import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod/misc.dart';
import '../api/providers/api_providers.dart';
import '../data/providers/database_providers.dart';
import '../features/settings/providers/sign_out_action.dart';
import '../router/auth_state.dart';
import 'auth_controller.dart';
import 'cognito_auth_client.dart';
import 'token_storage.dart';

/// The production bootstrap wiring, exercised directly in tests rather than
/// re-created inside their fixtures. This module has no e2e bypass import.
List<Override> sessionOverrides(
  AuthSessionSnapshot snapshot, {
  required TokenStorage storage,
  required CognitoAuthClient client,
}) => [
  authControllerProvider.overrideWith(
    () => AuthController.seeded(snapshot, storage: storage, client: client),
  ),
  authStatusProvider.overrideWith(
    () => SeededAuthStatusNotifier(snapshot.status),
  ),
  currentUserIdProvider.overrideWith((Ref ref) {
    final user = ref.watch(authControllerProvider).userId;
    if (user == null) {
      throw StateError('currentUserIdProvider read while signed out');
    }
    return user;
  }),
  apiAccessTokenProvider.overrideWith(
    (ref) => ref.watch(authControllerProvider.notifier).getValidAccessToken,
  ),
  signOutActionProvider.overrideWith(
    (ref) => ref.watch(authControllerProvider.notifier).signOut,
  ),
];
