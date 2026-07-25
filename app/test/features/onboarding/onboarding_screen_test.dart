// Widget tests for the first-run setup flow itself: stepping through
// dinners/servings/dietary flags, persisting what was captured, being
// skippable at any point, and ending by pointing at receipt-scan
// (AC-UX-04).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/onboarding/onboarding_screen.dart';
import 'package:glean/features/onboarding/providers/onboarding_status.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';

import '../../data/fixture.dart';

const String _userId = 'user-1';

Widget _buildApp({
  required GleanDatabase db,
  required InMemoryOnboardingStatusStore store,
  Haptics? haptics,
}) {
  final GoRouter router = GoRouter(
    initialLocation: '/',
    routes: <RouteBase>[
      GoRoute(path: '/', builder: (_, _) => const OnboardingScreen()),
      GoRoute(
        path: AppRoutes.intakeScan.path,
        name: AppRoutes.intakeScan.name,
        builder: (_, _) => const Text('SCAN_SCREEN_PLACEHOLDER'),
      ),
    ],
  );
  return ProviderScope(
    overrides: [
      gleanDatabaseProvider.overrideWithValue(db),
      currentUserIdProvider.overrideWithValue(_userId),
      onboardingStatusStoreProvider.overrideWithValue(store),
      if (haptics != null) hapticsProvider.overrideWithValue(haptics),
    ],
    child: MaterialApp.router(theme: gleanLightTheme, routerConfig: router),
  );
}

void main() {
  late GleanDatabase db;

  setUp(() => db = createTestDatabase());
  tearDown(() => db.close());

  testWidgets(
    'steps through dinners, servings and dietary flags, persists them, '
    'marks itself complete, and ends on receipt-scan',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(420, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      final store = InMemoryOnboardingStatusStore();
      await tester.pumpWidget(_buildApp(db: db, store: store));
      await tester.pumpAndSettle();

      expect(
        find.text('How many dinners do you cook at home most weeks?'),
        findsOneWidget,
      );

      final TestGesture gesture = await tester.startGesture(
        tester.getCenter(find.byType(Slider)),
      );
      await gesture.moveBy(const Offset(80, 0));
      await gesture.up();
      await tester.pump();

      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();
      expect(
        find.text('How many people are you usually cooking for?'),
        findsOneWidget,
      );

      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();
      expect(
        find.text('Any dietary preferences we should know about?'),
        findsOneWidget,
      );

      await tester.tap(find.text('Vegan'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Scan a receipt'));
      await tester.pumpAndSettle();

      expect(find.text('SCAN_SCREEN_PLACEHOLDER'), findsOneWidget);

      final saved = await UserConfigRepository(db).get(_userId);
      expect(saved.dietaryFlags, <String>['Vegan']);
      expect(await store.watch(_userId).first, isTrue);
    },
  );

  testWidgets(
    'Skip is available immediately, discards captured input, and marks '
    'setup complete without navigating to scan',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(420, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      final store = InMemoryOnboardingStatusStore();
      await tester.pumpWidget(_buildApp(db: db, store: store));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Skip'));
      await tester.pumpAndSettle();

      expect(find.text('SCAN_SCREEN_PLACEHOLDER'), findsNothing);
      expect(await store.watch(_userId).first, isTrue);

      final saved = await UserConfigRepository(db).get(_userId);
      expect(saved.dietaryFlags, isEmpty);
    },
  );

  testWidgets(
    '"I\'ll do this later" on the final step also persists captured input '
    'without navigating to scan',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(420, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      final store = InMemoryOnboardingStatusStore();
      await tester.pumpWidget(_buildApp(db: db, store: store));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Vegetarian'));
      await tester.pumpAndSettle();
      await tester.tap(find.text("I'll do this later"));
      await tester.pumpAndSettle();

      expect(find.text('SCAN_SCREEN_PLACEHOLDER'), findsNothing);
      final saved = await UserConfigRepository(db).get(_userId);
      expect(saved.dietaryFlags, <String>['Vegetarian']);
      expect(await store.watch(_userId).first, isTrue);
    },
  );
}
