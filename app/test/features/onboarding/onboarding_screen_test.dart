// Widget tests for the first-run flow: one basics page (the two numbers plus
// the dietary disclosure) that hands its values forward to the pantry step,
// which is the only step that writes them.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/onboarding/onboarding_screen.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';

import '../../data/fixture.dart';

const String _userId = 'user-1';
const Key _dinnersSlider = Key('onboarding.dinnersSlider');
const Key _servingsSlider = Key('onboarding.servingsSlider');
const Key _dinnersValue = ValueKey<String>('onboarding.dinnersValue');
const Key _servingsValue = ValueKey<String>('onboarding.servingsValue');

Widget _buildApp({required GleanDatabase db, Haptics? haptics}) {
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
      if (haptics != null) hapticsProvider.overrideWithValue(haptics),
    ],
    child: MaterialApp.router(theme: gleanLightTheme, routerConfig: router),
  );
}

void main() {
  late GleanDatabase db;

  setUp(() => db = createTestDatabase());
  tearDown(() => db.close());

  Future<void> pumpOnboarding(WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(420, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(_buildApp(db: db));
    await tester.pumpAndSettle();
  }

  Future<void> saveAndRead(WidgetTester tester) async {
    await tester.tap(find.text('Scan a receipt'));
    await tester.pumpAndSettle();
    expect(find.text('SCAN_SCREEN_PLACEHOLDER'), findsOneWidget);
  }

  testWidgets(
    'carries the chosen dinners, servings and dietary flags through to the '
    'save that the pantry step performs',
    (WidgetTester tester) async {
      await pumpOnboarding(tester);

      expect(find.text('The basics'), findsOneWidget);

      await tester.drag(find.byKey(_dinnersSlider), const Offset(400, 0));
      await tester.pumpAndSettle();
      expect(tester.widget<Text>(find.byKey(_dinnersValue)).data, '7');

      await tester.drag(find.byKey(_servingsSlider), const Offset(400, 0));
      await tester.pumpAndSettle();
      expect(tester.widget<Text>(find.byKey(_servingsValue)).data, '6');

      await tester.tap(find.text('Dietary preferences'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Vegan'));
      await tester.tap(find.text('Vegan'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
      expect(find.text('Stock your pantry'), findsOneWidget);

      await saveAndRead(tester);

      final saved = await UserConfigRepository(db).get(_userId);
      expect(saved.mealsPerWeek, 7);
      expect(saved.preferredServings, 6);
      expect(saved.dietaryFlags, <String>['Vegan']);
      expect(
        (await (db.select(
          db.userConfig,
        )..where((t) => t.id.equals(_userId))).getSingle()).onboardingCompleted,
        isTrue,
      );
      // The model still writes the same tolerance default it always has.
      expect(saved.purchaseTolerance, UserConfigView.defaultPurchaseTolerance);
    },
  );
}
