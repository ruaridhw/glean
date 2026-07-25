import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'receipt_camera_controller.dart';

/// Supplies a fresh [ReceiptCameraController] per screen visit. Defaults to
/// [SystemReceiptCamera]; widget tests override this with a factory that
/// returns a fake (see `test/features/intake/support/fake_receipt_camera.dart`).
final Provider<ReceiptCameraControllerFactory> receiptCameraFactoryProvider =
    Provider<ReceiptCameraControllerFactory>(
      (Ref ref) => SystemReceiptCamera.new,
    );
