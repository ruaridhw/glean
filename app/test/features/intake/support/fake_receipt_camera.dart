// A fake `ReceiptCameraController` for widget tests — no real camera or
// permission platform channel is registered under `flutter test`, so
// `ScanScreen` must never touch `package:camera`/`permission_handler`
// directly in a test. See `receipt_camera_controller.dart`'s doc comment.
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:glean/features/intake/camera/receipt_camera_controller.dart';

class FakeReceiptCameraController implements ReceiptCameraController {
  FakeReceiptCameraController({
    CameraPermissionState initialPermission = CameraPermissionState.granted,
    this.captureBytes,
    this.captureError,
  }) : permission = initialPermission;

  /// Mutable so a test can flip the state before calling
  /// `requestPermission()` (simulating the user granting/denying in the
  /// system dialog).
  CameraPermissionState permission;

  /// What `capture()` returns on success. Defaults to a tiny non-empty byte
  /// list so callers that just check "got some bytes" pass without fuss.
  Uint8List? captureBytes;

  /// When set, `capture()` throws this instead of returning [captureBytes].
  ReceiptCaptureException? captureError;

  bool initializeCalled = false;
  bool disposeCalled = false;
  int openAppSettingsCalls = 0;
  int requestPermissionCalls = 0;

  @override
  Future<CameraPermissionState> checkPermission() async => permission;

  @override
  Future<CameraPermissionState> requestPermission() async {
    requestPermissionCalls += 1;
    return permission;
  }

  @override
  Future<void> openAppSettings() async {
    openAppSettingsCalls += 1;
  }

  @override
  Future<void> initialize() async {
    initializeCalled = true;
  }

  @override
  Widget buildPreview() => const ColoredBox(color: Colors.black);

  @override
  Future<Uint8List> capture() async {
    final ReceiptCaptureException? error = captureError;
    if (error != null) throw error;
    return captureBytes ?? Uint8List.fromList(<int>[1, 2, 3]);
  }

  @override
  Future<void> dispose() async {
    disposeCalled = true;
  }
}
