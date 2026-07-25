// Ported from the Expo app's `src/db/recipes.ts` (see git history), scoped
// by `userId` (AC-DATA-02):
// the local `recipes` table is a user's saved/imported library, not the
// read-only server-side search corpus.
//
// `getByExternalId` attaches dietary flags like `getById`/`getSavedRecipes`
// do (AC-MEAL-13) — RN's version skipped that step, so an already-saved
// recipe reached by external id (the import-dedupe path) silently lost its
// dietary tags.
//
// `deleteRecipe` needs no special-casing to preserve a referencing plan
// entry (AC-MEAL-03): `meal_plan_entries.recipe_id` is declared
// `onDelete: setNull` in the schema, and the entry's `recipeTitle` snapshot
// was already captured when it was created, so the plain delete below is
// enough — SQLite (with `PRAGMA foreign_keys = ON`) does the rest.
import 'dart:convert';

import 'package:drift/drift.dart';

import '../database.dart';
import '../models/recipe_view.dart';
import 'ingredients_repository.dart';

class SaveRecipeIngredient {
  const SaveRecipeIngredient({
    required this.canonicalName,
    required this.quantity,
    required this.unit,
    this.apiIngredientId,
    this.preparation,
    this.isOptional = false,
    this.substitutions = const [],
  });

  final String canonicalName;
  final double quantity;
  final String unit;
  final String? apiIngredientId;
  final String? preparation;
  final bool isOptional;
  final List<String> substitutions;
}

class RecipesRepository {
  RecipesRepository(this._db, this._ingredients);

  final GleanDatabase _db;
  final IngredientsRepository _ingredients;

  Stream<List<RecipeView>> watchSaved(String userId) {
    final query = _db.select(_db.recipes)
      ..where((t) => t.userId.equals(userId))
      ..orderBy([(t) => OrderingTerm.desc(t.id)]);
    return query.watch().asyncMap(
      (rows) => _attachDietaryFlags(rows.map(_mapRecipe).toList()),
    );
  }

  /// One-shot twin of [watchSaved]: same ordering and dietary-flag
  /// attachment, but a plain `.get()`. Command paths (e.g. meal-plan
  /// generation) need a snapshot of the saved-recipe library, not a
  /// subscription opened and immediately cancelled (FINDINGS.md F-14).
  Future<List<RecipeView>> getSaved(String userId) async {
    final query = _db.select(_db.recipes)
      ..where((t) => t.userId.equals(userId))
      ..orderBy([(t) => OrderingTerm.desc(t.id)]);
    final rows = await query.get();
    return _attachDietaryFlags(rows.map(_mapRecipe).toList());
  }

  Future<RecipeView?> getById({required int id, required String userId}) async {
    final row =
        await (_db.select(_db.recipes)
              ..where((t) => t.id.equals(id) & t.userId.equals(userId)))
            .getSingleOrNull();
    if (row == null) return null;
    final withFlags = await _attachDietaryFlags([_mapRecipe(row)]);
    return withFlags.first;
  }

  Future<RecipeView?> getByExternalId({
    required String externalId,
    required String userId,
  }) async {
    final row =
        await (_db.select(_db.recipes)..where(
              (t) => t.externalId.equals(externalId) & t.userId.equals(userId),
            ))
            .getSingleOrNull();
    if (row == null) return null;
    final withFlags = await _attachDietaryFlags([_mapRecipe(row)]);
    return withFlags.first;
  }

