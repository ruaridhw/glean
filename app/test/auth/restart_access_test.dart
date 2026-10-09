import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/auth/auth_controller.dart';
import 'package:glean/auth/session_overrides.dart';
import 'package:glean/auth/token_storage.dart';
import 'package:glean/bootstrap.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/router.dart';
import '../data/fixture.dart';
import '../support/harness.dart';
import 'support/fakes.dart';

void main() {
  gleanWidgetTest(
    'restart from expired secure storage keeps real local data accessible and gates AI through production bootstrap wiring',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        'glean_user_sub': 'reopen-user',
      });
      final storage = SecureTokenStorage();
      final snapshot = await loadInitialAuthSnapshot(storage);
      final db = createTestDatabase();
      addTearDown(db.close);
      await UserConfigRepository(db).markOnboardingCompleted('reopen-user');
      await PantryRepository(db, IngredientsRepository(db)).addItem(
        userId: 'reopen-user',
        name: 'chicken breast',
        quantity: 200,
        unit: 'g',
        category: 'poultry',
      );
      final container = ProviderContainer(
        overrides: [
          gleanDatabaseProvider.overrideWithValue(db),
          apiBaseUrlProvider.overrideWithValue('https://api.example.test'),
          ...sessionOverrides(
            snapshot,
            storage: storage,
            client: MockCognitoAuthClient(),
          ),
        ],
      );
      addTearDown(container.dispose);
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const GleanRoot(),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('chicken breast'), findsOneWidget);
      expect(find.textContaining('Signed out — reconnect'), findsOneWidget);
      expect(container.read(currentUserIdProvider), 'reopen-user');
      expect(await container.read(apiAccessTokenProvider)(), isNull);
      container.read(goRouterProvider).go(AppRoutes.plan.path);
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, 'Generate'))
            .onPressed,
        isNull,
      );
    },
  );
}
