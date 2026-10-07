import 'dart:async';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/api_client.dart';
import 'package:glean/api/api_exception.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  for (final status in [403, 429, 502]) {
    test(
      'HTTP $status has a recoverable typed error even without a JSON body',
      () async {
        final api = GleanApiClient(
          baseUrl: 'https://api.example.test',
          httpClient: MockClient(
            (_) async => http.Response('upstream failure', status),
          ),
        );
        await expectLater(
          api.searchRecipes(q: 'chicken'),
          status == 403
              ? throwsA(isA<ApiAuthException>())
              : throwsA(
                  isA<ApiServerException>().having(
                    (e) => e.statusCode,
                    'status',
                    status,
                  ),
                ),
        );
      },
    );
  }
  test(
    'scan token acquisition is bounded and a late token cannot send an abandoned scan',
    () async {
      final token = Completer<String?>();
      var requests = 0;
      final api = GleanApiClient(
        baseUrl: 'https://api.example.test',
        httpClient: MockClient((_) async {
          requests++;
          return http.Response('{"items":[]}', 200);
        }),
        accessTokenProvider: () => token.future,
        timeout: const Duration(milliseconds: 10),
      );
      await expectLater(
        api
            .scanReceipt(Uint8List.fromList([1, 2, 3]))
            .timeout(const Duration(milliseconds: 100)),
        throwsA(isA<ApiTimeoutException>()),
      );
      token.complete('late');
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(requests, 0);
    },
  );
}
