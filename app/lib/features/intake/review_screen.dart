import 'package:flutter/material.dart';

import '../../router/intake_params.dart';

/// Placeholder — the Pantry/Shop feature waves replace this wholesale.
///
/// One review screen serves both pantry and shop intake (AC-PAN-05):
/// [ReviewArgs.destination] picks the verbs/behaviour, not a second route.
class ReviewScreen extends StatelessWidget {
  const ReviewScreen({required this.args, super.key});

  final ReviewArgs args;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Review items')),
      body: Center(child: Text('${args.items.length} items to review')),
    );
  }
}
