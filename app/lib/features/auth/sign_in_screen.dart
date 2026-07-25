import 'package:flutter/material.dart';

/// Placeholder — the AUTH wave replaces this wholesale with the real
/// Google-via-Cognito sign-in screen (FLUTTER_MIGRATION.md §5).
class SignInScreen extends StatelessWidget {
  const SignInScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Sign in')),
      body: const Center(child: Text('Sign in')),
    );
  }
}
