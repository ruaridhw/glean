// Widget tests for the first-run flow: one basics page (the two numbers plus
// the dietary disclosure) that hands its values forward to the pantry step,
// which is the only step that writes them.
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
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

  testWidgets(
    'skipping the basics page finishes setup without saving this page\'s '
    'answers, so the defaults still apply',
    (WidgetTester tester) async {
      await pumpOnboarding(tester);

      await tester.drag(find.byKey(_dinnersSlider), const Offset(400, 0));
      await tester.pumpAndSettle();
      await tester.drag(find.byKey(_servingsSlider), const Offset(-400, 0));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Dietary preferences'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Vegan'));
      await tester.tap(find.text('Vegan'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Skip this page'));
      await tester.pumpAndSettle();
      expect(find.text('Stock your pantry'), findsOneWidget);

      await tester.tap(find.text("I'll do this later"));
      await tester.pumpAndSettle();

      expect(find.text('SCAN_SCREEN_PLACEHOLDER'), findsNothing);
      final saved = await UserConfigRepository(db).get(_userId);
      expect(saved.mealsPerWeek, UserConfigView.defaultMealsPerWeek);
      expect(saved.preferredServings, UserConfigView.defaultPreferredServings);
      expect(saved.dietaryFlags, isEmpty);
      expect(
        (await (db.select(
          db.userConfig,
        )..where((t) => t.id.equals(_userId))).getSingle()).onboardingCompleted,
        isTrue,
      );
    },
  );

  testWidgets(
    'the dietary disclosure stays closed until asked and counts what is '
    'selected',
    (WidgetTester tester) async {
      await pumpOnboarding(tester);

      expect(find.text('Dietary preferences'), findsOneWidget);
      expect(find.text('0 selected'), findsOneWidget);
      expect(find.text('Vegetarian'), findsNothing);

      await tester.tap(find.text('Dietary preferences'));
      await tester.pumpAndSettle();
      expect(find.text('Vegetarian'), findsOneWidget);
      expect(find.text('Paleo'), findsOneWidget);

      await tester.tap(find.text('Vegan'));
      await tester.pumpAndSettle();
      expect(find.text('1 selected'), findsOneWidget);

      await tester.tap(find.text('Peanut-free'));
      await tester.pumpAndSettle();
      expect(find.text('2 selected'), findsOneWidget);

      await tester.tap(find.text('Dietary preferences'));
      await tester.pumpAndSettle();
      expect(find.text('Vegan'), findsNothing);
      expect(find.text('2 selected'), findsOneWidget);
    },
  );

  testWidgets(
    'Back from the pantry page returns to the basics page with the chosen '
    'values still in place',
    (WidgetTester tester) async {
      await pumpOnboarding(tester);

      await tester.drag(find.byKey(_dinnersSlider), const Offset(400, 0));
      await tester.pumpAndSettle();
      await tester.drag(find.byKey(_servingsSlider), const Offset(-400, 0));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Dietary preferences'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Vegan'));
      await tester.tap(find.text('Vegan'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
      expect(find.text('Stock your pantry'), findsOneWidget);

      await tester.tap(find.text('Back'));
      await tester.pumpAndSettle();

      expect(find.text('The basics'), findsOneWidget);
      expect(tester.widget<Text>(find.byKey(_dinnersValue)).data, '7');
      expect(tester.widget<Text>(find.byKey(_servingsValue)).data, '1');
      expect(find.text('1 selected'), findsOneWidget);

      await tester.tap(find.text('Dietary preferences'));
      await tester.pumpAndSettle();
      final FilterChip vegan = tester.widget<FilterChip>(
        find.ancestor(
          of: find.text('Vegan'),
          matching: find.byType(FilterChip),
        ),
      );
      expect(vegan.selected, isTrue);
    },
  );

  testWidgets(
    'the progress indicator marks the current page and keeps the taste '
    'interview\'s slot reserved',
    (WidgetTester tester) async {
      final SemanticsHandle semantics = tester.ensureSemantics();
      await pumpOnboarding(tester);

      bool isCurrent(String slot) =>
          tester
              .getSemantics(
                find.byKey(ValueKey<String>('onboarding.step.$slot')),
              )
              .getSemanticsData()
              .flagsCollection
              .isSelected
              .toBoolOrNull() ??
          false;

      expect(isCurrent('0'), isTrue);
      expect(isCurrent('1'), isFalse);
      expect(isCurrent('2'), isFalse);
      expect(
        find.bySemanticsLabel('Step 2 of 3: Taste, coming later'),
        findsOneWidget,
      );

      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      expect(isCurrent('0'), isFalse);
      expect(isCurrent('1'), isFalse);
      expect(isCurrent('2'), isTrue);
      expect(find.bySemanticsLabel('Step 3 of 3: Pantry'), findsOneWidget);

      semantics.dispose();
    },
  );

  testWidgets(
    'shows the same bounds as Settings, opens on the defaults, and calls the '
    'servings control Servings on first run',
    (WidgetTester tester) async {
      await pumpOnboarding(tester);

      expect(tester.widget<Text>(find.byKey(_dinnersValue)).data, '5');
      expect(tester.widget<Text>(find.byKey(_servingsValue)).data, '2');
      expect(find.text('SERVINGS'), findsOneWidget);
      expect(find.text('DEFAULT SERVINGS'), findsNothing);

      await tester.drag(find.byKey(_dinnersSlider), const Offset(-400, 0));
      await tester.pumpAndSettle();
      expect(tester.widget<Text>(find.byKey(_dinnersValue)).data, '3');

      await tester.drag(find.byKey(_servingsSlider), const Offset(-400, 0));
      await tester.pumpAndSettle();
      expect(tester.widget<Text>(find.byKey(_servingsValue)).data, '1');
    },
  );

  testWidgets(
    "I'll do this later on the pantry page saves what the basics page "
    'captured without opening the scanner',
    (WidgetTester tester) async {
      await pumpOnboarding(tester);

      await tester.drag(find.byKey(_dinnersSlider), const Offset(400, 0));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
      await tester.tap(find.text("I'll do this later"));
      await tester.pumpAndSettle();

      expect(find.text('SCAN_SCREEN_PLACEHOLDER'), findsNothing);
      final saved = await UserConfigRepository(db).get(_userId);
      expect(saved.mealsPerWeek, 7);
      expect(
        (await (db.select(
          db.userConfig,
        )..where((t) => t.id.equals(_userId))).getSingle()).onboardingCompleted,
        isTrue,
      );
    },
  );
}
