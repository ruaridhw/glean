/// The single `integration_test` suite (FLUTTER_MIGRATION.md §10, AC-TEST-15).
///
/// Ports the Expo app's `e2e/smoke.yaml` (see git history) intent onto
/// real widgets driving the real
/// router/database/camera stack — not the 11 Maestro files it replaces, one
/// of which (`smoke.yaml`) was the only one worth keeping as an automated
/// suite (the other 10 either fold into widget tests or drop outright, see
/// §10). It runs against `lib/main_e2e.dart` — the auth bypass lives only
/// there (FLUTTER_MIGRATION.md §5) — never `lib/main.dart`.
///
/// This file only *compiles* on this box (no Android SDK/Java/Xcode here);
/// `flutter analyze` covers that. Running it for real needs a device/
/// emulator/simulator and is a Mac concern — see the exact commands in
/// `app/README.md`.
///
/// Deliberately avoids `pumpAndSettle()` throughout: `SkeletonBox`
/// (`lib/design_system/skeleton.dart`) drives its shimmer with a
/// `TweenAnimationBuilder` that loops forever for as long as a skeleton is on
/// screen (AC-DS-11), and `StatefulShellRoute.indexedStack` keeps every
/// visited tab's branch mounted (off-stage, not disposed) once first visited.
/// A skeleton still looping anywhere in that stack — even off-stage — makes
/// `pumpAndSettle()` time out, because it pumps until *no* frame is
/// scheduled. `_pumpUntilFound` below pumps bounded, fixed steps instead and
/// only waits for the specific text/widget the next step needs, which is
/// unaffected by an unrelated animation still running elsewhere in the tree.
library;

