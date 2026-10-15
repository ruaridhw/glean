import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:xml/xml.dart';

void main() {
  test(
    'the main Android manifest grants release networking and connectivity observation',
    () {
      final manifest = XmlDocument.parse(
        File('android/app/src/main/AndroidManifest.xml').readAsStringSync(),
      );
      final permissions = manifest
          .findAllElements('uses-permission')
          .map(
            (node) => node.getAttribute(
              'name',
              namespaceUri: 'http://schemas.android.com/apk/res/android',
            ),
          )
          .toSet();
      expect(
        permissions,
        containsAll([
          'android.permission.INTERNET',
          'android.permission.ACCESS_NETWORK_STATE',
        ]),
      );
    },
  );
}
