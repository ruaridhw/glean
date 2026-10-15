import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/features/onboarding/providers/onboarding_status.dart';

import '../../data/fixture.dart';

void main() {
  late GleanDatabase db;

  setUp(() => db = createTestDatabase());
  tearDown(() => db.close());

  test('false until markOnboardingCompleted, then true', () async {
    final container = ProviderContainer(
      overrides: [
        gleanDatabaseProvider.overrideWithValue(db),
        currentUserIdProvider.overrideWithValue('u1'),
      ],
    );
    addTearDown(container.dispose);
    final sub = container.listen(hasCompletedOnboardingProvider, (_, _) {});
    await container.read(hasCompletedOnboardingProvider.future);
    expect(sub.read().value, isFalse);

    await container
        .read(userConfigRepositoryProvider)
        .markOnboardingCompleted('u1');
    await Future<void>.delayed(Duration.zero);
    expect(sub.read().value, isTrue);
  });
}
