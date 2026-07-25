import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/receipts.dart';
import 'api_providers.dart';

/// Command controller for `POST /receipts/scan`. Returns an ephemeral list
/// of parsed ingredients (AC-DATA-06) for the pantry/shop review screen;
/// nothing is written to drift until the user confirms there.
///
/// `autoDispose`: leaving the scan flow drops any in-flight/last result
/// rather than keeping stale state around for the next visit.
class ScanReceiptController extends AsyncNotifier<ScanResponse?> {
  @override
  FutureOr<ScanResponse?> build() => null;

  Future<void> scan(
    Uint8List imageBytes, {
    String filename = 'receipt.jpg',
  }) async {
    state = const AsyncLoading();
    final client = ref.read(apiClientProvider);
    state = await AsyncValue.guard(
      () => client.scanReceipt(imageBytes, filename: filename),
    );
  }
}

final AsyncNotifierProvider<ScanReceiptController, ScanResponse?>
scanReceiptControllerProvider = AsyncNotifierProvider.autoDispose(
  ScanReceiptController.new,
);

/// Command controller for `POST /receipts/describe`. Same ephemeral-result
/// shape as [ScanReceiptController]; the text-only sibling used by the
/// "describe what you bought" flow.
class DescribeReceiptController extends AsyncNotifier<ScanResponse?> {
  @override
  FutureOr<ScanResponse?> build() => null;

  Future<void> describe(String text) async {
    state = const AsyncLoading();
    final client = ref.read(apiClientProvider);
    state = await AsyncValue.guard(() => client.describeReceipt(text));
  }
}

final AsyncNotifierProvider<DescribeReceiptController, ScanResponse?>
describeReceiptControllerProvider = AsyncNotifierProvider.autoDispose(
  DescribeReceiptController.new,
);
