// Widget tests for the first-run flow: one basics page (the two numbers plus
// the dietary disclosure) that hands its values forward to the pantry step,
// which is the only step that writes them, with the taste interview in between.
// The interview's own conversation is covered by `interview_page_test.dart`;
// here it only has to be passed through, either skipped or confirmed.
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
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;

import '../../data/fixture.dart';
import '../../support/fake_interview_backend.dart';

const String _userId = 'user-1';
const Key _dinnersSlider = Key('onboarding.dinnersSlider');
const Key _servingsSlider = Key('onboarding.servingsSlider');
const Key _dinnersValue = ValueKey<String>('onboarding.dinnersValue');
const Key _servingsValue = ValueKey<String>('onboarding.servingsValue');

Widget _buildApp({
  required GleanDatabase db,
  Haptics? haptics,
  http.Client? httpClient,
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
      apiBaseUrlProvider.overrideWithValue('http://localhost:9999'),
      // These tests hold no session: the interview call goes out unauthenticated, as the client allows.
      apiAccessTokenProvider.overrideWithValue(() async => null),
      if (httpClient != null) httpClientProvider.overrideWithValue(httpClient),
      if (haptics != null) hapticsProvider.overrideWithValue(haptics),
    ],
    child: MaterialApp.router(theme: gleanLightTheme, routerConfig: router),
  );
}

