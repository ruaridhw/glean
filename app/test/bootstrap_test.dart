// Coverage for the splash → app hand-off (FLUTTER_MIGRATION.md §7, R-09):
// `GleanRoot` used to resolve the database gate with a bare `.when()` — a
// hard cut reproducing the exact unanimated RN splash pop §7 removes
// elsewhere. This asserts the mechanism (`GleanCrossFade`, i.e. an
// `AnimatedSwitcher`) is actually wrapping the transition — present before
// the gate resolves (with the real app not yet mounted) and still present
// once it has — rather than sampling an intermediate animation frame (see
// `test/support/harness.dart`'s guidance on why that's the wrong thing to
// assert on here).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/app.dart';
import 'package:glean/bootstrap.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:riverpod/misc.dart';

import 'support/harness.dart';

void main() {
  group('GleanRoot', () {
    gleanWidgetTest(
      'cross-fades the database gate instead of hard-cutting to the app '
      '(AC-TRN-05)',
      (WidgetTester tester) async {
        // Deliberately built *inside* the test body, not in `setUp` —
        // `setUp`/`tearDown` run outside `testWidgets`'s FakeAsync zone, and
        // a `Completer` created there doesn't let the zone's clock control
        // its completion callback, so `gate.complete()` below would never
        // actually unblock the pumps that follow it.
        final Completer<void> gate = Completer<void>();
        final AppTestHarness harness = AppTestHarness(
          overrides: <Override>[
            // Full control over when the gate resolves, independent of the
            // real database open the harness's `gleanDatabaseProvider`
            // override otherwise satisfies instantly.
            databaseReadyProvider.overrideWith((Ref ref) => gate.future),
          ],
        );
        addTearDown(harness.dispose);

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: harness.container,
            child: const GleanRoot(),
          ),
        );

        // Still resolving: the cross-fade mechanism is already in the tree
        // and the real app hasn't mounted yet.
        expect(find.byType(GleanCrossFade), findsOneWidget);
        expect(find.byType(AnimatedSwitcher), findsOneWidget);
        expect(find.byType(GleanApp), findsNothing);

        gate.complete();
        // Advance in fixed steps rather than `pumpAndSettle` — Pantry (the
        // landing tab `GleanApp` resolves to) shows a perpetually-animating
        // `SkeletonBox` on its first frame (F-13), which never reaches a
        // quiescent frame for `pumpAndSettle` to settle on.
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 300));

        expect(find.byType(GleanApp), findsOneWidget);
        // Still wrapped in the same cross-fade mechanism, not something
        // that swapped it out mid-transition (there are now two: this outer
        // one, plus whichever tab screen mounted underneath also uses its
        // own for its skeleton→content load).
        expect(find.byType(GleanCrossFade), findsAtLeastNWidgets(1));
      },
    );
  });
}
