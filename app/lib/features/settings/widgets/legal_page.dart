import 'package:flutter/material.dart';

/// The screen a Terms/Privacy link opens onto (AC-SET-04).
///
/// Pushed with a plain [MaterialPageRoute] rather than through `go_router`:
/// this is a static content leaf with nothing to deep-link to and no `extra`
/// to pass, and `lib/router/**` is another module's file — a real
/// destination doesn't require a route-table entry, just a real `Navigator`
/// push, which every `BuildContext` already supports.
///
/// **Placeholder copy.** No hosted Terms of Service / Privacy Policy text
/// exists anywhere in this repo yet (the RN app only ever showed a single
/// unlinked sentence — see `mobile/app/sign-in.tsx`). This renders a clearly
/// labelled stand-in so the *link* is real (tappable, navigates, shows
/// content) ahead of store submission, while flagging that the actual legal
/// copy — and, once it's hosted somewhere, an external `url_launcher` link
/// instead of this in-app page — is a required follow-up. `pubspec.yaml` is
/// orchestrator-owned (IMPLEMENTATION.md's module contract), so this wave
/// cannot add that dependency itself.
class LegalPage extends StatelessWidget {
  const LegalPage({super.key, required this.title, required this.body});

  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Text(body, style: Theme.of(context).textTheme.bodyLarge),
      ),
    );
  }
}

const String termsOfServicePlaceholder =
    'Placeholder copy — replace with Glean\'s finalised Terms of Service '
    'before store submission.\n\n'
    'By using Glean you agree to use the app for its intended purpose of '
    'planning meals, tracking pantry stock and generating shopping lists '
    'from your own data. Glean is provided as-is while in pre-launch '
    'development.';

const String privacyPolicyPlaceholder =
    'Placeholder copy — replace with Glean\'s finalised Privacy Policy '
    'before store submission.\n\n'
    'Your pantry, recipes, meal plan and shopping list are stored locally '
    'on your device. Photos you scan and text you describe are sent to '
    'Glean\'s backend only to extract structured data (ingredients, '
    'quantities) and are not retained beyond that request.';
