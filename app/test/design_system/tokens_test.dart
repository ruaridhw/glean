import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

void main() {
  test('lerp interpolates colours and tolerates an unrelated extension', () {
    const a = AppTokens.standard;
    final b = a.copyWith(ink: Colors.black);
    expect(a.lerp(b, 0.5).ink, Color.lerp(a.ink, b.ink, 0.5));
    expect(a.lerp(null, 0.5), same(a));
  });
}
