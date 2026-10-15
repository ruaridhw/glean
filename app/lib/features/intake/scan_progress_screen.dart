/// Submits the captured photo to `POST /receipts/scan` and lands on the
/// shared review screen, showing a real indeterminate indicator bound to the
/// request — see `widgets/scan_progress_body.dart`.
library;

import 'dart:async' show scheduleMicrotask;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/receipts.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/design_system/design_system.dart';
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
  Object? _error;

  @override
  void initState() {
    super.initState();
    scheduleMicrotask(_submit);
  }

  Future<void> _submit() async {
    if (!mounted) return;
    setState(() => _error = null);
    final ScanResponse response;
    try {
      response = await ref
          .read(apiClientProvider)
          .scanReceipt(widget.args.photoBytes);
    } catch (error) {
      if (!mounted || _navigated) return;
      ref.read(hapticsProvider).mediumImpact();
      setState(() => _error = error);
      return;
    }
    if (!mounted || _navigated) return;
    ref.read(hapticsProvider).mediumImpact();
    _onSuccess(response);
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
    _navigated = true;
    if (context.canPop()) {
      context.pop();
    } else {
      context.goNamed(
        widget.args.returnToShop ? AppRoutes.shop.name : AppRoutes.pantry.name,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final Object? error = _error;
    return Scaffold(
      appBar: AppBar(title: const Text('Reading receipt')),
      body: SafeArea(
        child: error == null
            ? ScanProgressBody(onCancel: _back)
            : ScanProgressError(
                message: _errorMessage(error),
                onRetry: _submit,
                onBack: _back,
              ),
      ),
    );
  }
}
