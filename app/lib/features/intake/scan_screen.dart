/// The receipt camera (FLUTTER_MIGRATION.md §6 Pantry). Reached from the
/// pantry `+` sheet or Shop's checkout bar (`args.returnToShop`); presented
/// outside the tab shell (`router.dart`) so a mid-scan tab tap can no longer
/// silently lose the capture (AC-PAN-04).
library;

import 'dart:async' show unawaited;
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

import 'camera/receipt_camera_controller.dart';
import 'camera/receipt_camera_providers.dart';
import 'widgets/camera_permission_prompt.dart';
import 'widgets/scan_back_button.dart';
import 'widgets/scan_overlay.dart';

enum _ScanPhase { checkingPermission, denied, permanentlyDenied, ready }

class ScanScreen extends ConsumerStatefulWidget {
  const ScanScreen({required this.args, super.key});

  final ScanArgs args;

  @override
  ConsumerState<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends ConsumerState<ScanScreen> {
  late final ReceiptCameraController _camera;
  _ScanPhase _phase = _ScanPhase.checkingPermission;
  bool _capturing = false;

  @override
  void initState() {
    super.initState();
    _camera = ref.read(receiptCameraFactoryProvider)();
    unawaited(_bootstrap());
  }

  Future<void> _bootstrap() async {
    final CameraPermissionState state = await _camera.checkPermission();
    await _applyPermission(state);
  }

  Future<void> _applyPermission(CameraPermissionState state) async {
    if (state == CameraPermissionState.granted) {
      await _camera.initialize();
      if (!mounted) return;
      setState(() => _phase = _ScanPhase.ready);
      return;
    }
    if (!mounted) return;
    setState(() {
      _phase = state == CameraPermissionState.permanentlyDenied
          ? _ScanPhase.permanentlyDenied
          : _ScanPhase.denied;
    });
  }

  Future<void> _requestPermission() async {
    final CameraPermissionState state = await _camera.requestPermission();
    await _applyPermission(state);
  }

  Future<void> _capture() async {
    if (_capturing) return;
    setState(() => _capturing = true);
    ref.read(hapticsProvider).lightImpact();
    try {
      final Uint8List bytes = await _camera.capture();
      if (!mounted) return;
      unawaited(
        context.pushNamed(
          AppRoutes.intakeScanProgress.name,
          extra: ScanProgressArgs(
            photoBytes: bytes,
            returnToShop: widget.args.returnToShop,
          ),
        ),
      );
    } on ReceiptCaptureException catch (_) {
      if (!mounted) return;
      GleanSnackBar.show(context, 'Could not capture the photo. Try again.');
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  void _exit() {
    if (context.canPop()) {
      context.pop();
      return;
    }
    context.goNamed(
      widget.args.returnToShop ? AppRoutes.shop.name : AppRoutes.pantry.name,
    );
  }

  @override
  void dispose() {
    unawaited(_camera.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF111511),
      body: Stack(
        fit: StackFit.expand,
        children: <Widget>[
          switch (_phase) {
            _ScanPhase.checkingPermission => const SizedBox.shrink(),
            _ScanPhase.ready => _camera.buildPreview(),
            _ScanPhase.denied ||
            _ScanPhase.permanentlyDenied => CameraPermissionPrompt(
              permanentlyDenied: _phase == _ScanPhase.permanentlyDenied,
              onRequestPermission: () => unawaited(_requestPermission()),
              onOpenSettings: () => unawaited(_camera.openAppSettings()),
            ),
          },
          if (_phase == _ScanPhase.ready)
            ScanOverlay(
              capturing: _capturing,
              onCapture: () => unawaited(_capture()),
            ),
          ScanBackButton(onPressed: _exit),
        ],
      ),
    );
  }
}
