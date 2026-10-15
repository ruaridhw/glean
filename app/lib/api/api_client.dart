import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart' show MediaType;

import 'api_exception.dart';
import 'models/meal_plan.dart';
import 'models/receipts.dart';
import 'models/recipes.dart';
import 'models/shopping.dart';
import 'text_input.dart';

/// Supplies the current user's bearer token, or `null` if signed out. Injected rather than read from token
/// storage, so the client stays testable and independent of `lib/auth/`.
typedef AccessTokenProvider = Future<String?> Function();

/// Typed HTTP client for the Glean FastAPI backend, which holds no user state. Every method returns an
/// ephemeral proposal (a DTO) for the caller to review and persist; nothing here writes to a database.
/// [baseUrl] is passed in: the entrypoint owns which backend a build talks to.
class GleanApiClient {
  GleanApiClient({
    required this.baseUrl,
    required this.httpClient,
    AccessTokenProvider? accessTokenProvider,
    this.timeout = const Duration(seconds: 30),
  }) : _accessTokenProvider = accessTokenProvider ?? _noAccessToken;

  /// e.g. `http://localhost:8000` locally, or the deployed API Gateway URL.
  final String baseUrl;

  /// Every request is bounded by this, so a stalled LLM call can't hang a screen forever.
  final Duration timeout;

  final http.Client httpClient;
  final AccessTokenProvider _accessTokenProvider;

  static Future<String?> _noAccessToken() async => null;

  // --- Recipes ---

  Future<RecipeSearchResponse> searchRecipes({String? q}) {
    final uri = _uri('/recipes/search', {
      if (q != null && q.isNotEmpty) 'q': q,
    });
    return _send(
      uri,
      () async => httpClient.get(uri, headers: await _authHeaders()),
      (dynamic json) =>
          RecipeSearchResponse.fromJson(json as Map<String, dynamic>),
    );
  }

  Future<RecipeOut> getRecipe(String recipeId) {
    final uri = _uri('/recipes/${Uri.encodeComponent(recipeId)}');
    return _send(
      uri,
      () async => httpClient.get(uri, headers: await _authHeaders()),
      (dynamic json) => RecipeOut.fromJson(json as Map<String, dynamic>),
    );
  }

  Future<RecipeOut> importRecipeFromUrl(ImportUrlRequest request) {
    final uri = _uri('/recipes/import-url');
    return _send(
      uri,
      () async => httpClient.post(
        uri,
        headers: await _jsonHeaders(),
        body: jsonEncode(request.toJson()),
      ),
      (dynamic json) => RecipeOut.fromJson(json as Map<String, dynamic>),
    );
  }

  // --- Meal plan ---

  Future<MealPlanResponse> generateMealPlan(MealPlanRequest request) {
    final uri = _uri('/meal-plan');
    return _send(
      uri,
      () async => httpClient.post(
        uri,
        headers: await _jsonHeaders(),
        body: jsonEncode(request.toJson()),
      ),
      (dynamic json) => MealPlanResponse.fromJson(json as Map<String, dynamic>),
    );
  }

  // --- Receipts ---

  Future<ScanResponse> scanReceipt(
    Uint8List imageBytes, {
    String filename = 'receipt.jpg',
  }) {
    final uri = _uri('/receipts/scan');
    return _send(uri, () async {
      final request = http.MultipartRequest('POST', uri)
        ..headers.addAll(await _authHeaders())
        ..files.add(
          http.MultipartFile.fromBytes(
            'file',
            imageBytes,
            filename: filename,
            contentType: MediaType('image', 'jpeg'),
          ),
        );
      return http.Response.fromStream(await httpClient.send(request));
    }, (dynamic json) => ScanResponse.fromJson(json as Map<String, dynamic>));
  }

  Future<ScanResponse> describeReceipt(String text) {
    final body = DescribeRequest(text: requireSubmittedText(text));
    final uri = _uri('/receipts/describe');
    return _send(
      uri,
      () async => httpClient.post(
        uri,
        headers: await _jsonHeaders(),
        body: jsonEncode(body.toJson()),
      ),
      (dynamic json) => ScanResponse.fromJson(json as Map<String, dynamic>),
    );
  }

  // --- Shopping ---

  Future<ShoppingParseResponse> parseShoppingDescription(String text) {
    final body = ShoppingParseRequest(text: requireSubmittedText(text));
    final uri = _uri('/shopping/parse-description');
    return _send(
      uri,
      () async => httpClient.post(
        uri,
        headers: await _jsonHeaders(),
        body: jsonEncode(body.toJson()),
      ),
      (dynamic json) =>
          ShoppingParseResponse.fromJson(json as Map<String, dynamic>),
    );
  }

  // --- Internals ---

  Uri _uri(String path, [Map<String, String>? query]) {
    final uri = Uri.parse('$baseUrl$path');
    if (query == null || query.isEmpty) return uri;
    return uri.replace(queryParameters: query);
  }

  Future<Map<String, String>> _authHeaders() async {
    final token = await _accessTokenProvider().timeout(
      timeout,
      onTimeout: () => throw const ApiTimeoutException('authentication'),
    );
    return {
      if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
    };
  }

  Future<Map<String, String>> _jsonHeaders() async => {
    ...await _authHeaders(),
    'Content-Type': 'application/json',
  };

  /// Runs [send], applying shared timeout/network/decode handling. Everything thrown is an [ApiException]
  /// subtype, so a caller can tell "signed out" from "timed out" from "server rejected it".
  Future<T> _send<T>(
    Uri uri,
    Future<http.Response> Function() send,
    T Function(dynamic json) decode,
  ) async {
    http.Response response;
    try {
      response = await send().timeout(timeout);
    } on TimeoutException {
      throw ApiTimeoutException(uri.path);
    } on ApiException {
      rethrow;
    } catch (error) {
      // Anything else — SocketException, http.ClientException, a DNS
      // failure — is "couldn't reach the server", not a bug in this client.
      throw ApiNetworkException(error.toString());
    }
    return _decode(response, decode);
  }

  T _decode<T>(http.Response response, T Function(dynamic json) decode) {
    final status = response.statusCode;
    if (status == 401 || status == 403) {
      throw ApiAuthException(
        statusCode: status,
        message: _detailMessage(response) ?? 'Authentication failed',
      );
    }
    if (status == 429) {
      throw ApiRateLimitException(
        _detailMessage(response) ?? 'Too many requests',
      );
    }
    if (status == 422) {
      throw ApiValidationException(
        message: _detailMessage(response) ?? 'Validation failed',
        detail: _detail(response),
      );
    }
    if (status < 200 || status >= 300) {
      throw ApiServerException(
        statusCode: status,
        message:
            _detailMessage(response) ?? 'Request failed with status $status',
      );
    }
    try {
      final dynamic json = response.body.isEmpty
          ? null
          : jsonDecode(response.body);
      return decode(json);
    } on ApiException {
      rethrow;
    } catch (error) {
      throw ApiParseException('Could not parse response body: $error');
    }
  }

  dynamic _detail(http.Response response) {
    try {
      final dynamic body = jsonDecode(response.body);
      if (body is Map<String, dynamic>) return body['detail'];
    } catch (_) {
      // Not JSON (or empty) — no detail to extract.
    }
    return null;
  }

  String? _detailMessage(http.Response response) {
    final detail = _detail(response);
    if (detail is String) return detail;
    if (detail is List) {
      return detail
          .map((entry) => entry is Map ? entry['msg'] ?? entry : entry)
          .join('; ');
    }
    return null;
  }
}
