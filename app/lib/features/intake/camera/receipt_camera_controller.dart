/// The camera seam for the Scan screen.
///
/// `flutter test` runs headless with no camera hardware and no platform
/// channels registered for `package:camera`/`permission_handler`, so
/// `ScanScreen` never talks to those packages directly — it goes through
/// this interface, exactly the pattern `Haptics`/`hapticsProvider` already
/// establishes for the same reason. Production gets [SystemReceiptCamera];
/// widget tests substitute a fake that can simulate every permission state
/// and a capture failure without touching a real device (AC-TEST-16 notes
/// the *live* preview itself is integration-suite territory — this seam is
/// what makes the permission-state and capture-failure branches testable
/// here instead).
library;

import 'dart:typed_data';

import 'package:camera/camera.dart' as camera_pkg;
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart' as ph;

/// Camera permission state, collapsed from `permission_handler`'s richer
/// [ph.PermissionStatus] to the three branches the Scan screen actually
/// renders differently (AC-PAN-13): usable, recoverably denied (can
/// re-prompt), and permanently denied (must fall through to OS settings).
enum CameraPermissionState { granted, denied, permanentlyDenied }

/// Thrown by [ReceiptCameraController.capture] on any failure — a missing
/// controller, a platform exception, an empty frame. Never left uncaught
/// (AC-PAN-14: the RN app's `takePictureAsync` throwing was silent).
class ReceiptCaptureException implements Exception {
  const ReceiptCaptureException(this.message);

  final String message;

  @override
  String toString() => 'ReceiptCaptureException: $message';
}

/// Drives the Scan screen's camera permission and capture lifecycle. One
/// instance per screen visit — callers create it in `initState` and
/// [dispose] it in `dispose`.
abstract class ReceiptCameraController {
  /// Checks the current permission without prompting the user.
  Future<CameraPermissionState> checkPermission();

  /// Prompts the system permission dialog and returns the resulting state.
  Future<CameraPermissionState> requestPermission();

  /// Opens the OS app-settings screen — the only recovery path once a
  /// permission is permanently denied.
  Future<void> openAppSettings();

  /// Starts the live preview. Only valid to call once permission is
  /// [CameraPermissionState.granted].
  Future<void> initialize();

  /// The live camera preview widget, valid after [initialize] completes.
  Widget buildPreview();

  /// Captures a still frame as JPEG bytes, or throws
  /// [ReceiptCaptureException] on failure.
  Future<Uint8List> capture();

  Future<void> dispose();
}

/// Production implementation wrapping `package:camera` for the live preview
/// and `permission_handler` for permission state.
class SystemReceiptCamera implements ReceiptCameraController {
  camera_pkg.CameraController? _controller;

  @override
  Future<CameraPermissionState> checkPermission() async {
    return _fromStatus(await ph.Permission.camera.status);
  }

  @override
  Future<CameraPermissionState> requestPermission() async {
    return _fromStatus(await ph.Permission.camera.request());
  }

  @override
  Future<void> openAppSettings() async {
    await ph.openAppSettings();
  }

  CameraPermissionState _fromStatus(ph.PermissionStatus status) {
    if (status.isGranted || status.isLimited) {
      return CameraPermissionState.granted;
    }
    if (status.isPermanentlyDenied) {
      return CameraPermissionState.permanentlyDenied;
    }
    return CameraPermissionState.denied;
  }

  @override
  Future<void> initialize() async {
    final List<camera_pkg.CameraDescription> cameras = await camera_pkg
        .availableCameras();
    if (cameras.isEmpty) {
      throw const ReceiptCaptureException(
        'No camera available on this device.',
      );
    }
    final camera_pkg.CameraController controller = camera_pkg.CameraController(
      cameras.first,
      camera_pkg.ResolutionPreset.high,
      enableAudio: false,
    );
    await controller.initialize();
    _controller = controller;
  }

  @override
  Widget buildPreview() {
    final camera_pkg.CameraController? controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return const SizedBox.shrink();
    }
    return camera_pkg.CameraPreview(controller);
  }

  @override
  Future<Uint8List> capture() async {
    final camera_pkg.CameraController? controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      throw const ReceiptCaptureException('Camera is not ready.');
    }
    try {
      final camera_pkg.XFile file = await controller.takePicture();
      return await file.readAsBytes();
    } catch (error) {
      throw ReceiptCaptureException('Could not capture photo: $error');
    }
  }

  @override
  Future<void> dispose() async {
    await _controller?.dispose();
  }
}

/// DI seam: production code never overrides this. Widget tests inject a fake
/// factory via `ProviderScope(overrides: [...])`, mirroring `hapticsProvider`.
/// A factory (not a shared instance) because a controller is per-screen-visit
/// stateful — each `ScanScreen` creates and disposes its own.
typedef ReceiptCameraControllerFactory = ReceiptCameraController Function();
