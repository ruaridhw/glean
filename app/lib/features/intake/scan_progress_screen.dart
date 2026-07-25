/// Submits the captured photo to `POST /receipts/scan` and lands on the
/// shared review screen (AC-PAN-05/06). Replaces the RN screen's three
/// fake time-based steps and ~2.3s artificial delay with a real
/// indeterminate indicator bound to the actual request — see
/// `widgets/scan_progress_body.dart`.
library;

import 'dart:async' show scheduleMicrotask;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/receipts.dart';
import 'package:glean/api/providers/receipts_providers.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

import 'widgets/scan_progress_body.dart';

class ScanProgressScreen extends ConsumerStatefulWidget {
  const ScanProgressScreen({required this.args, super.key});

  final ScanProgressArgs args;

  @override
  ConsumerState<ScanProgressScreen> createState() => _ScanProgressScreenState();
}

class _ScanProgressScreenState extends ConsumerState<ScanProgressScreen> {
  bool _navigated = false;

  @override
  void initState() {
    super.initState();
    // Riverpod forbids writing to a provider synchronously from `initState`
    // (it could observe an inconsistent UI mid-build) — deferred to a
    // microtask, which runs once this build phase finishes.
    scheduleMicrotask(_submit);
  }

  void _submit() {
    if (!mounted) return;
    ref
        .read(scanReceiptControllerProvider.notifier)
        .scan(widget.args.photoBytes);
  }

  void _onSuccess(ScanResponse response) {
    if (_navigated || !mounted) return;
    _navigated = true;
    final List<ReviewItemDraft> items = <ReviewItemDraft>[
      for (int i = 0; i < response.items.length; i++)
        ReviewItemDraft(
          reviewId: 'scan-$i',
          name: response.items[i].name,
          quantity: response.items[i].quantity,
          unit: response.items[i].unit,
          confidence: response.items[i].confidence,
          unitPrice: response.items[i].unitPrice,
          category: response.items[i].category,
        ),
    ];
    context.goNamed(
      AppRoutes.intakeReview.name,
      extra: ReviewArgs(
        destination: ReviewDestination.pantry,
        items: items,
        returnToShop: widget.args.returnToShop,
      ),
    );
  }

  String _errorMessage(Object error) {
    if (error is ApiTimeoutException) {
      return 'This is taking longer than expected. Check your connection '
          'and try again.';
    }
    return 'Could not process the receipt. Try again or add items manually.';
  }

  void _back() {
    if (context.canPop()) context.pop();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<AsyncValue<ScanResponse?>>(scanReceiptControllerProvider, (
      AsyncValue<ScanResponse?>? previous,
      AsyncValue<ScanResponse?> next,
    ) {
      final ScanResponse? response = next.value;
      if (response != null) _onSuccess(response);
    });

    final AsyncValue<ScanResponse?> async = ref.watch(
      scanReceiptControllerProvider,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Reading receipt')),
      body: SafeArea(
        child: async.when(
          data: (ScanResponse? _) => ScanProgressBody(onCancel: _back),
          loading: () => ScanProgressBody(onCancel: _back),
          error: (Object error, StackTrace _) => ScanProgressError(
            message: _errorMessage(error),
            onRetry: _submit,
            onBack: _back,
          ),
        ),
      ),
    );
  }
}
