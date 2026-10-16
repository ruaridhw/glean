import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../auth/auth_controller.dart';
import '../../logging/logger_providers.dart';
import '../api_client.dart';

/// Every request through [apiClientProvider] is bounded by this.
const Duration apiRequestTimeout = Duration(seconds: 30);

/// The API base URL, e.g. `http://localhost:8000` locally or the deployed API Gateway URL.
///
/// No default: each entrypoint reads its own `--dart-define` and overrides this in its `ProviderScope`. An
/// unconfigured base URL is a programmer error caught at first use.
final Provider<String> apiBaseUrlProvider = Provider<String>((ref) {
  throw UnimplementedError(
    'apiBaseUrlProvider has no default — override it from main.dart / '
    'main_e2e.dart with the configured API base URL.',
  );
});

/// Supplies the bearer token for authenticated requests: the session's
/// [AuthController.getValidAccessToken], which refreshes an expired token
/// first. It resolves `null` with no usable session (signed out, expired,
/// or the e2e bypass); the request then goes out unauthenticated, the
/// backend rejects it, and [ApiAuthException] carries that to the UI.
final Provider<AccessTokenProvider> apiAccessTokenProvider =
    Provider<AccessTokenProvider>(
      (ref) => ref.watch(authControllerProvider.notifier).getValidAccessToken,
    );

/// The `http.Client` every request goes through. Production gets a real
/// client, closed when the provider is disposed; tests override this with a
/// mock so no test hits the network.
final Provider<http.Client> httpClientProvider = Provider<http.Client>((ref) {
  final client = http.Client();
  ref.onDispose(client.close);
  return client;
});

/// The typed HTTP client every provider in `lib/api/providers` builds on. Screens never construct
/// [GleanApiClient] directly; they go through providers.
final Provider<GleanApiClient> apiClientProvider = Provider<GleanApiClient>((
  ref,
) {
  return GleanApiClient(
    baseUrl: ref.watch(apiBaseUrlProvider),
    httpClient: ref.watch(httpClientProvider),
    accessTokenProvider: ref.watch(apiAccessTokenProvider),
    timeout: apiRequestTimeout,
    logger: ref.watch(gleanLoggerProvider),
  );
});
