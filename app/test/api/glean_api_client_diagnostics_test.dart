import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/api_client.dart';
import 'package:glean/api/api_exception.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  late http.Request seen;

  GleanApiClient clientReturning(http.Response response) => GleanApiClient(
    baseUrl: 'http://localhost:8000',
    httpClient: MockClient((http.Request request) async {
      seen = request;
      return response;
    }),
    accessTokenProvider: () async => 'test-token',
  );

  test(
    'exportDiagnostics posts the database and the log as two multipart files and returns the stored prefix',
    () async {
      final GleanApiClient client = clientReturning(
        http.Response(
          jsonEncode(<String, Object?>{
            'status': 'uploaded',
            'prefix': 'db-exports/user-1/20261015T120000000000Z/',
            'keys': <String, String>{},
          }),
          200,
        ),
      );

      final result = await client.exportDiagnostics(
        database: Uint8List.fromList(utf8.encode('SQLITE-BYTES')),
        log: Uint8List.fromList(utf8.encode('LOG-LINES')),
      );

      expect(result.prefix, 'db-exports/user-1/20261015T120000000000Z/');
      expect(seen.method, 'POST');
      expect(seen.url.path, '/dev/export-db');
      expect(seen.headers['Authorization'], 'Bearer test-token');
      expect(seen.headers['content-type'], startsWith('multipart/form-data'));
      expect(seen.body, contains('name="database"'));
      expect(seen.body, contains('SQLITE-BYTES'));
      expect(seen.body, contains('name="log"'));
      expect(seen.body, contains('LOG-LINES'));
    },
  );

  test('a rejected export surfaces as a typed ApiException', () async {
    final GleanApiClient client = clientReturning(
      http.Response(
        jsonEncode(<String, Object?>{'detail': 'Missing token'}),
        401,
      ),
    );

    await expectLater(
      client.exportDiagnostics(database: Uint8List(0), log: Uint8List(0)),
      throwsA(isA<ApiAuthException>()),
    );
  });
}
