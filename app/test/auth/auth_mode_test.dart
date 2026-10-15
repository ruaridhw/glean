import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/auth_mode.dart';

void main() {
  group('isProductionApiBaseUrl', () {
    test('treats localhost and loopback hosts as non-production', () {
      expect(isProductionApiBaseUrl('http://localhost:8000'), isFalse);
      expect(isProductionApiBaseUrl('http://127.0.0.1:8000'), isFalse);
      // The Android emulator's alias for the host machine's localhost.
      expect(isProductionApiBaseUrl('http://10.0.2.2:8000'), isFalse);
    });

    test('treats a real deployed backend as production', () {
      expect(
        isProductionApiBaseUrl(
          'https://abc123.execute-api.eu-west-2.amazonaws.com',
        ),
        isTrue,
      );
    });

    test('fails safe for an unparseable base URL', () {
      expect(isProductionApiBaseUrl(''), isTrue);
      expect(isProductionApiBaseUrl('not a url'), isTrue);
    });
  });
}
