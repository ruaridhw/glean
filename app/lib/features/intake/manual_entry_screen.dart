import 'package:flutter/material.dart';

/// Placeholder — the Pantry feature wave replaces this wholesale. Manual
/// entry is reachable from the `+` sheet whether the pantry is empty or full
/// (AC-PAN-03) — the RN app only reached this screen via dead code.
class ManualEntryScreen extends StatelessWidget {
  const ManualEntryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add item')),
      body: const Center(child: Text('Add item')),
    );
  }
}
