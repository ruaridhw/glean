import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/api_client.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/logging/logging.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _NoPlatformLog implements PlatformLogSink {
  @override
  Future<void> write({
    required String level,
    required String tag,
    required String message,
  }) async {}
}

void main() {
  late Directory dir;
  late RotatingLogFile logFile;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('glean_api_log_test');
    logFile = RotatingLogFile(File('${dir.path}/glean.log'));
  });

  tearDown(() => dir.deleteSync(recursive: true));

  GleanApiClient clientReturning(http.Response response) => GleanApiClient(
    baseUrl: 'http://localhost:8000',
    httpClient: MockClient((_) async => response),
    accessTokenProvider: () async => 'live-access-token-9f8e7d',
    logger: GleanLogger(file: logFile, platform: _NoPlatformLog()),
  );

  test(
    'a response missing a required field is logged with the endpoint and the field name',
    () async {
      final GleanApiClient client = clientReturning(
        http.Response(
          jsonEncode(<String, Object?>{
            'results': <Object?>[
              <String, Object?>{'external_id': 'r1'}, // no title
            ],
          }),
          200,
        ),
      );

      await expectLater(
        client.searchRecipes(q: 'soup'),
        throwsA(isA<ApiParseException>()),
      );

      final String logged = logFile.readAll();
      expect(logged, contains('/recipes/search'));
      expect(logged, contains('title'));
    },
  );

  test(
    'a non-JSON body is logged as malformed without any of the body text',
    () async {
      final GleanApiClient client = clientReturning(
        http.Response(
          '<html>gateway says live-access-token-9f8e7d private-note</html>',
          200,
        ),
      );

      await expectLater(
        client.searchRecipes(),
        throwsA(isA<ApiParseException>()),
      );

      final String logged = logFile.readAll();
      expect(logged, contains('/recipes/search'));
      expect(logged, contains('not valid JSON'));
      expect(logged, isNot(contains('private-note')));
      expect(logged, isNot(contains('live-access-token')));
    },
  );

  test(
    'a server error is logged with status and endpoint, never the token or the body',
    () async {
      final GleanApiClient client = clientReturning(
        http.Response(
          jsonEncode(<String, Object?>{
            'detail': 'bad token live-access-token-9f8e7d',
          }),
          500,
        ),
      );

      await expectLater(
        client.getRecipe('r1'),
        throwsA(isA<ApiServerException>()),
      );

      final String logged = logFile.readAll();
      expect(logged, contains('/recipes/r1'));
      expect(logged, contains('HTTP 500'));
      expect(logged, isNot(contains('live-access-token')));
    },
  );
}
