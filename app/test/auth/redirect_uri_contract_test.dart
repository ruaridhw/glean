// AC-TEST-19: the redirect-URI cross-repo contract. `flutter test` always
// runs with the package root (`app/`) as the working directory, so
// `../backend/template.yaml` resolves regardless of which test file this is
// (mirrors mobile/tests/auth/redirect-uri.test.ts's equivalent check).
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/cognito_auth_client.dart';

void main() {
  test('redirectUri matches the CallbackURL backend/template.yaml declares for '
      'Cognito\'s app client', () {
    final String template = File('../backend/template.yaml').readAsStringSync();

    expect(CognitoAuthClient.redirectUri, 'glean://auth/callback');
    expect(template, contains('- ${CognitoAuthClient.redirectUri}'));
  });
}
