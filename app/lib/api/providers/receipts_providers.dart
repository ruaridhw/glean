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
/// rather than keeping stale state around for the next visit. That is a
/// *different* thing from disposing mid-network-call, which [scan] guards
/// against explicitly — see its doc comment (FINDINGS.md F-15).
class ScanReceiptController extends AsyncNotifier<ScanResponse?> {
  @override
  FutureOr<ScanResponse?> build() => null;

  /// Holds the provider alive for the duration of the request via
  /// [Ref.keepAlive]. Without this, a caller that only `ref.read`s this
  /// notifier (never watches it — the common case for a fire-and-forget
  /// command) leaves nothing keeping the provider alive while this method
  /// is suspended on the network `await`. `autoDispose` then tears it down
  /// *mid-flight*, and the `state = ...` assignment below throws using a
  /// disposed `Ref` — which the caller never sees, because it's thrown
  /// inside this notifier, not at the `await` call site. From the UI, that
  /// reads as the scan silently doing nothing: precisely the dead-end §11
  /// catalogues for RN's scan hanging forever on "Almost done…", except
  /// this one has no visible symptom at all. Closing the link once this
  /// method returns restores the normal drop-on-leave behaviour: if nobody
  /// is watching by then, disposal proceeds exactly as `autoDispose` intends.
  Future<void> scan(
    Uint8List imageBytes, {
    String filename = 'receipt.jpg',
  }) async {
    state = const AsyncLoading();
    final keepAliveLink = ref.keepAlive();
    try {
      final client = ref.read(apiClientProvider);
      state = await AsyncValue.guard(
        () => client.scanReceipt(imageBytes, filename: filename),
      );
    } finally {
      keepAliveLink.close();
    }
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

  /// See [ScanReceiptController.scan]'s doc comment for why the
  /// [Ref.keepAlive] hold-and-release is here (FINDINGS.md F-15).
  Future<void> describe(String text) async {
    state = const AsyncLoading();
    final keepAliveLink = ref.keepAlive();
    try {
      final client = ref.read(apiClientProvider);
      state = await AsyncValue.guard(() => client.describeReceipt(text));
    } finally {
      keepAliveLink.close();
    }
  }
}

final AsyncNotifierProvider<DescribeReceiptController, ScanResponse?>
describeReceiptControllerProvider = AsyncNotifierProvider.autoDispose(
  DescribeReceiptController.new,
);
