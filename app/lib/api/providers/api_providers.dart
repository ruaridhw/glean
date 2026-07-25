import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../api_client.dart';

/// Every request through [apiClientProvider] is bounded by this (AC-PAN-14).
const Duration apiRequestTimeout = Duration(seconds: 30);

/// The API base URL — e.g. `http://localhost:8000` locally, or the deployed
/// API Gateway URL for staging/prod.
///
/// **SEAM:** this has no default. `main.dart` and `main_e2e.dart` each read
/// their own `--dart-define` value and must override this provider in their
/// `ProviderScope`; the API module never reads `--dart-define` itself
/// (FLUTTER_MIGRATION.md §3 — "base URL is configuration, supplied by the
/// entrypoint"). An unconfigured base URL is a programmer error caught at
/// first use, not a runtime condition to handle gracefully.
final Provider<String> apiBaseUrlProvider = Provider<String>((ref) {
  throw UnimplementedError(
    'apiBaseUrlProvider has no default — override it from main.dart / '
    'main_e2e.dart with the configured API base URL.',
  );
});

/// Supplies the bearer token for authenticated requests.
///
/// **SEAM:** the AUTH module (`lib/auth/**`) owns tokens. This default
/// (always signed-out) keeps the API module independently testable without
/// importing `lib/auth/` — `lib/main.dart` overrides this provider with
/// [AuthController.getValidAccessToken] (see its `ProviderScope` overrides),
/// and `lib/main_e2e.dart` overrides it with the bypassed session's token
/// instead. This is not a placeholder bug — every route already 401s
/// cleanly without a token, and [ApiAuthException] carries that to the UI.
final Provider<AccessTokenProvider> apiAccessTokenProvider =
    Provider<AccessTokenProvider>((ref) {
      return () async => null;
    });

/// The `http.Client` every request goes through. Production gets a real
/// client, closed when the provider is disposed; tests override this with a
/// mock so no test hits the network.
final Provider<http.Client> httpClientProvider = Provider<http.Client>((ref) {
  final client = http.Client();
  ref.onDispose(client.close);
  return client;
});

/// The typed HTTP client every provider in `lib/api/providers` builds on.
///
/// AC-DATA-07: screens must never construct [GleanApiClient] or reach for
/// `lib/api` types directly — they go through providers built on this one.
final Provider<GleanApiClient> apiClientProvider = Provider<GleanApiClient>((
  ref,
) {
  return GleanApiClient(
    baseUrl: ref.watch(apiBaseUrlProvider),
    httpClient: ref.watch(httpClientProvider),
    accessTokenProvider: ref.watch(apiAccessTokenProvider),
    timeout: apiRequestTimeout,
  );
});
