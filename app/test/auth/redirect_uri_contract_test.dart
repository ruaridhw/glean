// AC-TEST-19: the redirect-URI cross-repo contract. `flutter test` always
// runs with the package root (`app/`) as the working directory, so
// `../backend/template.yaml` resolves regardless of which test file this is
// (mirrors the Expo app's tests/auth/redirect-uri.test.ts's equivalent
// check; see git history).
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

  // An empty taskAffinity puts MainActivity in a different task from the one
  // Chrome opens RedirectUriReceiverActivity in, so AppAuth never hands the
  // code back and sign-in silently stalls after Google (flutter_appauth README,
  // "No Redirect to app after login"; seen on the first Codemagic build).
  test('MainActivity keeps the default task affinity so the Cognito redirect '
      'returns to the waiting sign-in', () {
    final String manifest = File(
      'android/app/src/main/AndroidManifest.xml',
    ).readAsStringSync();
    final String mainActivity = RegExp(
      r'<activity\s[^>]*android:name="\.MainActivity"[^>]*>',
    ).firstMatch(manifest)![0]!;

    expect(mainActivity, isNot(contains('android:taskAffinity')));
  });
}
