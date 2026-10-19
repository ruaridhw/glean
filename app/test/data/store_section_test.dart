// A shopping row's store section, resolved through its ingredient. Until the catalogue supplies ingredient
// group and form, the section comes from the ingredient's group and name.
import 'package:drift/drift.dart' show Value;
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/models/store_section.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';

import 'fixture.dart';

void main() {
  group('Store section of a shopping row', () {
    late GleanDatabase db;
    late ShoppingRepository shopping;
    const userId = 'user-a';

    setUp(() {
      db = createTestDatabase();
      shopping = ShoppingRepository(db, IngredientsRepository(db));
    });

    tearDown(() => db.close());

    Future<Map<String, StoreSection>> sectionsByName() async => {
      for (final item in await shopping.watchAll(userId).first)
        item.name: item.section,
    };

    test(
      'oils, spices and stock land in Food Cupboard, flour and sugar in Baking, '
      'and anything frozen in Frozen',
      () async {
        await shopping.addAiItems(
          userId: userId,
          items: const <AiShoppingItem>[
            AiShoppingItem(
              name: 'Rapeseed oil',
              quantity: 1,
              unit: 'bottle',
              groupId: 'oils_and_fats',
            ),
            AiShoppingItem(
              name: 'Smoked paprika',
              quantity: 1,
              unit: 'jar',
              groupId: 'spices',
            ),
            AiShoppingItem(
              name: 'Frozen peas',
              quantity: 1,
              unit: 'bag',
              groupId: 'beans_and_pulses',
            ),
          ],
        );
        for (final name in [
          'Chicken stock cubes',
          'Plain flour',
          'Caster sugar',
          'Baking powder',
          'Frozen berries',
        ]) {
          await shopping.addManualItem(userId: userId, name: name);
        }

        expect(await sectionsByName(), {
          'Rapeseed oil': StoreSection.foodCupboard,
          'Smoked paprika': StoreSection.foodCupboard,
          'Chicken stock cubes': StoreSection.foodCupboard,
          'Plain flour': StoreSection.baking,
          'Caster sugar': StoreSection.baking,
          'Baking powder': StoreSection.baking,
          'Frozen peas': StoreSection.frozen,
          'Frozen berries': StoreSection.frozen,
        });
      },
    );

    test('a sugar snap pea is a vegetable, not baking sugar', () async {
      await shopping.addAiItems(
        userId: userId,
        items: const <AiShoppingItem>[
          AiShoppingItem(
            name: 'Sugar snap peas',
            quantity: 200,
            unit: 'g',
            groupId: 'beans_and_pulses',
          ),
        ],
      );

      expect(
        (await sectionsByName())['Sugar snap peas'],
        isNot(StoreSection.baking),
      );
    });

    test(
      'groups without a better signal map to the section they are shelved in',
      () async {
        const byGroup = <String, StoreSection>{
          'leafy_greens': StoreSection.fruitAndVeg,
          'fruit': StoreSection.fruitAndVeg,
          'red_meat': StoreSection.meatAndFish,
          'fish_and_seafood': StoreSection.meatAndFish,
          'dairy': StoreSection.dairyEggsChilled,
          'eggs': StoreSection.dairyEggsChilled,
          'bread': StoreSection.bakery,
          'pasta_and_rice': StoreSection.pastaRiceGrains,
          'sauces_and_condiments': StoreSection.foodCupboard,
          'baking': StoreSection.baking,
          'household': StoreSection.household,
          'pet': StoreSection.pet,
        };
        await shopping.addAiItems(
          userId: userId,
          items: [
            for (final entry in byGroup.entries)
              AiShoppingItem(
                name: 'item of ${entry.key}',
                quantity: 1,
                unit: 'x',
                groupId: entry.key,
              ),
          ],
        );

        final sections = await sectionsByName();
        expect(
          {
            for (final entry in byGroup.entries)
              'item of ${entry.key}': sections['item of ${entry.key}'],
          },
          {
            for (final entry in byGroup.entries)
              'item of ${entry.key}': entry.value,
          },
        );
      },
    );

    test('an item the mapping cannot place lands in Other', () async {
      await shopping.addManualItem(userId: userId, name: 'Birthday candles');

      expect((await sectionsByName())['Birthday candles'], StoreSection.other);
    });
    test(
      'moving an item sticks for its ingredient: a later row for the same '
      'ingredient lands in the chosen section, other ingredients do not move',
      () async {
        final milk = await shopping.addManualItem(userId: userId, name: 'Milk');
        await shopping.addManualItem(userId: userId, name: 'Oat milk');
        final milkIngredientId = (await shopping.watchAll(userId).first)
            .firstWhere((i) => i.id == milk)
            .ingredientId;

        await shopping.moveToSection(
          ingredientId: milkIngredientId,
          section: StoreSection.drinks,
        );
        await shopping.addManualItem(userId: userId, name: 'milk');

        final items = await shopping.watchAll(userId).first;
        expect(
          [
            for (final i in items.where((i) => i.name.toLowerCase() == 'milk'))
              i.section,
          ],
          [StoreSection.drinks, StoreSection.drinks],
        );
        expect(
          items.singleWhere((i) => i.name == 'Oat milk').section,
          StoreSection.other,
        );
      },
    );

    test(
      'moving an item whose ingredient is linked to the catalogue writes the '
      'choice into the item\'s override, keeps the override\'s other changes, '
      'and still places later rows',
      () async {
        await db
            .into(db.catalogueItems)
            .insert(
              CatalogueItemsCompanion.insert(
                id: 'milk',
                name: 'milk',
                groupId: 'dairy',
                form: 'not_applicable',
                source: 'seed',
              ),
            );
        await db
            .into(db.catalogueAliases)
            .insert(
              CatalogueAliasesCompanion.insert(
                key: 'milk',
                name: 'milk',
                itemId: 'milk',
              ),
            );
        await db
            .into(db.ingredientOverrides)
            .insert(
              IngredientOverridesCompanion.insert(
                itemId: 'milk',
                unopenedShelfLifeDays: const Value(4),
              ),
            );
        final row = await shopping.addManualItem(userId: userId, name: 'Milk');
        final ingredientId = (await shopping.watchAll(userId).first)
            .firstWhere((i) => i.id == row)
            .ingredientId;

        await shopping.moveToSection(
          ingredientId: ingredientId,
          section: StoreSection.drinks,
        );
        await shopping.addManualItem(userId: userId, name: 'milk');

        final override = await (db.select(
          db.ingredientOverrides,
        )..where((t) => t.itemId.equals('milk'))).getSingle();
        expect(
          (override.section, override.unopenedShelfLifeDays),
          ('Drinks', 4),
        );
        expect(
          (await (db.select(
            db.ingredients,
          )..where((t) => t.id.equals(ingredientId))).getSingle()).storeSection,
          isNull,
        );
        expect(
          [for (final i in await shopping.watchAll(userId).first) i.section],
          [StoreSection.drinks, StoreSection.drinks],
        );
      },
    );

    test(
      'moving an item whose ingredient is not linked keeps the choice on '
      'the ingredient, and linking it later carries the choice over',
      () async {
        final row = await shopping.addManualItem(userId: userId, name: 'Milk');
        final ingredientId = (await shopping.watchAll(userId).first)
            .firstWhere((i) => i.id == row)
            .ingredientId;
        await shopping.moveToSection(
          ingredientId: ingredientId,
          section: StoreSection.drinks,
        );
        expect(await db.select(db.ingredientOverrides).get(), isEmpty);

        await db
            .into(db.catalogueItems)
            .insert(
              CatalogueItemsCompanion.insert(
                id: 'milk',
                name: 'milk',
                groupId: 'dairy',
                form: 'not_applicable',
                source: 'seed',
              ),
            );
        await db
            .into(db.catalogueAliases)
            .insert(
              CatalogueAliasesCompanion.insert(
                key: 'milk',
                name: 'milk',
                itemId: 'milk',
              ),
            );
        await db.linkIngredientsToCatalogue();

        expect(
          (await db.select(db.ingredientOverrides).getSingle()).section,
          'Drinks',
        );
        expect(
          (await shopping.watchAll(userId).first).single.section,
          StoreSection.drinks,
        );
      },
    );
  });
}
