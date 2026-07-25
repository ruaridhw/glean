import 'package:flutter/material.dart';

import '../../router/intake_params.dart';

/// Placeholder — the Pantry feature wave replaces this wholesale with the
/// real `camera` preview + shutter. Presented outside the tab shell (see
/// `router.dart`) so a mid-scan tab tap can no longer silently lose the
/// capture (AC-PAN-04) — there is no tab bar in the tree to tap.
class ScanScreen extends StatelessWidget {
  const ScanScreen({required this.args, super.key});

  final ScanArgs args;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan receipt')),
      body: const Center(child: Text('Scan receipt')),
    );
  }
}
