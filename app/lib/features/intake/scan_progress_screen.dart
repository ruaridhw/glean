import 'package:flutter/material.dart';

import '../../router/intake_params.dart';

/// Placeholder — the Pantry feature wave replaces this wholesale with the
/// real indeterminate-progress + timeout + cancel UI (AC-PAN-06).
class ScanProgressScreen extends StatelessWidget {
  const ScanProgressScreen({required this.args, super.key});

  final ScanProgressArgs args;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reading receipt')),
      body: const Center(child: Text('Reading receipt')),
    );
  }
}