  Future<int> save({
    required String userId,
    String? externalId,
    required String title,
    String? sourceUrl,
    String? cuisine,
    String? difficulty,
    int? activeTimeMins,
    int? totalTimeMins,
    List<String> dietaryFlags = const [],
    List<String> notSuitableFor = const [],
    int? yieldCount,
    String? nutrition,
    List<RecipeInstructionStep> instructions = const [],
    required List<SaveRecipeIngredient> ingredients,
  }) {
    return _db.transaction(() async {
      final recipeId = await _db
          .into(_db.recipes)
          .insert(
            RecipesCompanion.insert(
              userId: userId,
              externalId: Value(externalId),
              title: title,
              sourceUrl: Value(sourceUrl),
              cuisine: Value(cuisine),
              difficulty: Value(difficulty),
              activeTimeMins: Value(activeTimeMins),
              totalTimeMins: Value(totalTimeMins),
              notSuitableFor: Value(jsonEncode(notSuitableFor)),
              yieldCount: Value(yieldCount),
              nutrition: Value(nutrition),
              instructions: Value(
                jsonEncode(instructions.map((s) => s.toJson()).toList()),
              ),
            ),
          );

      for (final flag in dietaryFlags) {
        await _db
            .into(_db.recipeDietaryFlags)
            .insert(
              RecipeDietaryFlagsCompanion.insert(
                recipeId: recipeId,
                flag: flag,
              ),
              mode: InsertMode.insertOrIgnore,
            );
      }

      for (final ing in ingredients) {
        // Recipe endpoints don't return a category (§9 scope is the parse
        // endpoints only), so this ingredient may stay null-categoried
        // until a pantry/shopping resolution upgrades it.
        final ingredient = await _ingredients.resolveOrCreate(
          canonicalName: ing.canonicalName,
          apiIngredientId: ing.apiIngredientId,
        );
        await _db
            .into(_db.recipeIngredients)
            .insert(
              RecipeIngredientsCompanion.insert(
                recipeId: recipeId,
                ingredientId: ingredient.id,
                quantity: ing.quantity,
                unit: ing.unit,
                preparation: Value(ing.preparation),
                isOptional: Value(ing.isOptional),
                substitutions: Value(jsonEncode(ing.substitutions)),
              ),
            );
      }

      return recipeId;
    });
  }

  Future<List<RecipeIngredientView>> getIngredients(int recipeId) async {
    final query = _db.select(_db.recipeIngredients).join([
      innerJoin(
        _db.ingredients,
        _db.ingredients.id.equalsExp(_db.recipeIngredients.ingredientId),
      ),
    ])..where(_db.recipeIngredients.recipeId.equals(recipeId));
    final rows = await query.get();
    return rows.map((row) {
      final ri = row.readTable(_db.recipeIngredients);
      final ing = row.readTable(_db.ingredients);
      return RecipeIngredientView(
        id: ri.id,
        recipeId: ri.recipeId,
        ingredientId: ri.ingredientId,
        quantity: ri.quantity,
        unit: ri.unit,
        preparation: ri.preparation,
        isOptional: ri.isOptional,
        substitutions: (jsonDecode(ri.substitutions) as List).cast<String>(),
        ingredient: IngredientView(
          id: ing.id,
          canonicalName: ing.canonicalName,
          apiIngredientId: ing.apiIngredientId,
          apiName: ing.apiName,
          category: ing.category,
          canonicalUnit: ing.canonicalUnit,
          isStaple: ing.isStaple,
        ),
      );
    }).toList();
  }

  Future<void> deleteRecipe({required int id, required String userId}) {
    return (_db.delete(
      _db.recipes,
    )..where((t) => t.id.equals(id) & t.userId.equals(userId))).go();
  }

  RecipeView _mapRecipe(Recipe row) {
    return RecipeView(
      id: row.id,
      userId: row.userId,
      externalId: row.externalId,
      title: row.title,
      sourceUrl: row.sourceUrl,
      cuisine: row.cuisine,
      difficulty: row.difficulty,
      activeTimeMins: row.activeTimeMins,
      totalTimeMins: row.totalTimeMins,
      notSuitableFor: (jsonDecode(row.notSuitableFor) as List).cast<String>(),
      yieldCount: row.yieldCount,
      nutrition: row.nutrition,
      instructions: (jsonDecode(row.instructions) as List)
          .map((e) => RecipeInstructionStep.fromJson(e as Map<String, dynamic>))
          .toList(),
      lastCookedAt: row.lastCookedAt == null
          ? null
          : DateTime.parse(row.lastCookedAt!),
      dietaryFlags: const [],
    );
  }

  Future<List<RecipeView>> _attachDietaryFlags(List<RecipeView> rows) async {
    if (rows.isEmpty) return rows;
    final ids = rows.map((r) => r.id).toList();
    final flagRows = await (_db.select(
      _db.recipeDietaryFlags,
    )..where((t) => t.recipeId.isIn(ids))).get();
    final byRecipe = <int, List<String>>{};
    for (final f in flagRows) {
      byRecipe.putIfAbsent(f.recipeId, () => []).add(f.flag);
    }
    return [
      for (final r in rows) r.withDietaryFlags(byRecipe[r.id] ?? const []),
    ];
  }
}
