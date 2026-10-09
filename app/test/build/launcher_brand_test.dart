import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final path in [
    'ios/Runner/Assets.xcassets/AppIcon.appiconset/Icon-App-1024x1024@1x.png',
    'android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png',
  ]) {
    test(
      '$path uses the green Glean launcher and retains its stroked stem',
      () async {
        final codec = await ui.instantiateImageCodec(
          await File(path).readAsBytes(),
        );
        final image = (await codec.getNextFrame()).image;
        final pixels = (await image.toByteData(
          format: ui.ImageByteFormat.rawRgba,
        ))!;
        List<int> at(double x, double y) {
          final offset =
              ((y * image.height).floor() * image.width +
                  (x * image.width).floor()) *
              4;
          return [for (var i = 0; i < 4; i++) pixels.getUint8(offset + i)];
        }

        // Background is green, not the stock Flutter icon's white/transparent.
        final background = at(0.1, 0.1);
        expect(background[1], greaterThan(background[0]));
        expect(background[1], greaterThan(background[2]));
        expect(background[3], 255);
        // The existing SVG's stem endpoint (752,482) is dark green rather
        // than the white leaf fill: catches stroke-dropping rasterizers (#90).
        final stem = at(752 / 1024, 482 / 1024);
        expect(stem[0], lessThan(40));
        expect(stem[1], inInclusiveRange(80, 160));
        expect(stem[2], lessThan(90));
        image.dispose();
        codec.dispose();
      },
    );
  }
}
