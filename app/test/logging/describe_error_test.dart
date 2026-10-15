import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/api_client.dart';
import 'package:glean/logging/logging.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const String _body =
    '<html>refresh_token=opaque-secret-123 private-receipt-note</html>';

Future<Object> _errorFrom(http.Response response) async {
  final GleanApiClient client = GleanApiClient(
    baseUrl: 'http://localhost:8000',
    httpClient: MockClient((_) async => response),
  );
  try {
    await client.searchRecipes();
  } catch (error) {
    return error;
  }
  fail('expected the request to fail');
}

void main() {
  group('describeError', () {
    test(
      'a response that cannot be decoded is described without its body or any token in it',
      () async {
        final Object error = await _errorFrom(http.Response(_body, 200));

        final String described = describeError(error);

        expect(described, startsWith('ApiParseException'));
        expect(described, isNot(contains('private-receipt-note')));
        expect(described, isNot(contains('opaque-secret-123')));
        expect(described, isNot(contains('<html>')));
      },
    );

    test('a decode failure names the field but not the values', () async {
      final Object error = await _errorFrom(
        http.Response('{"results": [{"external_id": "secret-value-77"}]}', 200),
      );

      final String described = describeError(error);

      expect(described, contains('title'));
      expect(described, isNot(contains('secret-value-77')));
    });

    test(
      'a server error is described by type and status, not its detail',
      () async {
        final Object error = await _errorFrom(
          http.Response('{"detail": "token opaque-secret-123 rejected"}', 500),
        );

        final String described = describeError(error);

        expect(described, contains('ApiServerException'));
        expect(described, contains('500'));
        expect(described, isNot(contains('opaque-secret-123')));
      },
    );

    test(
      'a FormatException is described without the source text it carries',
      () {
        final String described = describeError(
          const FormatException('bad input', _body, 0),
        );

        expect(described, contains('FormatException'));
        expect(described, isNot(contains('private-receipt-note')));
      },
    );

    test('any other error keeps its type and a short redacted message', () {
      final String described = describeError(
        StateError(
          'upload refused with token=abcdef0123456789abcdef0123456789',
        ),
      );

      expect(described, contains('StateError'));
      expect(described, contains('upload refused'));
      expect(described, isNot(contains('abcdef0123456789abcdef0123456789')));
    });

    test('a very long message is cut to a bounded length', () {
      expect(describeError(StateError('word ' * 5000)).length, lessThan(400));
    });
  });

  group('redactSecrets', () {
    test('hides the value of a named credential, however opaque', () {
      for (final String text in <String>[
        'refresh_token=opaque-secret-123',
        'id_token: opaque-secret-123',
        '"access_token":"opaque-secret-123"',
        'password=opaque-secret-123',
        'client_secret=opaque-secret-123',
        'Authorization: Basic opaque-secret-123',
      ]) {
        expect(
          redactSecrets(text),
          isNot(contains('opaque-secret-123')),
          reason: text,
        );
      }
    });

    test('hides long hex and base64 runs that are not named', () {
      const String hex =
          '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08';
      const String b64 = 'dGhpcyBpcyBhbiBvcGFxdWUgc2VjcmV0IHZhbHVlIQ==';

      expect(redactSecrets('digest $hex end'), isNot(contains(hex)));
      expect(redactSecrets('blob $b64 end'), isNot(contains(b64)));
    });

    test('leaves ordinary log text alone', () {
      const String line =
          '/recipes/search response could not be decoded: field "title" is missing or invalid';

      expect(redactSecrets(line), line);
    });
  });
}
