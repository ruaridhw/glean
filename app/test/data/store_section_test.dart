// A shopping row's store section, resolved through its ingredient. Until the catalogue supplies ingredient
// group and form, the section comes from the ingredient's category and name.
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
              category: 'oils_fats',
            ),
            AiShoppingItem(
              name: 'Smoked paprika',
              quantity: 1,
              unit: 'jar',
              category: 'spices',
            ),
            AiShoppingItem(
              name: 'Frozen peas',
              quantity: 1,
              unit: 'bag',
              category: 'legumes',
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
            category: 'legumes',
          ),
        ],
      );

      expect(
        (await sectionsByName())['Sugar snap peas'],
        isNot(StoreSection.baking),
      );
    });

    test(
      'categories without a better signal map to the section they are shelved in',
      () async {
        const byCategory = <String, StoreSection>{
          'leafy_greens': StoreSection.fruitAndVeg,
          'berries': StoreSection.fruitAndVeg,
          'red_meat': StoreSection.meatAndFish,
          'seafood': StoreSection.meatAndFish,
          'dairy': StoreSection.dairyEggsChilled,
          'eggs': StoreSection.dairyEggsChilled,
          'bread': StoreSection.bakery,
          'pasta_rice': StoreSection.pastaRiceGrains,
          'condiments': StoreSection.foodCupboard,
        };
        await shopping.addAiItems(
          userId: userId,
          items: [
            for (final entry in byCategory.entries)
              AiShoppingItem(
                name: 'item of ${entry.key}',
                quantity: 1,
                unit: 'x',
                category: entry.key,
              ),
          ],
        );

        final sections = await sectionsByName();
        expect(
          {
            for (final entry in byCategory.entries)
              'item of ${entry.key}': sections['item of ${entry.key}'],
          },
          {
            for (final entry in byCategory.entries)
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
  });
}