void main() {
  setUpAll(registerInterviewFallbacks);

  late GleanDatabase db;
  late FakeInterviewBackend interview;

  setUp(() {
    db = createTestDatabase();
    // One question, repeated: these tests only walk past the interview.
    interview = FakeInterviewBackend(<ScriptedResponse>[
      questionResponse(turn: 1),
    ])..attach();
  });
  tearDown(() => db.close());

  /// Walks first run past the interview without answering it. Skip all is the page-scoped skip, so it saves
  /// nothing and lands on the pantry page.
  Future<void> skipTastePage(WidgetTester tester) async {
    await tester.tap(find.text('Skip all'));
    await tester.pumpAndSettle();
  }

  Future<void> pumpOnboarding(
    WidgetTester tester, {
    Size size = const Size(420, 1200),
    double textScale = 1,
  }) async {
    tester.platformDispatcher.textScaleFactorTestValue = textScale;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.binding.setSurfaceSize(size);
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(_buildApp(db: db, httpClient: interview.client));
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
      expect(find.text('Question 1 of 7'), findsOneWidget);

      await skipTastePage(tester);
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
      expect(find.text('Question 1 of 7'), findsOneWidget);

      await skipTastePage(tester);
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
      await skipTastePage(tester);
      expect(find.text('Stock your pantry'), findsOneWidget);

      await tester.tap(find.text('Back'));
      await tester.pumpAndSettle();
      expect(find.text('Question 1 of 7'), findsOneWidget, reason: 'one step');

      await tester.tap(find.byTooltip('Back'));
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
    'the progress indicator marks the current page, and the taste interview is '
    'done or skipped rather than reserved',
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
        find.bySemanticsLabel('Step 2 of 3: Taste'),
        findsOneWidget,
        reason: 'it is a step of the flow now, not a reserved place',
      );

      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      expect(isCurrent('0'), isFalse);
      expect(isCurrent('1'), isTrue);
      expect(isCurrent('2'), isFalse);
      expect(
        find.bySemanticsLabel('Step 1 of 3: Basics, completed'),
        findsOneWidget,
      );

      await skipTastePage(tester);

      expect(isCurrent('0'), isFalse);
      expect(isCurrent('1'), isFalse);
      expect(isCurrent('2'), isTrue);
      expect(find.bySemanticsLabel('Step 3 of 3: Pantry'), findsOneWidget);
      expect(
        find.bySemanticsLabel('Step 2 of 3: Taste, skipped'),
        findsOneWidget,
        reason: 'Skip all is not the same as answering',
      );

      semantics.dispose();
    },
  );

  for (final double scale in <double>[1.3, 2]) {
    testWidgets(
      'both pages fit a 320-wide phone at ${scale}x text, with the chips open',
      (WidgetTester tester) async {
        await pumpOnboarding(
          tester,
          size: const Size(320, 844),
          textScale: scale,
        );
        expect(tester.takeException(), isNull, reason: 'the basics page');

        await tester.ensureVisible(find.text('Dietary preferences'));
        await tester.tap(find.text('Dietary preferences'));
        await tester.pumpAndSettle();
        expect(
          tester.takeException(),
          isNull,
          reason: 'the basics page with the chips open',
        );
        await tester.ensureVisible(find.text('Paleo'));
        expect(find.text('Paleo'), findsOneWidget);

        await tester.ensureVisible(find.text('Continue'));
        await tester.tap(find.text('Continue'));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull, reason: 'the interview page');

        await tester.ensureVisible(find.text('Skip all'));
        await skipTastePage(tester);
        expect(tester.takeException(), isNull, reason: 'the pantry page');

        expect(find.text('Stock your pantry'), findsOneWidget);
        await tester.ensureVisible(find.text('Scan a receipt'));
        expect(find.text('Scan a receipt'), findsOneWidget);
      },
    );
  }

  testWidgets(
    'a passed basics step looks and reads as done, and says how it was passed',
    (WidgetTester tester) async {
      final SemanticsHandle semantics = tester.ensureSemantics();
      await pumpOnboarding(tester);

      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      final Finder basicsSlot = find.byKey(
        const ValueKey<String>('onboarding.step.0'),
      );
      expect(
        find.bySemanticsLabel('Step 1 of 3: Basics, completed'),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: basicsSlot,
          matching: find.byIcon(Icons.check_rounded),
        ),
        findsOneWidget,
      );

      await tester.tap(find.byTooltip('Back'));
      await tester.pumpAndSettle();
      expect(
        find.bySemanticsLabel('Step 1 of 3: Basics'),
        findsOneWidget,
        reason: 'back on the basics page it is current again, not done',
      );

      await tester.tap(find.text('Skip this page'));
      await tester.pumpAndSettle();
      expect(
        find.bySemanticsLabel('Step 1 of 3: Basics, skipped'),
        findsOneWidget,
        reason: 'skipping is not the same as answering',
      );
      expect(
        find.descendant(
          of: basicsSlot,
          matching: find.byIcon(Icons.remove_rounded),
        ),
        findsOneWidget,
      );

      semantics.dispose();
    },
  );

  testWidgets('the pantry page keeps its content centred while it fits', (
    WidgetTester tester,
  ) async {
    await pumpOnboarding(tester);
    await tester.tap(find.text('Continue'));
    await tester.pumpAndSettle();
    await skipTastePage(tester);

    final Rect body = tester.getRect(find.byType(SingleChildScrollView));
    final Rect heading = tester.getRect(find.text('Stock your pantry'));
    final Rect icon = tester.getRect(find.byIcon(Icons.receipt_long_rounded));

    expect((heading.top + icon.bottom) / 2, closeTo(body.center.dy, 2));
  });

  testWidgets(
    'a screen reader can expand and collapse the dietary disclosure',
    (WidgetTester tester) async {
      final SemanticsHandle semantics = tester.ensureSemantics();
      await pumpOnboarding(tester);

      SemanticsNode disclosure() => find.semantics
          .byLabel('Dietary preferences, 0 selected')
          .evaluate()
          .single;

      expect(
        disclosure().getSemanticsData().hasAction(SemanticsAction.tap),
        isTrue,
        reason: 'a semantic button with no tap action cannot be activated',
      );

      tester.semantics.tap(
        find.semantics.byLabel('Dietary preferences, 0 selected'),
      );
      await tester.pumpAndSettle();
      expect(find.text('Vegan'), findsOneWidget);
      expect(
        disclosure()
            .getSemanticsData()
            .flagsCollection
            .isExpanded
            .toBoolOrNull(),
        isTrue,
      );

      tester.semantics.tap(
        find.semantics.byLabel('Dietary preferences, 0 selected'),
      );
      await tester.pumpAndSettle();
      expect(find.text('Vegan'), findsNothing);

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
      await skipTastePage(tester);
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
