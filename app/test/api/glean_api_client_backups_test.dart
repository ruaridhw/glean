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
    'listBackups asks for the signed-in user\'s backups and keeps the server order',
    () async {
      final GleanApiClient client = clientReturning(
        http.Response(
          jsonEncode(<String, Object?>{
            'backups': <Object?>[
              <String, Object?>{
                'id': 'db-exports/u/20260101T000000000000Z/',
                'created_at': '2026-01-01T00:00:00+00:00',
                'prepared': true,
                'label': 'ml to presence',
                'schema_version': 2,
                'size': 4096,
                'download_url': 'https://bucket.s3.amazonaws.com/a?sig=1',
              },
              <String, Object?>{
                'id': 'db-exports/u/20261015T120000000000Z/',
                'created_at': '2026-10-15T12:00:00+00:00',
                'prepared': false,
                'label': null,
                'schema_version': null,
                'size': 8192,
                'download_url': 'https://bucket.s3.amazonaws.com/b?sig=2',
              },
            ],
          }),
          200,
        ),
      );

      final backups = await client.listBackups();

      expect(seen.method, 'GET');
      expect(seen.url.path, '/dev/backups');
      expect(seen.url.query, isEmpty, reason: 'scope comes from the token');
      expect(seen.headers['Authorization'], 'Bearer test-token');
      expect(backups.map((b) => b.prepared), <bool>[true, false]);
      expect(backups.first.label, 'ml to presence');
      expect(backups.first.schemaVersion, 2);
      expect(backups.last.schemaVersion, isNull);
      expect(backups.last.createdAt, DateTime.utc(2026, 10, 15, 12));
    },
  );

  test(
    'downloadBackup fetches the signed URL without sending the Cognito token to S3',
    () async {
      final GleanApiClient client = clientReturning(
        http.Response.bytes(<int>[1, 2, 3], 200),
      );

      final Uint8List bytes = await client.downloadBackup(
        'https://bucket.s3.amazonaws.com/b?sig=2',
      );

      expect(bytes, <int>[1, 2, 3]);
      expect(seen.url.host, 'bucket.s3.amazonaws.com');
      expect(seen.headers.containsKey('Authorization'), isFalse);
    },
  );

  test('an expired download link surfaces as a typed ApiException', () async {
    final GleanApiClient client = clientReturning(
      http.Response('<Error>AccessDenied</Error>', 403),
    );

    await expectLater(
      client.downloadBackup('https://bucket.s3.amazonaws.com/b?sig=2'),
      throwsA(isA<ApiException>()),
    );
  });
}
