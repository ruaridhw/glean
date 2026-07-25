// Widget coverage for the receipt camera screen: permission denied/pending
// back affordances (AC-PAN-13), capture failure surfaced (AC-PAN-14), and
// the shutter haptic (AC-HAP-05) — all exercised through
// `FakeReceiptCameraController` since `flutter test` has no real camera or
// permission platform channel (see the controller's doc comment).
import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/intake/camera/receipt_camera_controller.dart';
import 'package:glean/features/intake/camera/receipt_camera_providers.dart';
import 'package:glean/features/intake/scan_screen.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';

import '../../support/harness.dart';
import 'support/fake_receipt_camera.dart';

void main() {
  group('ScanScreen', () {
    late AppTestHarness harness;
    late FakeReceiptCameraController camera;

    void setUpHarness(CameraPermissionState initialPermission) {
      camera = FakeReceiptCameraController(
        initialPermission: initialPermission,
      );
      harness = AppTestHarness(
        overrides: [
          receiptCameraFactoryProvider.overrideWithValue(() => camera),
        ],
      );
    }

    tearDown(() => harness.dispose());

    Future<void> pumpScan(WidgetTester tester) async {
      unawaited(
        harness.router.pushNamed(
          AppRoutes.intakeScan.name,
          extra: const ScanArgs(),
        ),
      );
      await tester.pumpWidget(harness.app());
      await tester.pumpAndSettle();
    }

    testWidgets('permission denied shows a working back affordance '
        '(AC-PAN-13)', (WidgetTester tester) async {
      setUpHarness(CameraPermissionState.denied);
      await pumpScan(tester);

      expect(
        find.text('Camera permission is needed to scan receipts.'),
        findsOneWidget,
      );
      expect(find.text('Grant permission'), findsOneWidget);

      await tester.tap(find.byIcon(Icons.arrow_back_rounded));
      await tester.pumpAndSettle();

      // Was pushed from the Pantry tab (a single push), so back returns
      // there — never a dead end, unlike the RN app's denied branch.
      expect(find.byType(ScanScreen), findsNothing);
    });

    testWidgets('permanently denied shows Open Settings and a back '
        'affordance (AC-PAN-13)', (WidgetTester tester) async {
      setUpHarness(CameraPermissionState.permanentlyDenied);
      await pumpScan(tester);

      expect(find.text('Open Settings'), findsOneWidget);
      await tester.tap(find.text('Open Settings'));
      await tester.pumpAndSettle();
      expect(camera.openAppSettingsCalls, 1);

      await tester.tap(find.byIcon(Icons.arrow_back_rounded));
      await tester.pumpAndSettle();
      expect(find.byType(ScanScreen), findsNothing);
    });

    testWidgets('granted: tapping the shutter fires a haptic and navigates '
        'to scan-progress with the captured bytes', (
      WidgetTester tester,
    ) async {
      setUpHarness(CameraPermissionState.granted);
      camera.captureBytes = Uint8List.fromList(<int>[9, 9, 9]);
      await pumpScan(tester);

      expect(camera.initializeCalled, isTrue);

      await tester.tap(
        find.byKey(const ValueKey<String>('scan-shutter')),
      ); // the shutter button
      await tester.pumpAndSettle();

      expect(harness.hapticCalls, contains(HapticWeight.light));
      expect(find.text('Reading receipt'), findsOneWidget);
    });

    testWidgets('a capture failure surfaces instead of hanging silently '
        '(AC-PAN-14)', (WidgetTester tester) async {
      setUpHarness(CameraPermissionState.granted);
      camera.captureError = const ReceiptCaptureException('boom');
      await pumpScan(tester);

      await tester.tap(find.byKey(const ValueKey<String>('scan-shutter')));
      await tester.pumpAndSettle();

      expect(
        find.text('Could not capture the photo. Try again.'),
        findsOneWidget,
      );
      // Never navigated away — the user is still on the camera and can retry.
      expect(find.byType(ScanScreen), findsOneWidget);
    });
  });
}