import 'package:camera/camera.dart' show CameraPreview;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/bootstrap.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/features/onboarding/providers/onboarding_status.dart';
import 'package:glean/main_e2e.dart' as app;
import 'package:integration_test/integration_test.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'launch, five tabs, camera-permission handling, and manual pantry add',
    (WidgetTester tester) async {
      await app.main();
      await _pumpUntilFound(tester, find.byType(GleanRoot));
      final container = ProviderScope.containerOf(
        tester.element(find.byType(GleanRoot)),
      );
      // The gate briefly fails open while SQLite resolves onboarding status.
      // A tab label alone can therefore identify a transient shell, not a
      // ready returning-user UI. Wait for the real status before tapping.
      final deadline = DateTime.now().add(const Duration(seconds: 20));
      while (!container.read(databaseReadyProvider).hasValue ||
          !container.read(hasCompletedOnboardingProvider).hasValue) {
        if (DateTime.now().isAfter(deadline)) {
          fail('Database/onboarding did not resolve within 20 seconds');
        }
        await tester.pump(const Duration(milliseconds: 100));
      }
      await tester.pump();
      if (!container.read(hasCompletedOnboardingProvider).requireValue) {
        await _pumpUntilFound(tester, find.text('Skip'));
        await tester.tap(find.text('Skip'));
        await _pumpUntilFound(tester, find.byType(NavigationBar));
      }

      // --- Fresh launch: the native splash hands over to `bootstrap.dart`'s
      // `_SplashHolding` (same brand green, no text) while the database
      // opens, then to the real tab tree. Bounds that DB-init window instead
      // of assuming it's already done by the next line. ---
      await _pumpUntilFound(tester, find.text('Pantry'));

      // --- All five tabs visible (mirrors smoke.yaml's five assertVisible
      // calls) — the `NavigationDestination` labels in `AppShell`. ---
      expect(find.text('Pantry'), findsWidgets);
      expect(find.text('Meals'), findsWidgets);
      expect(find.text('Plan'), findsWidgets);
      expect(find.text('Shop'), findsWidgets);
      expect(find.text('Settings'), findsWidgets);

      // --- Navigate to each tab and assert its own heading, same order as
      // smoke.yaml. `StatefulShellRoute.indexedStack` branches build lazily
      // on first visit, so each label below is still unambiguous the first
      // time it's tapped; `.first` guards the one case that isn't (Pantry,
      // whose own AppBar title duplicates its tab label from frame one). ---
      await _tapTab(tester, 'Meals');
      await _pumpUntilFound(tester, find.text('Meals'));

      await _tapTab(tester, 'Plan');
      await _pumpUntilFound(tester, find.text('Plan'));

      await _tapTab(tester, 'Shop');
      // The Shop tab's own heading is "Shopping", not "Shop" (AC-SHOP-07
      // unifies in-screen cart wording; the tab label itself stays short).
      await _pumpUntilFound(tester, find.text('Shopping'));

      await _tapTab(tester, 'Settings');
      await _pumpUntilFound(tester, find.text('Settings'));

      await _tapTab(tester, 'Pantry');
      await _pumpUntilFound(tester, find.byTooltip('Add to pantry'));

      // --- Camera-permission handling (AC-TEST-16, AC-PAN-13) ---
      //
      // Opens the `+` sheet, chooses Scan, and lets `ScanScreen` run its real
      // `checkPermission()` against the device/emulator/simulator — this is
      // the one branch a widget test cannot cover (`ReceiptCameraController`
      // is faked there specifically because widget tests have no camera
      // platform channel; see that file's doc comment). It deliberately
      // never taps "Grant permission": that would raise the OS's *native*
      // permission dialog, which is not a Flutter widget and cannot be
      // driven from `WidgetTester`. Instead it asserts the back affordance
      // is present and usable in whatever permission state the device
      // starts in — denied, permanently denied, or already granted (the
      // live preview) — and uses it, which is exactly the dead end AC-PAN-13
      // fixes: every one of those states must have a way out.
      await tester.tap(find.byTooltip('Add to pantry'));
      await _pumpUntilFound(tester, find.text('Scan receipt'));
      await tester.tap(find.text('Scan receipt'));

      await _pumpUntilFound(
        tester,
        find.byWidgetPredicate(
          (Widget widget) =>
              widget is CameraPreview ||
              (widget is Text &&
                  (widget.data == 'Grant permission' ||
                      widget.data == 'Open Settings')),
        ),
      );
      expect(
        find.byTooltip('Cancel'),
        findsOneWidget,
        reason:
            'the Scan screen must always offer a way out, in every '
            'permission state (AC-PAN-13) — the RN app dead-ended here',
      );
      await tester.tap(find.byTooltip('Cancel'));
      await _pumpUntilFound(tester, find.byTooltip('Add to pantry'));

      // --- Add item via manual entry (AC-PAN-03, AC-TEST-15) ---
      //
      // Dead code in the RN app — nothing routed to it there at all. Reaches
      // it the same way a real user would: through the `+` sheet, which is
      // available whether the pantry is empty or full.
      await tester.tap(find.byTooltip('Add to pantry'));
      await _pumpUntilFound(tester, find.text('Manual entry'));
      await tester.tap(find.text('Manual entry'));
      await _pumpUntilFound(tester, find.text('Add item'));

      await tester.enterText(find.byType(TextField).at(0), 'test chicken');
      await tester.enterText(find.byType(TextField).at(1), '500');

      // Category is required (no LLM classification behind a manually typed
      // item — see `manual_entry_screen.dart`'s doc comment). "Leafy Greens"
      // is simply the first taxonomy entry, chosen so it's on-screen the
      // moment the menu opens with no scroll needed; which category is
      // picked doesn't matter to this smoke test.
      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await _pumpUntilFound(tester, find.text('Leafy Greens'));
      await tester.tap(find.text('Leafy Greens'));
      await _pumpUntilFound(tester, find.text('Add to pantry'));

      await tester.tap(find.text('Add to pantry'));

      // --- Verify the item lands back on Pantry (AC-PAN-03/AC-DATA-04: a
      // plain drift write, no invalidation call — the stream just re-emits). ---
      await _pumpUntilFound(tester, find.text('test chicken'));
      expect(find.text('test chicken'), findsWidgets);
    },
  );
}

/// Pumps fixed, bounded steps until [finder] locates something, instead of
/// `pumpAndSettle()` — see this file's top comment for why that matters here.
Future<void> _pumpUntilFound(
  WidgetTester tester,
  Finder finder, {
  Duration timeout = const Duration(seconds: 20),
  Duration step = const Duration(milliseconds: 100),
}) async {
  final DateTime deadline = DateTime.now().add(timeout);
  while (finder.evaluate().isEmpty) {
    if (DateTime.now().isAfter(deadline)) {
      fail('Timed out after $timeout waiting for $finder');
    }
    await tester.pump(step);
  }
  // Advance multiple frames: one long pump can merely start a route animation.
  for (var i = 0; i < 5; i++) {
    await tester.pump(step);
  }
}

Future<void> _tapTab(WidgetTester tester, String label) async {
  await tester.tap(
    find.descendant(of: find.byType(NavigationBar), matching: find.text(label)),
  );
  for (var i = 0; i < 5; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}
