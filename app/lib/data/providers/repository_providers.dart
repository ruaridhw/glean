// One `Provider` per repository, each a thin wrapper around `GleanDatabase`. Mutations are plain async
// methods; no invalidation machinery is needed because every read is a drift stream that re-emits on its own.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../repositories/catalogue_repository.dart';
import '../repositories/household_profile_repository.dart';
import '../repositories/ingredients_repository.dart';
import '../repositories/pantry_repository.dart';
import '../repositories/plan_repository.dart';
import '../repositories/recipes_repository.dart';
import '../repositories/shopping_repository.dart';
import '../repositories/user_config_repository.dart';
import 'database_providers.dart';

final Provider<IngredientsRepository> ingredientsRepositoryProvider =
    Provider<IngredientsRepository>(
      (ref) => IngredientsRepository(ref.watch(gleanDatabaseProvider)),
    );

final Provider<PantryRepository> pantryRepositoryProvider =
    Provider<PantryRepository>(
      (ref) => PantryRepository(
        ref.watch(gleanDatabaseProvider),
        ref.watch(ingredientsRepositoryProvider),
      ),
    );

final Provider<RecipesRepository> recipesRepositoryProvider =
    Provider<RecipesRepository>(
      (ref) => RecipesRepository(
        ref.watch(gleanDatabaseProvider),
        ref.watch(ingredientsRepositoryProvider),
      ),
    );

final Provider<PlanRepository> planRepositoryProvider =
    Provider<PlanRepository>(
      (ref) => PlanRepository(
        ref.watch(gleanDatabaseProvider),
        ref.watch(pantryRepositoryProvider),
      ),
    );

final Provider<ShoppingRepository> shoppingRepositoryProvider =
    Provider<ShoppingRepository>(
      (ref) => ShoppingRepository(
        ref.watch(gleanDatabaseProvider),
        ref.watch(ingredientsRepositoryProvider),
      ),
    );

final Provider<UserConfigRepository> userConfigRepositoryProvider =
    Provider<UserConfigRepository>(
      (ref) => UserConfigRepository(ref.watch(gleanDatabaseProvider)),
    );

final Provider<CatalogueRepository> catalogueRepositoryProvider =
    Provider<CatalogueRepository>(
      (ref) => CatalogueRepository(ref.watch(gleanDatabaseProvider)),
    );

final Provider<HouseholdProfileRepository> householdProfileRepositoryProvider =
    Provider<HouseholdProfileRepository>(
      (ref) => HouseholdProfileRepository(ref.watch(gleanDatabaseProvider)),
    );
