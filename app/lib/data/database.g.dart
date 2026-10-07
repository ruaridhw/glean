// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'database.dart';

// ignore_for_file: type=lint
class $IngredientCategoriesTable extends IngredientCategories
    with TableInfo<$IngredientCategoriesTable, IngredientCategory> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $IngredientCategoriesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _categoryMeta = const VerificationMeta(
    'category',
  );
  @override
  late final GeneratedColumn<String> category = GeneratedColumn<String>(
    'category',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _foodGroupMeta = const VerificationMeta(
    'foodGroup',
  );
  @override
  late final GeneratedColumn<String> foodGroup = GeneratedColumn<String>(
    'food_group',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _shelfLifeDaysMeta = const VerificationMeta(
    'shelfLifeDays',
  );
  @override
  late final GeneratedColumn<int> shelfLifeDays = GeneratedColumn<int>(
    'shelf_life_days',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [category, foodGroup, shelfLifeDays];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'ingredient_categories';
  @override
  VerificationContext validateIntegrity(
    Insertable<IngredientCategory> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('category')) {
      context.handle(
        _categoryMeta,
        category.isAcceptableOrUnknown(data['category']!, _categoryMeta),
      );
    } else if (isInserting) {
      context.missing(_categoryMeta);
    }
    if (data.containsKey('food_group')) {
      context.handle(
        _foodGroupMeta,
        foodGroup.isAcceptableOrUnknown(data['food_group']!, _foodGroupMeta),
      );
    } else if (isInserting) {
      context.missing(_foodGroupMeta);
    }
    if (data.containsKey('shelf_life_days')) {
      context.handle(
        _shelfLifeDaysMeta,
        shelfLifeDays.isAcceptableOrUnknown(
          data['shelf_life_days']!,
          _shelfLifeDaysMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_shelfLifeDaysMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {category};
  @override
  IngredientCategory map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return IngredientCategory(
      category: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}category'],
      )!,
      foodGroup: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}food_group'],
      )!,
      shelfLifeDays: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}shelf_life_days'],
      )!,
    );
  }

  @override
  $IngredientCategoriesTable createAlias(String alias) {
    return $IngredientCategoriesTable(attachedDatabase, alias);
  }
}

class IngredientCategory extends DataClass
    implements Insertable<IngredientCategory> {
  final String category;
  final String foodGroup;
  final int shelfLifeDays;
  const IngredientCategory({
    required this.category,
    required this.foodGroup,
    required this.shelfLifeDays,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['category'] = Variable<String>(category);
    map['food_group'] = Variable<String>(foodGroup);
    map['shelf_life_days'] = Variable<int>(shelfLifeDays);
    return map;
  }

  IngredientCategoriesCompanion toCompanion(bool nullToAbsent) {
    return IngredientCategoriesCompanion(
      category: Value(category),
      foodGroup: Value(foodGroup),
      shelfLifeDays: Value(shelfLifeDays),
    );
  }

  factory IngredientCategory.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return IngredientCategory(
      category: serializer.fromJson<String>(json['category']),
      foodGroup: serializer.fromJson<String>(json['foodGroup']),
      shelfLifeDays: serializer.fromJson<int>(json['shelfLifeDays']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'category': serializer.toJson<String>(category),
      'foodGroup': serializer.toJson<String>(foodGroup),
      'shelfLifeDays': serializer.toJson<int>(shelfLifeDays),
    };
  }

  IngredientCategory copyWith({
    String? category,
    String? foodGroup,
    int? shelfLifeDays,
  }) => IngredientCategory(
    category: category ?? this.category,
    foodGroup: foodGroup ?? this.foodGroup,
    shelfLifeDays: shelfLifeDays ?? this.shelfLifeDays,
  );
  IngredientCategory copyWithCompanion(IngredientCategoriesCompanion data) {
    return IngredientCategory(
      category: data.category.present ? data.category.value : this.category,
      foodGroup: data.foodGroup.present ? data.foodGroup.value : this.foodGroup,
      shelfLifeDays: data.shelfLifeDays.present
          ? data.shelfLifeDays.value
          : this.shelfLifeDays,
    );
  }

  @override
  String toString() {
    return (StringBuffer('IngredientCategory(')
          ..write('category: $category, ')
          ..write('foodGroup: $foodGroup, ')
          ..write('shelfLifeDays: $shelfLifeDays')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(category, foodGroup, shelfLifeDays);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is IngredientCategory &&
          other.category == this.category &&
          other.foodGroup == this.foodGroup &&
          other.shelfLifeDays == this.shelfLifeDays);
}

class IngredientCategoriesCompanion
    extends UpdateCompanion<IngredientCategory> {
  final Value<String> category;
  final Value<String> foodGroup;
  final Value<int> shelfLifeDays;
  final Value<int> rowid;
  const IngredientCategoriesCompanion({
    this.category = const Value.absent(),
    this.foodGroup = const Value.absent(),
    this.shelfLifeDays = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  IngredientCategoriesCompanion.insert({
    required String category,
    required String foodGroup,
    required int shelfLifeDays,
    this.rowid = const Value.absent(),
  }) : category = Value(category),
       foodGroup = Value(foodGroup),
       shelfLifeDays = Value(shelfLifeDays);
  static Insertable<IngredientCategory> custom({
    Expression<String>? category,
    Expression<String>? foodGroup,
    Expression<int>? shelfLifeDays,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (category != null) 'category': category,
      if (foodGroup != null) 'food_group': foodGroup,
      if (shelfLifeDays != null) 'shelf_life_days': shelfLifeDays,
      if (rowid != null) 'rowid': rowid,
    });
  }

  IngredientCategoriesCompanion copyWith({
    Value<String>? category,
    Value<String>? foodGroup,
    Value<int>? shelfLifeDays,
    Value<int>? rowid,
  }) {
    return IngredientCategoriesCompanion(
      category: category ?? this.category,
      foodGroup: foodGroup ?? this.foodGroup,
      shelfLifeDays: shelfLifeDays ?? this.shelfLifeDays,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (category.present) {
      map['category'] = Variable<String>(category.value);
    }
    if (foodGroup.present) {
      map['food_group'] = Variable<String>(foodGroup.value);
    }
    if (shelfLifeDays.present) {
      map['shelf_life_days'] = Variable<int>(shelfLifeDays.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('IngredientCategoriesCompanion(')
          ..write('category: $category, ')
          ..write('foodGroup: $foodGroup, ')
          ..write('shelfLifeDays: $shelfLifeDays, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $IngredientsTable extends Ingredients
    with TableInfo<$IngredientsTable, Ingredient> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $IngredientsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _canonicalNameMeta = const VerificationMeta(
    'canonicalName',
  );
  @override
  late final GeneratedColumn<String> canonicalName = GeneratedColumn<String>(
    'canonical_name',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways('UNIQUE'),
  );
  static const VerificationMeta _apiIngredientIdMeta = const VerificationMeta(
    'apiIngredientId',
  );
  @override
  late final GeneratedColumn<String> apiIngredientId = GeneratedColumn<String>(
    'api_ingredient_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _apiNameMeta = const VerificationMeta(
    'apiName',
  );
  @override
  late final GeneratedColumn<String> apiName = GeneratedColumn<String>(
    'api_name',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _categoryMeta = const VerificationMeta(
    'category',
  );
  @override
  late final GeneratedColumn<String> category = GeneratedColumn<String>(
    'category',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES ingredient_categories (category)',
    ),
  );
  static const VerificationMeta _canonicalUnitMeta = const VerificationMeta(
    'canonicalUnit',
  );
  @override
  late final GeneratedColumn<String> canonicalUnit = GeneratedColumn<String>(
    'canonical_unit',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _isStapleMeta = const VerificationMeta(
    'isStaple',
  );
  @override
  late final GeneratedColumn<bool> isStaple = GeneratedColumn<bool>(
    'is_staple',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("is_staple" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    canonicalName,
    apiIngredientId,
    apiName,
    category,
    canonicalUnit,
    isStaple,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'ingredients';
  @override
  VerificationContext validateIntegrity(
    Insertable<Ingredient> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('canonical_name')) {
      context.handle(
        _canonicalNameMeta,
        canonicalName.isAcceptableOrUnknown(
          data['canonical_name']!,
          _canonicalNameMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_canonicalNameMeta);
    }
    if (data.containsKey('api_ingredient_id')) {
      context.handle(
        _apiIngredientIdMeta,
        apiIngredientId.isAcceptableOrUnknown(
          data['api_ingredient_id']!,
          _apiIngredientIdMeta,
        ),
      );
    }
    if (data.containsKey('api_name')) {
      context.handle(
        _apiNameMeta,
        apiName.isAcceptableOrUnknown(data['api_name']!, _apiNameMeta),
      );
    }
    if (data.containsKey('category')) {
      context.handle(
        _categoryMeta,
        category.isAcceptableOrUnknown(data['category']!, _categoryMeta),
      );
    }
    if (data.containsKey('canonical_unit')) {
      context.handle(
        _canonicalUnitMeta,
        canonicalUnit.isAcceptableOrUnknown(
          data['canonical_unit']!,
          _canonicalUnitMeta,
        ),
      );
    }
    if (data.containsKey('is_staple')) {
      context.handle(
        _isStapleMeta,
        isStaple.isAcceptableOrUnknown(data['is_staple']!, _isStapleMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  Ingredient map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Ingredient(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      canonicalName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}canonical_name'],
      )!,
      apiIngredientId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}api_ingredient_id'],
      ),
      apiName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}api_name'],
      ),
      category: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}category'],
      ),
      canonicalUnit: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}canonical_unit'],
      ),
      isStaple: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}is_staple'],
      )!,
    );
  }

  @override
  $IngredientsTable createAlias(String alias) {
    return $IngredientsTable(attachedDatabase, alias);
  }
}

class Ingredient extends DataClass implements Insertable<Ingredient> {
  final int id;
  final String canonicalName;
  final String? apiIngredientId;
  final String? apiName;
  final String? category;
  final String? canonicalUnit;
  final bool isStaple;
  const Ingredient({
    required this.id,
    required this.canonicalName,
    this.apiIngredientId,
    this.apiName,
    this.category,
    this.canonicalUnit,
    required this.isStaple,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['canonical_name'] = Variable<String>(canonicalName);
    if (!nullToAbsent || apiIngredientId != null) {
      map['api_ingredient_id'] = Variable<String>(apiIngredientId);
    }
    if (!nullToAbsent || apiName != null) {
      map['api_name'] = Variable<String>(apiName);
    }
    if (!nullToAbsent || category != null) {
      map['category'] = Variable<String>(category);
    }
    if (!nullToAbsent || canonicalUnit != null) {
      map['canonical_unit'] = Variable<String>(canonicalUnit);
    }
    map['is_staple'] = Variable<bool>(isStaple);
    return map;
  }

  IngredientsCompanion toCompanion(bool nullToAbsent) {
    return IngredientsCompanion(
      id: Value(id),
      canonicalName: Value(canonicalName),
      apiIngredientId: apiIngredientId == null && nullToAbsent
          ? const Value.absent()
          : Value(apiIngredientId),
      apiName: apiName == null && nullToAbsent
          ? const Value.absent()
          : Value(apiName),
      category: category == null && nullToAbsent
          ? const Value.absent()
          : Value(category),
      canonicalUnit: canonicalUnit == null && nullToAbsent
          ? const Value.absent()
          : Value(canonicalUnit),
      isStaple: Value(isStaple),
    );
  }

  factory Ingredient.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Ingredient(
      id: serializer.fromJson<int>(json['id']),
      canonicalName: serializer.fromJson<String>(json['canonicalName']),
      apiIngredientId: serializer.fromJson<String?>(json['apiIngredientId']),
      apiName: serializer.fromJson<String?>(json['apiName']),
      category: serializer.fromJson<String?>(json['category']),
      canonicalUnit: serializer.fromJson<String?>(json['canonicalUnit']),
      isStaple: serializer.fromJson<bool>(json['isStaple']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'canonicalName': serializer.toJson<String>(canonicalName),
      'apiIngredientId': serializer.toJson<String?>(apiIngredientId),
      'apiName': serializer.toJson<String?>(apiName),
      'category': serializer.toJson<String?>(category),
      'canonicalUnit': serializer.toJson<String?>(canonicalUnit),
      'isStaple': serializer.toJson<bool>(isStaple),
    };
  }

  Ingredient copyWith({
    int? id,
    String? canonicalName,
    Value<String?> apiIngredientId = const Value.absent(),
    Value<String?> apiName = const Value.absent(),
    Value<String?> category = const Value.absent(),
    Value<String?> canonicalUnit = const Value.absent(),
    bool? isStaple,
  }) => Ingredient(
    id: id ?? this.id,
    canonicalName: canonicalName ?? this.canonicalName,
    apiIngredientId: apiIngredientId.present
        ? apiIngredientId.value
        : this.apiIngredientId,
    apiName: apiName.present ? apiName.value : this.apiName,
    category: category.present ? category.value : this.category,
    canonicalUnit: canonicalUnit.present
        ? canonicalUnit.value
        : this.canonicalUnit,
    isStaple: isStaple ?? this.isStaple,
  );
  Ingredient copyWithCompanion(IngredientsCompanion data) {
    return Ingredient(
      id: data.id.present ? data.id.value : this.id,
      canonicalName: data.canonicalName.present
          ? data.canonicalName.value
          : this.canonicalName,
      apiIngredientId: data.apiIngredientId.present
          ? data.apiIngredientId.value
          : this.apiIngredientId,
      apiName: data.apiName.present ? data.apiName.value : this.apiName,
      category: data.category.present ? data.category.value : this.category,
      canonicalUnit: data.canonicalUnit.present
          ? data.canonicalUnit.value
          : this.canonicalUnit,
      isStaple: data.isStaple.present ? data.isStaple.value : this.isStaple,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Ingredient(')
          ..write('id: $id, ')
          ..write('canonicalName: $canonicalName, ')
          ..write('apiIngredientId: $apiIngredientId, ')
          ..write('apiName: $apiName, ')
          ..write('category: $category, ')
          ..write('canonicalUnit: $canonicalUnit, ')
          ..write('isStaple: $isStaple')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    canonicalName,
    apiIngredientId,
    apiName,
    category,
    canonicalUnit,
    isStaple,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Ingredient &&
          other.id == this.id &&
          other.canonicalName == this.canonicalName &&
          other.apiIngredientId == this.apiIngredientId &&
          other.apiName == this.apiName &&
          other.category == this.category &&
          other.canonicalUnit == this.canonicalUnit &&
          other.isStaple == this.isStaple);
}

class IngredientsCompanion extends UpdateCompanion<Ingredient> {
  final Value<int> id;
  final Value<String> canonicalName;
  final Value<String?> apiIngredientId;
  final Value<String?> apiName;
  final Value<String?> category;
  final Value<String?> canonicalUnit;
  final Value<bool> isStaple;
  const IngredientsCompanion({
    this.id = const Value.absent(),
    this.canonicalName = const Value.absent(),
    this.apiIngredientId = const Value.absent(),
    this.apiName = const Value.absent(),
    this.category = const Value.absent(),
    this.canonicalUnit = const Value.absent(),
    this.isStaple = const Value.absent(),
  });
  IngredientsCompanion.insert({
    this.id = const Value.absent(),
    required String canonicalName,
    this.apiIngredientId = const Value.absent(),
    this.apiName = const Value.absent(),
    this.category = const Value.absent(),
    this.canonicalUnit = const Value.absent(),
    this.isStaple = const Value.absent(),
  }) : canonicalName = Value(canonicalName);
  static Insertable<Ingredient> custom({
    Expression<int>? id,
    Expression<String>? canonicalName,
    Expression<String>? apiIngredientId,
    Expression<String>? apiName,
    Expression<String>? category,
    Expression<String>? canonicalUnit,
    Expression<bool>? isStaple,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (canonicalName != null) 'canonical_name': canonicalName,
      if (apiIngredientId != null) 'api_ingredient_id': apiIngredientId,
      if (apiName != null) 'api_name': apiName,
      if (category != null) 'category': category,
      if (canonicalUnit != null) 'canonical_unit': canonicalUnit,
      if (isStaple != null) 'is_staple': isStaple,
    });
  }

  IngredientsCompanion copyWith({
    Value<int>? id,
    Value<String>? canonicalName,
    Value<String?>? apiIngredientId,
    Value<String?>? apiName,
    Value<String?>? category,
    Value<String?>? canonicalUnit,
    Value<bool>? isStaple,
  }) {
    return IngredientsCompanion(
      id: id ?? this.id,
      canonicalName: canonicalName ?? this.canonicalName,
      apiIngredientId: apiIngredientId ?? this.apiIngredientId,
      apiName: apiName ?? this.apiName,
      category: category ?? this.category,
      canonicalUnit: canonicalUnit ?? this.canonicalUnit,
      isStaple: isStaple ?? this.isStaple,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (canonicalName.present) {
      map['canonical_name'] = Variable<String>(canonicalName.value);
    }
    if (apiIngredientId.present) {
      map['api_ingredient_id'] = Variable<String>(apiIngredientId.value);
    }
    if (apiName.present) {
      map['api_name'] = Variable<String>(apiName.value);
    }
    if (category.present) {
      map['category'] = Variable<String>(category.value);
    }
    if (canonicalUnit.present) {
      map['canonical_unit'] = Variable<String>(canonicalUnit.value);
    }
    if (isStaple.present) {
      map['is_staple'] = Variable<bool>(isStaple.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('IngredientsCompanion(')
          ..write('id: $id, ')
          ..write('canonicalName: $canonicalName, ')
          ..write('apiIngredientId: $apiIngredientId, ')
          ..write('apiName: $apiName, ')
          ..write('category: $category, ')
          ..write('canonicalUnit: $canonicalUnit, ')
          ..write('isStaple: $isStaple')
          ..write(')'))
        .toString();
  }
}

class $PantryItemsTable extends PantryItems
    with TableInfo<$PantryItemsTable, PantryItem> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $PantryItemsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _userIdMeta = const VerificationMeta('userId');
  @override
  late final GeneratedColumn<String> userId = GeneratedColumn<String>(
    'user_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _ingredientIdMeta = const VerificationMeta(
    'ingredientId',
  );
  @override
  late final GeneratedColumn<int> ingredientId = GeneratedColumn<int>(
    'ingredient_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES ingredients (id)',
    ),
  );
  static const VerificationMeta _quantityMeta = const VerificationMeta(
    'quantity',
  );
  @override
  late final GeneratedColumn<double> quantity = GeneratedColumn<double>(
    'quantity',
    aliasedName,
    false,
    type: DriftSqlType.double,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _unitMeta = const VerificationMeta('unit');
  @override
  late final GeneratedColumn<String> unit = GeneratedColumn<String>(
    'unit',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _unitPriceMeta = const VerificationMeta(
    'unitPrice',
  );
  @override
  late final GeneratedColumn<double> unitPrice = GeneratedColumn<double>(
    'unit_price',
    aliasedName,
    true,
    type: DriftSqlType.double,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _expiryDateMeta = const VerificationMeta(
    'expiryDate',
  );
  @override
  late final GeneratedColumn<String> expiryDate = GeneratedColumn<String>(
    'expiry_date',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _lastUsedAtMeta = const VerificationMeta(
    'lastUsedAt',
  );
  @override
  late final GeneratedColumn<String> lastUsedAt = GeneratedColumn<String>(
    'last_used_at',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _updatedAtMeta = const VerificationMeta(
    'updatedAt',
  );
  @override
  late final GeneratedColumn<String> updatedAt = GeneratedColumn<String>(
    'updated_at',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    userId,
    ingredientId,
    quantity,
    unit,
    unitPrice,
    expiryDate,
    lastUsedAt,
    updatedAt,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'pantry_items';
  @override
  VerificationContext validateIntegrity(
    Insertable<PantryItem> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('user_id')) {
      context.handle(
        _userIdMeta,
        userId.isAcceptableOrUnknown(data['user_id']!, _userIdMeta),
      );
    } else if (isInserting) {
      context.missing(_userIdMeta);
    }
    if (data.containsKey('ingredient_id')) {
      context.handle(
        _ingredientIdMeta,
        ingredientId.isAcceptableOrUnknown(
          data['ingredient_id']!,
          _ingredientIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_ingredientIdMeta);
    }
    if (data.containsKey('quantity')) {
      context.handle(
        _quantityMeta,
        quantity.isAcceptableOrUnknown(data['quantity']!, _quantityMeta),
      );
    } else if (isInserting) {
      context.missing(_quantityMeta);
    }
    if (data.containsKey('unit')) {
      context.handle(
        _unitMeta,
        unit.isAcceptableOrUnknown(data['unit']!, _unitMeta),
      );
    } else if (isInserting) {
      context.missing(_unitMeta);
    }
    if (data.containsKey('unit_price')) {
      context.handle(
        _unitPriceMeta,
        unitPrice.isAcceptableOrUnknown(data['unit_price']!, _unitPriceMeta),
      );
    }
    if (data.containsKey('expiry_date')) {
      context.handle(
        _expiryDateMeta,
        expiryDate.isAcceptableOrUnknown(data['expiry_date']!, _expiryDateMeta),
      );
    }
    if (data.containsKey('last_used_at')) {
      context.handle(
        _lastUsedAtMeta,
        lastUsedAt.isAcceptableOrUnknown(
          data['last_used_at']!,
          _lastUsedAtMeta,
        ),
      );
    }
    if (data.containsKey('updated_at')) {
      context.handle(
        _updatedAtMeta,
        updatedAt.isAcceptableOrUnknown(data['updated_at']!, _updatedAtMeta),
      );
    } else if (isInserting) {
      context.missing(_updatedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  List<Set<GeneratedColumn>> get uniqueKeys => [
    {userId, ingredientId},
  ];
  @override
  PantryItem map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return PantryItem(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      userId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}user_id'],
      )!,
      ingredientId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}ingredient_id'],
      )!,
      quantity: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}quantity'],
      )!,
      unit: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}unit'],
      )!,
      unitPrice: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}unit_price'],
      ),
      expiryDate: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}expiry_date'],
      ),
      lastUsedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}last_used_at'],
      ),
      updatedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}updated_at'],
      )!,
    );
  }

  @override
  $PantryItemsTable createAlias(String alias) {
    return $PantryItemsTable(attachedDatabase, alias);
  }
}

class PantryItem extends DataClass implements Insertable<PantryItem> {
  final int id;
  final String userId;
  final int ingredientId;
  final double quantity;
  final String unit;
  final double? unitPrice;
  final String? expiryDate;
  final String? lastUsedAt;
  final String updatedAt;
  const PantryItem({
    required this.id,
    required this.userId,
    required this.ingredientId,
    required this.quantity,
    required this.unit,
    this.unitPrice,
    this.expiryDate,
    this.lastUsedAt,
    required this.updatedAt,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['user_id'] = Variable<String>(userId);
    map['ingredient_id'] = Variable<int>(ingredientId);
    map['quantity'] = Variable<double>(quantity);
    map['unit'] = Variable<String>(unit);
    if (!nullToAbsent || unitPrice != null) {
      map['unit_price'] = Variable<double>(unitPrice);
    }
    if (!nullToAbsent || expiryDate != null) {
      map['expiry_date'] = Variable<String>(expiryDate);
    }
    if (!nullToAbsent || lastUsedAt != null) {
      map['last_used_at'] = Variable<String>(lastUsedAt);
    }
    map['updated_at'] = Variable<String>(updatedAt);
    return map;
  }

  PantryItemsCompanion toCompanion(bool nullToAbsent) {
    return PantryItemsCompanion(
      id: Value(id),
      userId: Value(userId),
      ingredientId: Value(ingredientId),
      quantity: Value(quantity),
      unit: Value(unit),
      unitPrice: unitPrice == null && nullToAbsent
          ? const Value.absent()
          : Value(unitPrice),
      expiryDate: expiryDate == null && nullToAbsent
          ? const Value.absent()
          : Value(expiryDate),
      lastUsedAt: lastUsedAt == null && nullToAbsent
          ? const Value.absent()
          : Value(lastUsedAt),
      updatedAt: Value(updatedAt),
    );
  }

  factory PantryItem.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return PantryItem(
      id: serializer.fromJson<int>(json['id']),
      userId: serializer.fromJson<String>(json['userId']),
      ingredientId: serializer.fromJson<int>(json['ingredientId']),
      quantity: serializer.fromJson<double>(json['quantity']),
      unit: serializer.fromJson<String>(json['unit']),
      unitPrice: serializer.fromJson<double?>(json['unitPrice']),
      expiryDate: serializer.fromJson<String?>(json['expiryDate']),
      lastUsedAt: serializer.fromJson<String?>(json['lastUsedAt']),
      updatedAt: serializer.fromJson<String>(json['updatedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'userId': serializer.toJson<String>(userId),
      'ingredientId': serializer.toJson<int>(ingredientId),
      'quantity': serializer.toJson<double>(quantity),
      'unit': serializer.toJson<String>(unit),
      'unitPrice': serializer.toJson<double?>(unitPrice),
      'expiryDate': serializer.toJson<String?>(expiryDate),
      'lastUsedAt': serializer.toJson<String?>(lastUsedAt),
      'updatedAt': serializer.toJson<String>(updatedAt),
    };
  }

  PantryItem copyWith({
    int? id,
    String? userId,
    int? ingredientId,
    double? quantity,
    String? unit,
    Value<double?> unitPrice = const Value.absent(),
    Value<String?> expiryDate = const Value.absent(),
    Value<String?> lastUsedAt = const Value.absent(),
    String? updatedAt,
  }) => PantryItem(
    id: id ?? this.id,
    userId: userId ?? this.userId,
    ingredientId: ingredientId ?? this.ingredientId,
    quantity: quantity ?? this.quantity,
    unit: unit ?? this.unit,
    unitPrice: unitPrice.present ? unitPrice.value : this.unitPrice,
    expiryDate: expiryDate.present ? expiryDate.value : this.expiryDate,
    lastUsedAt: lastUsedAt.present ? lastUsedAt.value : this.lastUsedAt,
    updatedAt: updatedAt ?? this.updatedAt,
  );
  PantryItem copyWithCompanion(PantryItemsCompanion data) {
    return PantryItem(
      id: data.id.present ? data.id.value : this.id,
      userId: data.userId.present ? data.userId.value : this.userId,
      ingredientId: data.ingredientId.present
          ? data.ingredientId.value
          : this.ingredientId,
      quantity: data.quantity.present ? data.quantity.value : this.quantity,
      unit: data.unit.present ? data.unit.value : this.unit,
      unitPrice: data.unitPrice.present ? data.unitPrice.value : this.unitPrice,
      expiryDate: data.expiryDate.present
          ? data.expiryDate.value
          : this.expiryDate,
      lastUsedAt: data.lastUsedAt.present
          ? data.lastUsedAt.value
          : this.lastUsedAt,
      updatedAt: data.updatedAt.present ? data.updatedAt.value : this.updatedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('PantryItem(')
          ..write('id: $id, ')
          ..write('userId: $userId, ')
          ..write('ingredientId: $ingredientId, ')
          ..write('quantity: $quantity, ')
          ..write('unit: $unit, ')
          ..write('unitPrice: $unitPrice, ')
          ..write('expiryDate: $expiryDate, ')
          ..write('lastUsedAt: $lastUsedAt, ')
          ..write('updatedAt: $updatedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    userId,
    ingredientId,
    quantity,
    unit,
    unitPrice,
    expiryDate,
    lastUsedAt,
    updatedAt,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is PantryItem &&
          other.id == this.id &&
          other.userId == this.userId &&
          other.ingredientId == this.ingredientId &&
          other.quantity == this.quantity &&
          other.unit == this.unit &&
          other.unitPrice == this.unitPrice &&
          other.expiryDate == this.expiryDate &&
          other.lastUsedAt == this.lastUsedAt &&
          other.updatedAt == this.updatedAt);
}

class PantryItemsCompanion extends UpdateCompanion<PantryItem> {
  final Value<int> id;
  final Value<String> userId;
  final Value<int> ingredientId;
  final Value<double> quantity;
  final Value<String> unit;
  final Value<double?> unitPrice;
  final Value<String?> expiryDate;
  final Value<String?> lastUsedAt;
  final Value<String> updatedAt;
  const PantryItemsCompanion({
    this.id = const Value.absent(),
    this.userId = const Value.absent(),
    this.ingredientId = const Value.absent(),
    this.quantity = const Value.absent(),
    this.unit = const Value.absent(),
    this.unitPrice = const Value.absent(),
    this.expiryDate = const Value.absent(),
    this.lastUsedAt = const Value.absent(),
    this.updatedAt = const Value.absent(),
  });
  PantryItemsCompanion.insert({
    this.id = const Value.absent(),
    required String userId,
    required int ingredientId,
    required double quantity,
    required String unit,
    this.unitPrice = const Value.absent(),
    this.expiryDate = const Value.absent(),
    this.lastUsedAt = const Value.absent(),
    required String updatedAt,
  }) : userId = Value(userId),
       ingredientId = Value(ingredientId),
       quantity = Value(quantity),
       unit = Value(unit),
       updatedAt = Value(updatedAt);
  static Insertable<PantryItem> custom({
    Expression<int>? id,
    Expression<String>? userId,
    Expression<int>? ingredientId,
    Expression<double>? quantity,
    Expression<String>? unit,
    Expression<double>? unitPrice,
    Expression<String>? expiryDate,
    Expression<String>? lastUsedAt,
    Expression<String>? updatedAt,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (userId != null) 'user_id': userId,
      if (ingredientId != null) 'ingredient_id': ingredientId,
      if (quantity != null) 'quantity': quantity,
      if (unit != null) 'unit': unit,
      if (unitPrice != null) 'unit_price': unitPrice,
      if (expiryDate != null) 'expiry_date': expiryDate,
      if (lastUsedAt != null) 'last_used_at': lastUsedAt,
      if (updatedAt != null) 'updated_at': updatedAt,
    });
  }

  PantryItemsCompanion copyWith({
    Value<int>? id,
    Value<String>? userId,
    Value<int>? ingredientId,
    Value<double>? quantity,
    Value<String>? unit,
    Value<double?>? unitPrice,
    Value<String?>? expiryDate,
    Value<String?>? lastUsedAt,
    Value<String>? updatedAt,
  }) {
    return PantryItemsCompanion(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      ingredientId: ingredientId ?? this.ingredientId,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      unitPrice: unitPrice ?? this.unitPrice,
      expiryDate: expiryDate ?? this.expiryDate,
      lastUsedAt: lastUsedAt ?? this.lastUsedAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (userId.present) {
      map['user_id'] = Variable<String>(userId.value);
    }
    if (ingredientId.present) {
      map['ingredient_id'] = Variable<int>(ingredientId.value);
    }
    if (quantity.present) {
      map['quantity'] = Variable<double>(quantity.value);
    }
    if (unit.present) {
      map['unit'] = Variable<String>(unit.value);
    }
    if (unitPrice.present) {
      map['unit_price'] = Variable<double>(unitPrice.value);
    }
    if (expiryDate.present) {
      map['expiry_date'] = Variable<String>(expiryDate.value);
    }
    if (lastUsedAt.present) {
      map['last_used_at'] = Variable<String>(lastUsedAt.value);
    }
    if (updatedAt.present) {
      map['updated_at'] = Variable<String>(updatedAt.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('PantryItemsCompanion(')
          ..write('id: $id, ')
          ..write('userId: $userId, ')
          ..write('ingredientId: $ingredientId, ')
          ..write('quantity: $quantity, ')
          ..write('unit: $unit, ')
          ..write('unitPrice: $unitPrice, ')
          ..write('expiryDate: $expiryDate, ')
          ..write('lastUsedAt: $lastUsedAt, ')
          ..write('updatedAt: $updatedAt')
          ..write(')'))
        .toString();
  }
}

class $RecipesTable extends Recipes with TableInfo<$RecipesTable, Recipe> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $RecipesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _userIdMeta = const VerificationMeta('userId');
  @override
  late final GeneratedColumn<String> userId = GeneratedColumn<String>(
    'user_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _externalIdMeta = const VerificationMeta(
    'externalId',
  );
  @override
  late final GeneratedColumn<String> externalId = GeneratedColumn<String>(
    'external_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _titleMeta = const VerificationMeta('title');
  @override
  late final GeneratedColumn<String> title = GeneratedColumn<String>(
    'title',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sourceUrlMeta = const VerificationMeta(
    'sourceUrl',
  );
  @override
  late final GeneratedColumn<String> sourceUrl = GeneratedColumn<String>(
    'source_url',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _cuisineMeta = const VerificationMeta(
    'cuisine',
  );
  @override
  late final GeneratedColumn<String> cuisine = GeneratedColumn<String>(
    'cuisine',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _difficultyMeta = const VerificationMeta(
    'difficulty',
  );
  @override
  late final GeneratedColumn<String> difficulty = GeneratedColumn<String>(
    'difficulty',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _activeTimeMinsMeta = const VerificationMeta(
    'activeTimeMins',
  );
  @override
  late final GeneratedColumn<int> activeTimeMins = GeneratedColumn<int>(
    'active_time_mins',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _totalTimeMinsMeta = const VerificationMeta(
    'totalTimeMins',
  );
  @override
  late final GeneratedColumn<int> totalTimeMins = GeneratedColumn<int>(
    'total_time_mins',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _notSuitableForMeta = const VerificationMeta(
    'notSuitableFor',
  );
  @override
  late final GeneratedColumn<String> notSuitableFor = GeneratedColumn<String>(
    'not_suitable_for',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('[]'),
  );
  static const VerificationMeta _yieldCountMeta = const VerificationMeta(
    'yieldCount',
  );
  @override
  late final GeneratedColumn<int> yieldCount = GeneratedColumn<int>(
    'yield_count',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _nutritionMeta = const VerificationMeta(
    'nutrition',
  );
  @override
  late final GeneratedColumn<String> nutrition = GeneratedColumn<String>(
    'nutrition',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _instructionsMeta = const VerificationMeta(
    'instructions',
  );
  @override
  late final GeneratedColumn<String> instructions = GeneratedColumn<String>(
    'instructions',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('[]'),
  );
  static const VerificationMeta _lastCookedAtMeta = const VerificationMeta(
    'lastCookedAt',
  );
  @override
  late final GeneratedColumn<String> lastCookedAt = GeneratedColumn<String>(
    'last_cooked_at',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    userId,
    externalId,
    title,
    sourceUrl,
    cuisine,
    difficulty,
    activeTimeMins,
    totalTimeMins,
    notSuitableFor,
    yieldCount,
    nutrition,
    instructions,
    lastCookedAt,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'recipes';
  @override
  VerificationContext validateIntegrity(
    Insertable<Recipe> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('user_id')) {
      context.handle(
        _userIdMeta,
        userId.isAcceptableOrUnknown(data['user_id']!, _userIdMeta),
      );
    } else if (isInserting) {
      context.missing(_userIdMeta);
    }
    if (data.containsKey('external_id')) {
      context.handle(
        _externalIdMeta,
        externalId.isAcceptableOrUnknown(data['external_id']!, _externalIdMeta),
      );
    }
    if (data.containsKey('title')) {
      context.handle(
        _titleMeta,
        title.isAcceptableOrUnknown(data['title']!, _titleMeta),
      );
    } else if (isInserting) {
      context.missing(_titleMeta);
    }
    if (data.containsKey('source_url')) {
      context.handle(
        _sourceUrlMeta,
        sourceUrl.isAcceptableOrUnknown(data['source_url']!, _sourceUrlMeta),
      );
    }
    if (data.containsKey('cuisine')) {
      context.handle(
        _cuisineMeta,
        cuisine.isAcceptableOrUnknown(data['cuisine']!, _cuisineMeta),
      );
    }
    if (data.containsKey('difficulty')) {
      context.handle(
        _difficultyMeta,
        difficulty.isAcceptableOrUnknown(data['difficulty']!, _difficultyMeta),
      );
    }
    if (data.containsKey('active_time_mins')) {
      context.handle(
        _activeTimeMinsMeta,
        activeTimeMins.isAcceptableOrUnknown(
          data['active_time_mins']!,
          _activeTimeMinsMeta,
        ),
      );
    }
    if (data.containsKey('total_time_mins')) {
      context.handle(
        _totalTimeMinsMeta,
        totalTimeMins.isAcceptableOrUnknown(
          data['total_time_mins']!,
          _totalTimeMinsMeta,
        ),
      );
    }
    if (data.containsKey('not_suitable_for')) {
      context.handle(
        _notSuitableForMeta,
        notSuitableFor.isAcceptableOrUnknown(
          data['not_suitable_for']!,
          _notSuitableForMeta,
        ),
      );
    }
    if (data.containsKey('yield_count')) {
      context.handle(
        _yieldCountMeta,
        yieldCount.isAcceptableOrUnknown(data['yield_count']!, _yieldCountMeta),
      );
    }
    if (data.containsKey('nutrition')) {
      context.handle(
        _nutritionMeta,
        nutrition.isAcceptableOrUnknown(data['nutrition']!, _nutritionMeta),
      );
    }
    if (data.containsKey('instructions')) {
      context.handle(
        _instructionsMeta,
        instructions.isAcceptableOrUnknown(
          data['instructions']!,
          _instructionsMeta,
        ),
      );
    }
    if (data.containsKey('last_cooked_at')) {
      context.handle(
        _lastCookedAtMeta,
        lastCookedAt.isAcceptableOrUnknown(
          data['last_cooked_at']!,
          _lastCookedAtMeta,
        ),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  List<Set<GeneratedColumn>> get uniqueKeys => [
    {userId, externalId},
  ];
  @override
  Recipe map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Recipe(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      userId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}user_id'],
      )!,
      externalId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}external_id'],
      ),
      title: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}title'],
      )!,
      sourceUrl: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}source_url'],
      ),
      cuisine: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}cuisine'],
      ),
      difficulty: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}difficulty'],
      ),
      activeTimeMins: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}active_time_mins'],
      ),
      totalTimeMins: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}total_time_mins'],
      ),
      notSuitableFor: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}not_suitable_for'],
      )!,
      yieldCount: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}yield_count'],
      ),
      nutrition: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}nutrition'],
      ),
      instructions: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}instructions'],
      )!,
      lastCookedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}last_cooked_at'],
      ),
    );
  }

  @override
  $RecipesTable createAlias(String alias) {
    return $RecipesTable(attachedDatabase, alias);
  }
}

class Recipe extends DataClass implements Insertable<Recipe> {
  final int id;
  final String userId;
  final String? externalId;
  final String title;
  final String? sourceUrl;
  final String? cuisine;
  final String? difficulty;
  final int? activeTimeMins;
  final int? totalTimeMins;
  final String notSuitableFor;
  final int? yieldCount;
  final String? nutrition;
  final String instructions;
  final String? lastCookedAt;
  const Recipe({
    required this.id,
    required this.userId,
    this.externalId,
    required this.title,
    this.sourceUrl,
    this.cuisine,
    this.difficulty,
    this.activeTimeMins,
    this.totalTimeMins,
    required this.notSuitableFor,
    this.yieldCount,
    this.nutrition,
    required this.instructions,
    this.lastCookedAt,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['user_id'] = Variable<String>(userId);
    if (!nullToAbsent || externalId != null) {
      map['external_id'] = Variable<String>(externalId);
    }
    map['title'] = Variable<String>(title);
    if (!nullToAbsent || sourceUrl != null) {
      map['source_url'] = Variable<String>(sourceUrl);
    }
    if (!nullToAbsent || cuisine != null) {
      map['cuisine'] = Variable<String>(cuisine);
    }
    if (!nullToAbsent || difficulty != null) {
      map['difficulty'] = Variable<String>(difficulty);
    }
    if (!nullToAbsent || activeTimeMins != null) {
      map['active_time_mins'] = Variable<int>(activeTimeMins);
    }
    if (!nullToAbsent || totalTimeMins != null) {
      map['total_time_mins'] = Variable<int>(totalTimeMins);
    }
    map['not_suitable_for'] = Variable<String>(notSuitableFor);
    if (!nullToAbsent || yieldCount != null) {
      map['yield_count'] = Variable<int>(yieldCount);
    }
    if (!nullToAbsent || nutrition != null) {
      map['nutrition'] = Variable<String>(nutrition);
    }
    map['instructions'] = Variable<String>(instructions);
    if (!nullToAbsent || lastCookedAt != null) {
      map['last_cooked_at'] = Variable<String>(lastCookedAt);
    }
    return map;
  }

  RecipesCompanion toCompanion(bool nullToAbsent) {
    return RecipesCompanion(
      id: Value(id),
      userId: Value(userId),
      externalId: externalId == null && nullToAbsent
          ? const Value.absent()
          : Value(externalId),
      title: Value(title),
      sourceUrl: sourceUrl == null && nullToAbsent
          ? const Value.absent()
          : Value(sourceUrl),
      cuisine: cuisine == null && nullToAbsent
          ? const Value.absent()
          : Value(cuisine),
      difficulty: difficulty == null && nullToAbsent
          ? const Value.absent()
          : Value(difficulty),
      activeTimeMins: activeTimeMins == null && nullToAbsent
          ? const Value.absent()
          : Value(activeTimeMins),
      totalTimeMins: totalTimeMins == null && nullToAbsent
          ? const Value.absent()
          : Value(totalTimeMins),
      notSuitableFor: Value(notSuitableFor),
      yieldCount: yieldCount == null && nullToAbsent
          ? const Value.absent()
          : Value(yieldCount),
      nutrition: nutrition == null && nullToAbsent
          ? const Value.absent()
          : Value(nutrition),
      instructions: Value(instructions),
      lastCookedAt: lastCookedAt == null && nullToAbsent
          ? const Value.absent()
          : Value(lastCookedAt),
    );
  }

  factory Recipe.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Recipe(
      id: serializer.fromJson<int>(json['id']),
      userId: serializer.fromJson<String>(json['userId']),
      externalId: serializer.fromJson<String?>(json['externalId']),
      title: serializer.fromJson<String>(json['title']),
      sourceUrl: serializer.fromJson<String?>(json['sourceUrl']),
      cuisine: serializer.fromJson<String?>(json['cuisine']),
      difficulty: serializer.fromJson<String?>(json['difficulty']),
      activeTimeMins: serializer.fromJson<int?>(json['activeTimeMins']),
      totalTimeMins: serializer.fromJson<int?>(json['totalTimeMins']),
      notSuitableFor: serializer.fromJson<String>(json['notSuitableFor']),
      yieldCount: serializer.fromJson<int?>(json['yieldCount']),
      nutrition: serializer.fromJson<String?>(json['nutrition']),
      instructions: serializer.fromJson<String>(json['instructions']),
      lastCookedAt: serializer.fromJson<String?>(json['lastCookedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'userId': serializer.toJson<String>(userId),
      'externalId': serializer.toJson<String?>(externalId),
      'title': serializer.toJson<String>(title),
      'sourceUrl': serializer.toJson<String?>(sourceUrl),
      'cuisine': serializer.toJson<String?>(cuisine),
      'difficulty': serializer.toJson<String?>(difficulty),
      'activeTimeMins': serializer.toJson<int?>(activeTimeMins),
      'totalTimeMins': serializer.toJson<int?>(totalTimeMins),
      'notSuitableFor': serializer.toJson<String>(notSuitableFor),
      'yieldCount': serializer.toJson<int?>(yieldCount),
      'nutrition': serializer.toJson<String?>(nutrition),
      'instructions': serializer.toJson<String>(instructions),
      'lastCookedAt': serializer.toJson<String?>(lastCookedAt),
    };
  }

  Recipe copyWith({
    int? id,
    String? userId,
    Value<String?> externalId = const Value.absent(),
    String? title,
    Value<String?> sourceUrl = const Value.absent(),
    Value<String?> cuisine = const Value.absent(),
    Value<String?> difficulty = const Value.absent(),
    Value<int?> activeTimeMins = const Value.absent(),
    Value<int?> totalTimeMins = const Value.absent(),
    String? notSuitableFor,
    Value<int?> yieldCount = const Value.absent(),
    Value<String?> nutrition = const Value.absent(),
    String? instructions,
    Value<String?> lastCookedAt = const Value.absent(),
  }) => Recipe(
    id: id ?? this.id,
    userId: userId ?? this.userId,
    externalId: externalId.present ? externalId.value : this.externalId,
    title: title ?? this.title,
    sourceUrl: sourceUrl.present ? sourceUrl.value : this.sourceUrl,
    cuisine: cuisine.present ? cuisine.value : this.cuisine,
    difficulty: difficulty.present ? difficulty.value : this.difficulty,
    activeTimeMins: activeTimeMins.present
        ? activeTimeMins.value
        : this.activeTimeMins,
    totalTimeMins: totalTimeMins.present
        ? totalTimeMins.value
        : this.totalTimeMins,
    notSuitableFor: notSuitableFor ?? this.notSuitableFor,
    yieldCount: yieldCount.present ? yieldCount.value : this.yieldCount,
    nutrition: nutrition.present ? nutrition.value : this.nutrition,
    instructions: instructions ?? this.instructions,
    lastCookedAt: lastCookedAt.present ? lastCookedAt.value : this.lastCookedAt,
  );
  Recipe copyWithCompanion(RecipesCompanion data) {
    return Recipe(
      id: data.id.present ? data.id.value : this.id,
      userId: data.userId.present ? data.userId.value : this.userId,
      externalId: data.externalId.present
          ? data.externalId.value
          : this.externalId,
      title: data.title.present ? data.title.value : this.title,
      sourceUrl: data.sourceUrl.present ? data.sourceUrl.value : this.sourceUrl,
      cuisine: data.cuisine.present ? data.cuisine.value : this.cuisine,
      difficulty: data.difficulty.present
          ? data.difficulty.value
          : this.difficulty,
      activeTimeMins: data.activeTimeMins.present
          ? data.activeTimeMins.value
          : this.activeTimeMins,
      totalTimeMins: data.totalTimeMins.present
          ? data.totalTimeMins.value
          : this.totalTimeMins,
      notSuitableFor: data.notSuitableFor.present
          ? data.notSuitableFor.value
          : this.notSuitableFor,
      yieldCount: data.yieldCount.present
          ? data.yieldCount.value
          : this.yieldCount,
      nutrition: data.nutrition.present ? data.nutrition.value : this.nutrition,
      instructions: data.instructions.present
          ? data.instructions.value
          : this.instructions,
      lastCookedAt: data.lastCookedAt.present
          ? data.lastCookedAt.value
          : this.lastCookedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Recipe(')
          ..write('id: $id, ')
          ..write('userId: $userId, ')
          ..write('externalId: $externalId, ')
          ..write('title: $title, ')
          ..write('sourceUrl: $sourceUrl, ')
          ..write('cuisine: $cuisine, ')
          ..write('difficulty: $difficulty, ')
          ..write('activeTimeMins: $activeTimeMins, ')
          ..write('totalTimeMins: $totalTimeMins, ')
          ..write('notSuitableFor: $notSuitableFor, ')
          ..write('yieldCount: $yieldCount, ')
          ..write('nutrition: $nutrition, ')
          ..write('instructions: $instructions, ')
          ..write('lastCookedAt: $lastCookedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    userId,
    externalId,
    title,
    sourceUrl,
    cuisine,
    difficulty,
    activeTimeMins,
    totalTimeMins,
    notSuitableFor,
    yieldCount,
    nutrition,
    instructions,
    lastCookedAt,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Recipe &&
          other.id == this.id &&
          other.userId == this.userId &&
          other.externalId == this.externalId &&
          other.title == this.title &&
          other.sourceUrl == this.sourceUrl &&
          other.cuisine == this.cuisine &&
          other.difficulty == this.difficulty &&
          other.activeTimeMins == this.activeTimeMins &&
          other.totalTimeMins == this.totalTimeMins &&
          other.notSuitableFor == this.notSuitableFor &&
          other.yieldCount == this.yieldCount &&
          other.nutrition == this.nutrition &&
          other.instructions == this.instructions &&
          other.lastCookedAt == this.lastCookedAt);
}

class RecipesCompanion extends UpdateCompanion<Recipe> {
  final Value<int> id;
  final Value<String> userId;
  final Value<String?> externalId;
  final Value<String> title;
  final Value<String?> sourceUrl;
  final Value<String?> cuisine;
  final Value<String?> difficulty;
  final Value<int?> activeTimeMins;
  final Value<int?> totalTimeMins;
  final Value<String> notSuitableFor;
  final Value<int?> yieldCount;
  final Value<String?> nutrition;
  final Value<String> instructions;
  final Value<String?> lastCookedAt;
  const RecipesCompanion({
    this.id = const Value.absent(),
    this.userId = const Value.absent(),
    this.externalId = const Value.absent(),
    this.title = const Value.absent(),
    this.sourceUrl = const Value.absent(),
    this.cuisine = const Value.absent(),
    this.difficulty = const Value.absent(),
    this.activeTimeMins = const Value.absent(),
    this.totalTimeMins = const Value.absent(),
    this.notSuitableFor = const Value.absent(),
    this.yieldCount = const Value.absent(),
    this.nutrition = const Value.absent(),
    this.instructions = const Value.absent(),
    this.lastCookedAt = const Value.absent(),
  });
  RecipesCompanion.insert({
    this.id = const Value.absent(),
    required String userId,
    this.externalId = const Value.absent(),
    required String title,
    this.sourceUrl = const Value.absent(),
    this.cuisine = const Value.absent(),
    this.difficulty = const Value.absent(),
    this.activeTimeMins = const Value.absent(),
    this.totalTimeMins = const Value.absent(),
    this.notSuitableFor = const Value.absent(),
    this.yieldCount = const Value.absent(),
    this.nutrition = const Value.absent(),
    this.instructions = const Value.absent(),
    this.lastCookedAt = const Value.absent(),
  }) : userId = Value(userId),
       title = Value(title);
  static Insertable<Recipe> custom({
    Expression<int>? id,
    Expression<String>? userId,
    Expression<String>? externalId,
    Expression<String>? title,
    Expression<String>? sourceUrl,
    Expression<String>? cuisine,
    Expression<String>? difficulty,
    Expression<int>? activeTimeMins,
    Expression<int>? totalTimeMins,
    Expression<String>? notSuitableFor,
    Expression<int>? yieldCount,
    Expression<String>? nutrition,
    Expression<String>? instructions,
    Expression<String>? lastCookedAt,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (userId != null) 'user_id': userId,
      if (externalId != null) 'external_id': externalId,
      if (title != null) 'title': title,
      if (sourceUrl != null) 'source_url': sourceUrl,
      if (cuisine != null) 'cuisine': cuisine,
      if (difficulty != null) 'difficulty': difficulty,
      if (activeTimeMins != null) 'active_time_mins': activeTimeMins,
      if (totalTimeMins != null) 'total_time_mins': totalTimeMins,
      if (notSuitableFor != null) 'not_suitable_for': notSuitableFor,
      if (yieldCount != null) 'yield_count': yieldCount,
      if (nutrition != null) 'nutrition': nutrition,
      if (instructions != null) 'instructions': instructions,
      if (lastCookedAt != null) 'last_cooked_at': lastCookedAt,
    });
  }

  RecipesCompanion copyWith({
    Value<int>? id,
    Value<String>? userId,
    Value<String?>? externalId,
    Value<String>? title,
    Value<String?>? sourceUrl,
    Value<String?>? cuisine,
    Value<String?>? difficulty,
    Value<int?>? activeTimeMins,
    Value<int?>? totalTimeMins,
    Value<String>? notSuitableFor,
    Value<int?>? yieldCount,
    Value<String?>? nutrition,
    Value<String>? instructions,
    Value<String?>? lastCookedAt,
  }) {
    return RecipesCompanion(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      externalId: externalId ?? this.externalId,
      title: title ?? this.title,
      sourceUrl: sourceUrl ?? this.sourceUrl,
      cuisine: cuisine ?? this.cuisine,
      difficulty: difficulty ?? this.difficulty,
      activeTimeMins: activeTimeMins ?? this.activeTimeMins,
      totalTimeMins: totalTimeMins ?? this.totalTimeMins,
      notSuitableFor: notSuitableFor ?? this.notSuitableFor,
      yieldCount: yieldCount ?? this.yieldCount,
      nutrition: nutrition ?? this.nutrition,
      instructions: instructions ?? this.instructions,
      lastCookedAt: lastCookedAt ?? this.lastCookedAt,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (userId.present) {
      map['user_id'] = Variable<String>(userId.value);
    }
    if (externalId.present) {
      map['external_id'] = Variable<String>(externalId.value);
    }
    if (title.present) {
      map['title'] = Variable<String>(title.value);
    }
    if (sourceUrl.present) {
      map['source_url'] = Variable<String>(sourceUrl.value);
    }
    if (cuisine.present) {
      map['cuisine'] = Variable<String>(cuisine.value);
    }
    if (difficulty.present) {
      map['difficulty'] = Variable<String>(difficulty.value);
    }
    if (activeTimeMins.present) {
      map['active_time_mins'] = Variable<int>(activeTimeMins.value);
    }
    if (totalTimeMins.present) {
      map['total_time_mins'] = Variable<int>(totalTimeMins.value);
    }
    if (notSuitableFor.present) {
      map['not_suitable_for'] = Variable<String>(notSuitableFor.value);
    }
    if (yieldCount.present) {
      map['yield_count'] = Variable<int>(yieldCount.value);
    }
    if (nutrition.present) {
      map['nutrition'] = Variable<String>(nutrition.value);
    }
    if (instructions.present) {
      map['instructions'] = Variable<String>(instructions.value);
    }
    if (lastCookedAt.present) {
      map['last_cooked_at'] = Variable<String>(lastCookedAt.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('RecipesCompanion(')
          ..write('id: $id, ')
          ..write('userId: $userId, ')
          ..write('externalId: $externalId, ')
          ..write('title: $title, ')
          ..write('sourceUrl: $sourceUrl, ')
          ..write('cuisine: $cuisine, ')
          ..write('difficulty: $difficulty, ')
          ..write('activeTimeMins: $activeTimeMins, ')
          ..write('totalTimeMins: $totalTimeMins, ')
          ..write('notSuitableFor: $notSuitableFor, ')
          ..write('yieldCount: $yieldCount, ')
          ..write('nutrition: $nutrition, ')
          ..write('instructions: $instructions, ')
          ..write('lastCookedAt: $lastCookedAt')
          ..write(')'))
        .toString();
  }
}

class $RecipeDietaryFlagsTable extends RecipeDietaryFlags
    with TableInfo<$RecipeDietaryFlagsTable, RecipeDietaryFlag> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $RecipeDietaryFlagsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _recipeIdMeta = const VerificationMeta(
    'recipeId',
  );
  @override
  late final GeneratedColumn<int> recipeId = GeneratedColumn<int>(
    'recipe_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES recipes (id) ON DELETE CASCADE',
    ),
  );
  static const VerificationMeta _flagMeta = const VerificationMeta('flag');
  @override
  late final GeneratedColumn<String> flag = GeneratedColumn<String>(
    'flag',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [recipeId, flag];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'recipe_dietary_flags';
  @override
  VerificationContext validateIntegrity(
    Insertable<RecipeDietaryFlag> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('recipe_id')) {
      context.handle(
        _recipeIdMeta,
        recipeId.isAcceptableOrUnknown(data['recipe_id']!, _recipeIdMeta),
      );
    } else if (isInserting) {
      context.missing(_recipeIdMeta);
    }
    if (data.containsKey('flag')) {
      context.handle(
        _flagMeta,
        flag.isAcceptableOrUnknown(data['flag']!, _flagMeta),
      );
    } else if (isInserting) {
      context.missing(_flagMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {recipeId, flag};
  @override
  RecipeDietaryFlag map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return RecipeDietaryFlag(
      recipeId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}recipe_id'],
      )!,
      flag: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}flag'],
      )!,
    );
  }

  @override
  $RecipeDietaryFlagsTable createAlias(String alias) {
    return $RecipeDietaryFlagsTable(attachedDatabase, alias);
  }
}

class RecipeDietaryFlag extends DataClass
    implements Insertable<RecipeDietaryFlag> {
  final int recipeId;
  final String flag;
  const RecipeDietaryFlag({required this.recipeId, required this.flag});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['recipe_id'] = Variable<int>(recipeId);
    map['flag'] = Variable<String>(flag);
    return map;
  }

  RecipeDietaryFlagsCompanion toCompanion(bool nullToAbsent) {
    return RecipeDietaryFlagsCompanion(
      recipeId: Value(recipeId),
      flag: Value(flag),
    );
  }

  factory RecipeDietaryFlag.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return RecipeDietaryFlag(
      recipeId: serializer.fromJson<int>(json['recipeId']),
      flag: serializer.fromJson<String>(json['flag']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'recipeId': serializer.toJson<int>(recipeId),
      'flag': serializer.toJson<String>(flag),
    };
  }

  RecipeDietaryFlag copyWith({int? recipeId, String? flag}) =>
      RecipeDietaryFlag(
        recipeId: recipeId ?? this.recipeId,
        flag: flag ?? this.flag,
      );
  RecipeDietaryFlag copyWithCompanion(RecipeDietaryFlagsCompanion data) {
    return RecipeDietaryFlag(
      recipeId: data.recipeId.present ? data.recipeId.value : this.recipeId,
      flag: data.flag.present ? data.flag.value : this.flag,
    );
  }

  @override
  String toString() {
    return (StringBuffer('RecipeDietaryFlag(')
          ..write('recipeId: $recipeId, ')
          ..write('flag: $flag')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(recipeId, flag);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is RecipeDietaryFlag &&
          other.recipeId == this.recipeId &&
          other.flag == this.flag);
}

class RecipeDietaryFlagsCompanion extends UpdateCompanion<RecipeDietaryFlag> {
  final Value<int> recipeId;
  final Value<String> flag;
  final Value<int> rowid;
  const RecipeDietaryFlagsCompanion({
    this.recipeId = const Value.absent(),
    this.flag = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  RecipeDietaryFlagsCompanion.insert({
    required int recipeId,
    required String flag,
    this.rowid = const Value.absent(),
  }) : recipeId = Value(recipeId),
       flag = Value(flag);
  static Insertable<RecipeDietaryFlag> custom({
    Expression<int>? recipeId,
    Expression<String>? flag,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (recipeId != null) 'recipe_id': recipeId,
      if (flag != null) 'flag': flag,
      if (rowid != null) 'rowid': rowid,
    });
  }

  RecipeDietaryFlagsCompanion copyWith({
    Value<int>? recipeId,
    Value<String>? flag,
    Value<int>? rowid,
  }) {
    return RecipeDietaryFlagsCompanion(
      recipeId: recipeId ?? this.recipeId,
      flag: flag ?? this.flag,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (recipeId.present) {
      map['recipe_id'] = Variable<int>(recipeId.value);
    }
    if (flag.present) {
      map['flag'] = Variable<String>(flag.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('RecipeDietaryFlagsCompanion(')
          ..write('recipeId: $recipeId, ')
          ..write('flag: $flag, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $RecipeIngredientsTable extends RecipeIngredients
    with TableInfo<$RecipeIngredientsTable, RecipeIngredient> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $RecipeIngredientsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _recipeIdMeta = const VerificationMeta(
    'recipeId',
  );
  @override
  late final GeneratedColumn<int> recipeId = GeneratedColumn<int>(
    'recipe_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES recipes (id) ON DELETE CASCADE',
    ),
  );
  static const VerificationMeta _ingredientIdMeta = const VerificationMeta(
    'ingredientId',
  );
  @override
  late final GeneratedColumn<int> ingredientId = GeneratedColumn<int>(
    'ingredient_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES ingredients (id)',
    ),
  );
  static const VerificationMeta _quantityMeta = const VerificationMeta(
    'quantity',
  );
  @override
  late final GeneratedColumn<double> quantity = GeneratedColumn<double>(
    'quantity',
    aliasedName,
    false,
    type: DriftSqlType.double,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _unitMeta = const VerificationMeta('unit');
  @override
  late final GeneratedColumn<String> unit = GeneratedColumn<String>(
    'unit',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _preparationMeta = const VerificationMeta(
    'preparation',
  );
  @override
  late final GeneratedColumn<String> preparation = GeneratedColumn<String>(
    'preparation',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _isOptionalMeta = const VerificationMeta(
    'isOptional',
  );
  @override
  late final GeneratedColumn<bool> isOptional = GeneratedColumn<bool>(
    'is_optional',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("is_optional" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  static const VerificationMeta _substitutionsMeta = const VerificationMeta(
    'substitutions',
  );
  @override
  late final GeneratedColumn<String> substitutions = GeneratedColumn<String>(
    'substitutions',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('[]'),
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    recipeId,
    ingredientId,
    quantity,
    unit,
    preparation,
    isOptional,
    substitutions,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'recipe_ingredients';
  @override
  VerificationContext validateIntegrity(
    Insertable<RecipeIngredient> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('recipe_id')) {
      context.handle(
        _recipeIdMeta,
        recipeId.isAcceptableOrUnknown(data['recipe_id']!, _recipeIdMeta),
      );
    } else if (isInserting) {
      context.missing(_recipeIdMeta);
    }
    if (data.containsKey('ingredient_id')) {
      context.handle(
        _ingredientIdMeta,
        ingredientId.isAcceptableOrUnknown(
          data['ingredient_id']!,
          _ingredientIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_ingredientIdMeta);
    }
    if (data.containsKey('quantity')) {
      context.handle(
        _quantityMeta,
        quantity.isAcceptableOrUnknown(data['quantity']!, _quantityMeta),
      );
    } else if (isInserting) {
      context.missing(_quantityMeta);
    }
    if (data.containsKey('unit')) {
      context.handle(
        _unitMeta,
        unit.isAcceptableOrUnknown(data['unit']!, _unitMeta),
      );
    } else if (isInserting) {
      context.missing(_unitMeta);
    }
    if (data.containsKey('preparation')) {
      context.handle(
        _preparationMeta,
        preparation.isAcceptableOrUnknown(
          data['preparation']!,
          _preparationMeta,
        ),
      );
    }
    if (data.containsKey('is_optional')) {
      context.handle(
        _isOptionalMeta,
        isOptional.isAcceptableOrUnknown(data['is_optional']!, _isOptionalMeta),
      );
    }
    if (data.containsKey('substitutions')) {
      context.handle(
        _substitutionsMeta,
        substitutions.isAcceptableOrUnknown(
          data['substitutions']!,
          _substitutionsMeta,
        ),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  RecipeIngredient map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return RecipeIngredient(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      recipeId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}recipe_id'],
      )!,
      ingredientId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}ingredient_id'],
      )!,
      quantity: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}quantity'],
      )!,
      unit: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}unit'],
      )!,
      preparation: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}preparation'],
      ),
      isOptional: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}is_optional'],
      )!,
      substitutions: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}substitutions'],
      )!,
    );
  }

  @override
  $RecipeIngredientsTable createAlias(String alias) {
    return $RecipeIngredientsTable(attachedDatabase, alias);
  }
}

class RecipeIngredient extends DataClass
    implements Insertable<RecipeIngredient> {
  final int id;
  final int recipeId;
  final int ingredientId;
  final double quantity;
  final String unit;
  final String? preparation;
  final bool isOptional;
  final String substitutions;
  const RecipeIngredient({
    required this.id,
    required this.recipeId,
    required this.ingredientId,
    required this.quantity,
    required this.unit,
    this.preparation,
    required this.isOptional,
    required this.substitutions,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['recipe_id'] = Variable<int>(recipeId);
    map['ingredient_id'] = Variable<int>(ingredientId);
    map['quantity'] = Variable<double>(quantity);
    map['unit'] = Variable<String>(unit);
    if (!nullToAbsent || preparation != null) {
      map['preparation'] = Variable<String>(preparation);
    }
    map['is_optional'] = Variable<bool>(isOptional);
    map['substitutions'] = Variable<String>(substitutions);
    return map;
  }

  RecipeIngredientsCompanion toCompanion(bool nullToAbsent) {
    return RecipeIngredientsCompanion(
      id: Value(id),
      recipeId: Value(recipeId),
      ingredientId: Value(ingredientId),
      quantity: Value(quantity),
      unit: Value(unit),
      preparation: preparation == null && nullToAbsent
          ? const Value.absent()
          : Value(preparation),
      isOptional: Value(isOptional),
      substitutions: Value(substitutions),
    );
  }

  factory RecipeIngredient.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return RecipeIngredient(
      id: serializer.fromJson<int>(json['id']),
      recipeId: serializer.fromJson<int>(json['recipeId']),
      ingredientId: serializer.fromJson<int>(json['ingredientId']),
      quantity: serializer.fromJson<double>(json['quantity']),
      unit: serializer.fromJson<String>(json['unit']),
      preparation: serializer.fromJson<String?>(json['preparation']),
      isOptional: serializer.fromJson<bool>(json['isOptional']),
      substitutions: serializer.fromJson<String>(json['substitutions']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'recipeId': serializer.toJson<int>(recipeId),
      'ingredientId': serializer.toJson<int>(ingredientId),
      'quantity': serializer.toJson<double>(quantity),
      'unit': serializer.toJson<String>(unit),
      'preparation': serializer.toJson<String?>(preparation),
      'isOptional': serializer.toJson<bool>(isOptional),
      'substitutions': serializer.toJson<String>(substitutions),
    };
  }

  RecipeIngredient copyWith({
    int? id,
    int? recipeId,
    int? ingredientId,
    double? quantity,
    String? unit,
    Value<String?> preparation = const Value.absent(),
    bool? isOptional,
    String? substitutions,
  }) => RecipeIngredient(
    id: id ?? this.id,
    recipeId: recipeId ?? this.recipeId,
    ingredientId: ingredientId ?? this.ingredientId,
    quantity: quantity ?? this.quantity,
    unit: unit ?? this.unit,
    preparation: preparation.present ? preparation.value : this.preparation,
    isOptional: isOptional ?? this.isOptional,
    substitutions: substitutions ?? this.substitutions,
  );
  RecipeIngredient copyWithCompanion(RecipeIngredientsCompanion data) {
    return RecipeIngredient(
      id: data.id.present ? data.id.value : this.id,
      recipeId: data.recipeId.present ? data.recipeId.value : this.recipeId,
      ingredientId: data.ingredientId.present
          ? data.ingredientId.value
          : this.ingredientId,
      quantity: data.quantity.present ? data.quantity.value : this.quantity,
      unit: data.unit.present ? data.unit.value : this.unit,
      preparation: data.preparation.present
          ? data.preparation.value
          : this.preparation,
      isOptional: data.isOptional.present
          ? data.isOptional.value
          : this.isOptional,
      substitutions: data.substitutions.present
          ? data.substitutions.value
          : this.substitutions,
    );
  }

  @override
  String toString() {
    return (StringBuffer('RecipeIngredient(')
          ..write('id: $id, ')
          ..write('recipeId: $recipeId, ')
          ..write('ingredientId: $ingredientId, ')
          ..write('quantity: $quantity, ')
          ..write('unit: $unit, ')
          ..write('preparation: $preparation, ')
          ..write('isOptional: $isOptional, ')
          ..write('substitutions: $substitutions')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    recipeId,
    ingredientId,
    quantity,
    unit,
    preparation,
    isOptional,
    substitutions,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is RecipeIngredient &&
          other.id == this.id &&
          other.recipeId == this.recipeId &&
          other.ingredientId == this.ingredientId &&
          other.quantity == this.quantity &&
          other.unit == this.unit &&
          other.preparation == this.preparation &&
          other.isOptional == this.isOptional &&
          other.substitutions == this.substitutions);
}

class RecipeIngredientsCompanion extends UpdateCompanion<RecipeIngredient> {
  final Value<int> id;
  final Value<int> recipeId;
  final Value<int> ingredientId;
  final Value<double> quantity;
  final Value<String> unit;
  final Value<String?> preparation;
  final Value<bool> isOptional;
  final Value<String> substitutions;
  const RecipeIngredientsCompanion({
    this.id = const Value.absent(),
    this.recipeId = const Value.absent(),
    this.ingredientId = const Value.absent(),
    this.quantity = const Value.absent(),
    this.unit = const Value.absent(),
    this.preparation = const Value.absent(),
    this.isOptional = const Value.absent(),
    this.substitutions = const Value.absent(),
  });
  RecipeIngredientsCompanion.insert({
    this.id = const Value.absent(),
    required int recipeId,
    required int ingredientId,
    required double quantity,
    required String unit,
    this.preparation = const Value.absent(),
    this.isOptional = const Value.absent(),
    this.substitutions = const Value.absent(),
  }) : recipeId = Value(recipeId),
       ingredientId = Value(ingredientId),
       quantity = Value(quantity),
       unit = Value(unit);
  static Insertable<RecipeIngredient> custom({
    Expression<int>? id,
    Expression<int>? recipeId,
    Expression<int>? ingredientId,
    Expression<double>? quantity,
    Expression<String>? unit,
    Expression<String>? preparation,
    Expression<bool>? isOptional,
    Expression<String>? substitutions,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (recipeId != null) 'recipe_id': recipeId,
      if (ingredientId != null) 'ingredient_id': ingredientId,
      if (quantity != null) 'quantity': quantity,
      if (unit != null) 'unit': unit,
      if (preparation != null) 'preparation': preparation,
      if (isOptional != null) 'is_optional': isOptional,
      if (substitutions != null) 'substitutions': substitutions,
    });
  }

  RecipeIngredientsCompanion copyWith({
    Value<int>? id,
    Value<int>? recipeId,
    Value<int>? ingredientId,
    Value<double>? quantity,
    Value<String>? unit,
    Value<String?>? preparation,
    Value<bool>? isOptional,
    Value<String>? substitutions,
  }) {
    return RecipeIngredientsCompanion(
      id: id ?? this.id,
      recipeId: recipeId ?? this.recipeId,
      ingredientId: ingredientId ?? this.ingredientId,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      preparation: preparation ?? this.preparation,
      isOptional: isOptional ?? this.isOptional,
      substitutions: substitutions ?? this.substitutions,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (recipeId.present) {
      map['recipe_id'] = Variable<int>(recipeId.value);
    }
    if (ingredientId.present) {
      map['ingredient_id'] = Variable<int>(ingredientId.value);
    }
    if (quantity.present) {
      map['quantity'] = Variable<double>(quantity.value);
    }
    if (unit.present) {
      map['unit'] = Variable<String>(unit.value);
    }
    if (preparation.present) {
      map['preparation'] = Variable<String>(preparation.value);
    }
    if (isOptional.present) {
      map['is_optional'] = Variable<bool>(isOptional.value);
    }
    if (substitutions.present) {
      map['substitutions'] = Variable<String>(substitutions.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('RecipeIngredientsCompanion(')
          ..write('id: $id, ')
          ..write('recipeId: $recipeId, ')
          ..write('ingredientId: $ingredientId, ')
          ..write('quantity: $quantity, ')
          ..write('unit: $unit, ')
          ..write('preparation: $preparation, ')
          ..write('isOptional: $isOptional, ')
          ..write('substitutions: $substitutions')
          ..write(')'))
        .toString();
  }
}

class $MealPlanEntriesTable extends MealPlanEntries
    with TableInfo<$MealPlanEntriesTable, MealPlanEntry> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $MealPlanEntriesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _userIdMeta = const VerificationMeta('userId');
  @override
  late final GeneratedColumn<String> userId = GeneratedColumn<String>(
    'user_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _recipeIdMeta = const VerificationMeta(
    'recipeId',
  );
  @override
  late final GeneratedColumn<int> recipeId = GeneratedColumn<int>(
    'recipe_id',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES recipes (id) ON DELETE SET NULL',
    ),
  );
  static const VerificationMeta _recipeTitleMeta = const VerificationMeta(
    'recipeTitle',
  );
  @override
  late final GeneratedColumn<String> recipeTitle = GeneratedColumn<String>(
    'recipe_title',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _plannedDateMeta = const VerificationMeta(
    'plannedDate',
  );
  @override
  late final GeneratedColumn<String> plannedDate = GeneratedColumn<String>(
    'planned_date',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _cookedAtMeta = const VerificationMeta(
    'cookedAt',
  );
  @override
  late final GeneratedColumn<String> cookedAt = GeneratedColumn<String>(
    'cooked_at',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _externalIdSnapshotMeta =
      const VerificationMeta('externalIdSnapshot');
  @override
  late final GeneratedColumn<String> externalIdSnapshot =
      GeneratedColumn<String>(
        'external_id_snapshot',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _previousRecipeCookedAtMeta =
      const VerificationMeta('previousRecipeCookedAt');
  @override
  late final GeneratedColumn<String> previousRecipeCookedAt =
      GeneratedColumn<String>(
        'previous_recipe_cooked_at',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _servingsMeta = const VerificationMeta(
    'servings',
  );
  @override
  late final GeneratedColumn<int> servings = GeneratedColumn<int>(
    'servings',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    userId,
    recipeId,
    recipeTitle,
    plannedDate,
    cookedAt,
    externalIdSnapshot,
    previousRecipeCookedAt,
    servings,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'meal_plan_entries';
  @override
  VerificationContext validateIntegrity(
    Insertable<MealPlanEntry> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('user_id')) {
      context.handle(
        _userIdMeta,
        userId.isAcceptableOrUnknown(data['user_id']!, _userIdMeta),
      );
    } else if (isInserting) {
      context.missing(_userIdMeta);
    }
    if (data.containsKey('recipe_id')) {
      context.handle(
        _recipeIdMeta,
        recipeId.isAcceptableOrUnknown(data['recipe_id']!, _recipeIdMeta),
      );
    }
    if (data.containsKey('recipe_title')) {
      context.handle(
        _recipeTitleMeta,
        recipeTitle.isAcceptableOrUnknown(
          data['recipe_title']!,
          _recipeTitleMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_recipeTitleMeta);
    }
    if (data.containsKey('planned_date')) {
      context.handle(
        _plannedDateMeta,
        plannedDate.isAcceptableOrUnknown(
          data['planned_date']!,
          _plannedDateMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_plannedDateMeta);
    }
    if (data.containsKey('cooked_at')) {
      context.handle(
        _cookedAtMeta,
        cookedAt.isAcceptableOrUnknown(data['cooked_at']!, _cookedAtMeta),
      );
    }
    if (data.containsKey('external_id_snapshot')) {
      context.handle(
        _externalIdSnapshotMeta,
        externalIdSnapshot.isAcceptableOrUnknown(
          data['external_id_snapshot']!,
          _externalIdSnapshotMeta,
        ),
      );
    }
    if (data.containsKey('previous_recipe_cooked_at')) {
      context.handle(
        _previousRecipeCookedAtMeta,
        previousRecipeCookedAt.isAcceptableOrUnknown(
          data['previous_recipe_cooked_at']!,
          _previousRecipeCookedAtMeta,
        ),
      );
    }
    if (data.containsKey('servings')) {
      context.handle(
        _servingsMeta,
        servings.isAcceptableOrUnknown(data['servings']!, _servingsMeta),
      );
    } else if (isInserting) {
      context.missing(_servingsMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  MealPlanEntry map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return MealPlanEntry(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      userId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}user_id'],
      )!,
      recipeId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}recipe_id'],
      ),
      recipeTitle: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}recipe_title'],
      )!,
      plannedDate: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}planned_date'],
      )!,
      cookedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}cooked_at'],
      ),
      externalIdSnapshot: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}external_id_snapshot'],
      ),
      previousRecipeCookedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}previous_recipe_cooked_at'],
      ),
      servings: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}servings'],
      )!,
    );
  }

  @override
  $MealPlanEntriesTable createAlias(String alias) {
    return $MealPlanEntriesTable(attachedDatabase, alias);
  }
}

class MealPlanEntry extends DataClass implements Insertable<MealPlanEntry> {
  final int id;
  final String userId;
  final int? recipeId;
  final String recipeTitle;
  final String plannedDate;
  final String? cookedAt;
  final String? externalIdSnapshot;
  final String? previousRecipeCookedAt;
  final int servings;
  const MealPlanEntry({
    required this.id,
    required this.userId,
    this.recipeId,
    required this.recipeTitle,
    required this.plannedDate,
    this.cookedAt,
    this.externalIdSnapshot,
    this.previousRecipeCookedAt,
    required this.servings,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['user_id'] = Variable<String>(userId);
    if (!nullToAbsent || recipeId != null) {
      map['recipe_id'] = Variable<int>(recipeId);
    }
    map['recipe_title'] = Variable<String>(recipeTitle);
    map['planned_date'] = Variable<String>(plannedDate);
    if (!nullToAbsent || cookedAt != null) {
      map['cooked_at'] = Variable<String>(cookedAt);
    }
    if (!nullToAbsent || externalIdSnapshot != null) {
      map['external_id_snapshot'] = Variable<String>(externalIdSnapshot);
    }
    if (!nullToAbsent || previousRecipeCookedAt != null) {
      map['previous_recipe_cooked_at'] = Variable<String>(
        previousRecipeCookedAt,
      );
    }
    map['servings'] = Variable<int>(servings);
    return map;
  }

  MealPlanEntriesCompanion toCompanion(bool nullToAbsent) {
    return MealPlanEntriesCompanion(
      id: Value(id),
      userId: Value(userId),
      recipeId: recipeId == null && nullToAbsent
          ? const Value.absent()
          : Value(recipeId),
      recipeTitle: Value(recipeTitle),
      plannedDate: Value(plannedDate),
      cookedAt: cookedAt == null && nullToAbsent
          ? const Value.absent()
          : Value(cookedAt),
      externalIdSnapshot: externalIdSnapshot == null && nullToAbsent
          ? const Value.absent()
          : Value(externalIdSnapshot),
      previousRecipeCookedAt: previousRecipeCookedAt == null && nullToAbsent
          ? const Value.absent()
          : Value(previousRecipeCookedAt),
      servings: Value(servings),
    );
  }

  factory MealPlanEntry.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return MealPlanEntry(
      id: serializer.fromJson<int>(json['id']),
      userId: serializer.fromJson<String>(json['userId']),
      recipeId: serializer.fromJson<int?>(json['recipeId']),
      recipeTitle: serializer.fromJson<String>(json['recipeTitle']),
      plannedDate: serializer.fromJson<String>(json['plannedDate']),
      cookedAt: serializer.fromJson<String?>(json['cookedAt']),
      externalIdSnapshot: serializer.fromJson<String?>(
        json['externalIdSnapshot'],
      ),
      previousRecipeCookedAt: serializer.fromJson<String?>(
        json['previousRecipeCookedAt'],
      ),
      servings: serializer.fromJson<int>(json['servings']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'userId': serializer.toJson<String>(userId),
      'recipeId': serializer.toJson<int?>(recipeId),
      'recipeTitle': serializer.toJson<String>(recipeTitle),
      'plannedDate': serializer.toJson<String>(plannedDate),
      'cookedAt': serializer.toJson<String?>(cookedAt),
      'externalIdSnapshot': serializer.toJson<String?>(externalIdSnapshot),
      'previousRecipeCookedAt': serializer.toJson<String?>(
        previousRecipeCookedAt,
      ),
      'servings': serializer.toJson<int>(servings),
    };
  }

  MealPlanEntry copyWith({
    int? id,
    String? userId,
    Value<int?> recipeId = const Value.absent(),
    String? recipeTitle,
    String? plannedDate,
    Value<String?> cookedAt = const Value.absent(),
    Value<String?> externalIdSnapshot = const Value.absent(),
    Value<String?> previousRecipeCookedAt = const Value.absent(),
    int? servings,
  }) => MealPlanEntry(
    id: id ?? this.id,
    userId: userId ?? this.userId,
    recipeId: recipeId.present ? recipeId.value : this.recipeId,
    recipeTitle: recipeTitle ?? this.recipeTitle,
    plannedDate: plannedDate ?? this.plannedDate,
    cookedAt: cookedAt.present ? cookedAt.value : this.cookedAt,
    externalIdSnapshot: externalIdSnapshot.present
        ? externalIdSnapshot.value
        : this.externalIdSnapshot,
    previousRecipeCookedAt: previousRecipeCookedAt.present
        ? previousRecipeCookedAt.value
        : this.previousRecipeCookedAt,
    servings: servings ?? this.servings,
  );
  MealPlanEntry copyWithCompanion(MealPlanEntriesCompanion data) {
    return MealPlanEntry(
      id: data.id.present ? data.id.value : this.id,
      userId: data.userId.present ? data.userId.value : this.userId,
      recipeId: data.recipeId.present ? data.recipeId.value : this.recipeId,
      recipeTitle: data.recipeTitle.present
          ? data.recipeTitle.value
          : this.recipeTitle,
      plannedDate: data.plannedDate.present
          ? data.plannedDate.value
          : this.plannedDate,
      cookedAt: data.cookedAt.present ? data.cookedAt.value : this.cookedAt,
      externalIdSnapshot: data.externalIdSnapshot.present
          ? data.externalIdSnapshot.value
          : this.externalIdSnapshot,
      previousRecipeCookedAt: data.previousRecipeCookedAt.present
          ? data.previousRecipeCookedAt.value
          : this.previousRecipeCookedAt,
      servings: data.servings.present ? data.servings.value : this.servings,
    );
  }

  @override
  String toString() {
    return (StringBuffer('MealPlanEntry(')
          ..write('id: $id, ')
          ..write('userId: $userId, ')
          ..write('recipeId: $recipeId, ')
          ..write('recipeTitle: $recipeTitle, ')
          ..write('plannedDate: $plannedDate, ')
          ..write('cookedAt: $cookedAt, ')
          ..write('externalIdSnapshot: $externalIdSnapshot, ')
          ..write('previousRecipeCookedAt: $previousRecipeCookedAt, ')
          ..write('servings: $servings')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    userId,
    recipeId,
    recipeTitle,
    plannedDate,
    cookedAt,
    externalIdSnapshot,
    previousRecipeCookedAt,
    servings,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is MealPlanEntry &&
          other.id == this.id &&
          other.userId == this.userId &&
          other.recipeId == this.recipeId &&
          other.recipeTitle == this.recipeTitle &&
          other.plannedDate == this.plannedDate &&
          other.cookedAt == this.cookedAt &&
          other.externalIdSnapshot == this.externalIdSnapshot &&
          other.previousRecipeCookedAt == this.previousRecipeCookedAt &&
          other.servings == this.servings);
}

class MealPlanEntriesCompanion extends UpdateCompanion<MealPlanEntry> {
  final Value<int> id;
  final Value<String> userId;
  final Value<int?> recipeId;
  final Value<String> recipeTitle;
  final Value<String> plannedDate;
  final Value<String?> cookedAt;
  final Value<String?> externalIdSnapshot;
  final Value<String?> previousRecipeCookedAt;
  final Value<int> servings;
  const MealPlanEntriesCompanion({
    this.id = const Value.absent(),
    this.userId = const Value.absent(),
    this.recipeId = const Value.absent(),
    this.recipeTitle = const Value.absent(),
    this.plannedDate = const Value.absent(),
    this.cookedAt = const Value.absent(),
    this.externalIdSnapshot = const Value.absent(),
    this.previousRecipeCookedAt = const Value.absent(),
    this.servings = const Value.absent(),
  });
  MealPlanEntriesCompanion.insert({
    this.id = const Value.absent(),
    required String userId,
    this.recipeId = const Value.absent(),
    required String recipeTitle,
    required String plannedDate,
    this.cookedAt = const Value.absent(),
    this.externalIdSnapshot = const Value.absent(),
    this.previousRecipeCookedAt = const Value.absent(),
    required int servings,
  }) : userId = Value(userId),
       recipeTitle = Value(recipeTitle),
       plannedDate = Value(plannedDate),
       servings = Value(servings);
  static Insertable<MealPlanEntry> custom({
    Expression<int>? id,
    Expression<String>? userId,
    Expression<int>? recipeId,
    Expression<String>? recipeTitle,
    Expression<String>? plannedDate,
    Expression<String>? cookedAt,
    Expression<String>? externalIdSnapshot,
    Expression<String>? previousRecipeCookedAt,
    Expression<int>? servings,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (userId != null) 'user_id': userId,
      if (recipeId != null) 'recipe_id': recipeId,
      if (recipeTitle != null) 'recipe_title': recipeTitle,
      if (plannedDate != null) 'planned_date': plannedDate,
      if (cookedAt != null) 'cooked_at': cookedAt,
      if (externalIdSnapshot != null)
        'external_id_snapshot': externalIdSnapshot,
      if (previousRecipeCookedAt != null)
        'previous_recipe_cooked_at': previousRecipeCookedAt,
      if (servings != null) 'servings': servings,
    });
  }

  MealPlanEntriesCompanion copyWith({
    Value<int>? id,
    Value<String>? userId,
    Value<int?>? recipeId,
    Value<String>? recipeTitle,
    Value<String>? plannedDate,
    Value<String?>? cookedAt,
    Value<String?>? externalIdSnapshot,
    Value<String?>? previousRecipeCookedAt,
    Value<int>? servings,
  }) {
    return MealPlanEntriesCompanion(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      recipeId: recipeId ?? this.recipeId,
      recipeTitle: recipeTitle ?? this.recipeTitle,
      plannedDate: plannedDate ?? this.plannedDate,
      cookedAt: cookedAt ?? this.cookedAt,
      externalIdSnapshot: externalIdSnapshot ?? this.externalIdSnapshot,
      previousRecipeCookedAt:
          previousRecipeCookedAt ?? this.previousRecipeCookedAt,
      servings: servings ?? this.servings,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (userId.present) {
      map['user_id'] = Variable<String>(userId.value);
    }
    if (recipeId.present) {
      map['recipe_id'] = Variable<int>(recipeId.value);
    }
    if (recipeTitle.present) {
      map['recipe_title'] = Variable<String>(recipeTitle.value);
    }
    if (plannedDate.present) {
      map['planned_date'] = Variable<String>(plannedDate.value);
    }
    if (cookedAt.present) {
      map['cooked_at'] = Variable<String>(cookedAt.value);
    }
    if (externalIdSnapshot.present) {
      map['external_id_snapshot'] = Variable<String>(externalIdSnapshot.value);
    }
    if (previousRecipeCookedAt.present) {
      map['previous_recipe_cooked_at'] = Variable<String>(
        previousRecipeCookedAt.value,
      );
    }
    if (servings.present) {
      map['servings'] = Variable<int>(servings.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('MealPlanEntriesCompanion(')
          ..write('id: $id, ')
          ..write('userId: $userId, ')
          ..write('recipeId: $recipeId, ')
          ..write('recipeTitle: $recipeTitle, ')
          ..write('plannedDate: $plannedDate, ')
          ..write('cookedAt: $cookedAt, ')
          ..write('externalIdSnapshot: $externalIdSnapshot, ')
          ..write('previousRecipeCookedAt: $previousRecipeCookedAt, ')
          ..write('servings: $servings')
          ..write(')'))
        .toString();
  }
}

class $CookedAdjustmentsTable extends CookedAdjustments
    with TableInfo<$CookedAdjustmentsTable, CookedAdjustment> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CookedAdjustmentsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _userIdMeta = const VerificationMeta('userId');
  @override
  late final GeneratedColumn<String> userId = GeneratedColumn<String>(
    'user_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _mealPlanEntryIdMeta = const VerificationMeta(
    'mealPlanEntryId',
  );
  @override
  late final GeneratedColumn<int> mealPlanEntryId = GeneratedColumn<int>(
    'meal_plan_entry_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES meal_plan_entries (id) ON DELETE CASCADE',
    ),
  );
  static const VerificationMeta _ingredientIdMeta = const VerificationMeta(
    'ingredientId',
  );
  @override
  late final GeneratedColumn<int> ingredientId = GeneratedColumn<int>(
    'ingredient_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES ingredients (id)',
    ),
  );
  static const VerificationMeta _amountDeductedMeta = const VerificationMeta(
    'amountDeducted',
  );
  @override
  late final GeneratedColumn<double> amountDeducted = GeneratedColumn<double>(
    'amount_deducted',
    aliasedName,
    false,
    type: DriftSqlType.double,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _unitMeta = const VerificationMeta('unit');
  @override
  late final GeneratedColumn<String> unit = GeneratedColumn<String>(
    'unit',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _previousLastUsedAtMeta =
      const VerificationMeta('previousLastUsedAt');
  @override
  late final GeneratedColumn<String> previousLastUsedAt =
      GeneratedColumn<String>(
        'previous_last_used_at',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _createdAtMeta = const VerificationMeta(
    'createdAt',
  );
  @override
  late final GeneratedColumn<String> createdAt = GeneratedColumn<String>(
    'created_at',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    userId,
    mealPlanEntryId,
    ingredientId,
    amountDeducted,
    unit,
    previousLastUsedAt,
    createdAt,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'cooked_adjustments';
  @override
  VerificationContext validateIntegrity(
    Insertable<CookedAdjustment> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('user_id')) {
      context.handle(
        _userIdMeta,
        userId.isAcceptableOrUnknown(data['user_id']!, _userIdMeta),
      );
    } else if (isInserting) {
      context.missing(_userIdMeta);
    }
    if (data.containsKey('meal_plan_entry_id')) {
      context.handle(
        _mealPlanEntryIdMeta,
        mealPlanEntryId.isAcceptableOrUnknown(
          data['meal_plan_entry_id']!,
          _mealPlanEntryIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_mealPlanEntryIdMeta);
    }
    if (data.containsKey('ingredient_id')) {
      context.handle(
        _ingredientIdMeta,
        ingredientId.isAcceptableOrUnknown(
          data['ingredient_id']!,
          _ingredientIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_ingredientIdMeta);
    }
    if (data.containsKey('amount_deducted')) {
      context.handle(
        _amountDeductedMeta,
        amountDeducted.isAcceptableOrUnknown(
          data['amount_deducted']!,
          _amountDeductedMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_amountDeductedMeta);
    }
    if (data.containsKey('unit')) {
      context.handle(
        _unitMeta,
        unit.isAcceptableOrUnknown(data['unit']!, _unitMeta),
      );
    } else if (isInserting) {
      context.missing(_unitMeta);
    }
    if (data.containsKey('previous_last_used_at')) {
      context.handle(
        _previousLastUsedAtMeta,
        previousLastUsedAt.isAcceptableOrUnknown(
          data['previous_last_used_at']!,
          _previousLastUsedAtMeta,
        ),
      );
    }
    if (data.containsKey('created_at')) {
      context.handle(
        _createdAtMeta,
        createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta),
      );
    } else if (isInserting) {
      context.missing(_createdAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  CookedAdjustment map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CookedAdjustment(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      userId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}user_id'],
      )!,
      mealPlanEntryId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}meal_plan_entry_id'],
      )!,
      ingredientId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}ingredient_id'],
      )!,
      amountDeducted: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}amount_deducted'],
      )!,
      unit: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}unit'],
      )!,
      previousLastUsedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}previous_last_used_at'],
      ),
      createdAt: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}created_at'],
      )!,
    );
  }

  @override
  $CookedAdjustmentsTable createAlias(String alias) {
    return $CookedAdjustmentsTable(attachedDatabase, alias);
  }
}

class CookedAdjustment extends DataClass
    implements Insertable<CookedAdjustment> {
  final int id;
  final String userId;
  final int mealPlanEntryId;
  final int ingredientId;
  final double amountDeducted;
  final String unit;
  final String? previousLastUsedAt;
  final String createdAt;
  const CookedAdjustment({
    required this.id,
    required this.userId,
    required this.mealPlanEntryId,
    required this.ingredientId,
    required this.amountDeducted,
    required this.unit,
    this.previousLastUsedAt,
    required this.createdAt,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['user_id'] = Variable<String>(userId);
    map['meal_plan_entry_id'] = Variable<int>(mealPlanEntryId);
    map['ingredient_id'] = Variable<int>(ingredientId);
    map['amount_deducted'] = Variable<double>(amountDeducted);
    map['unit'] = Variable<String>(unit);
    if (!nullToAbsent || previousLastUsedAt != null) {
      map['previous_last_used_at'] = Variable<String>(previousLastUsedAt);
    }
    map['created_at'] = Variable<String>(createdAt);
    return map;
  }

  CookedAdjustmentsCompanion toCompanion(bool nullToAbsent) {
    return CookedAdjustmentsCompanion(
      id: Value(id),
      userId: Value(userId),
      mealPlanEntryId: Value(mealPlanEntryId),
      ingredientId: Value(ingredientId),
      amountDeducted: Value(amountDeducted),
      unit: Value(unit),
      previousLastUsedAt: previousLastUsedAt == null && nullToAbsent
          ? const Value.absent()
          : Value(previousLastUsedAt),
      createdAt: Value(createdAt),
    );
  }

  factory CookedAdjustment.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CookedAdjustment(
      id: serializer.fromJson<int>(json['id']),
      userId: serializer.fromJson<String>(json['userId']),
      mealPlanEntryId: serializer.fromJson<int>(json['mealPlanEntryId']),
      ingredientId: serializer.fromJson<int>(json['ingredientId']),
      amountDeducted: serializer.fromJson<double>(json['amountDeducted']),
      unit: serializer.fromJson<String>(json['unit']),
      previousLastUsedAt: serializer.fromJson<String?>(
        json['previousLastUsedAt'],
      ),
      createdAt: serializer.fromJson<String>(json['createdAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'userId': serializer.toJson<String>(userId),
      'mealPlanEntryId': serializer.toJson<int>(mealPlanEntryId),
      'ingredientId': serializer.toJson<int>(ingredientId),
      'amountDeducted': serializer.toJson<double>(amountDeducted),
      'unit': serializer.toJson<String>(unit),
      'previousLastUsedAt': serializer.toJson<String?>(previousLastUsedAt),
      'createdAt': serializer.toJson<String>(createdAt),
    };
  }

  CookedAdjustment copyWith({
    int? id,
    String? userId,
    int? mealPlanEntryId,
    int? ingredientId,
    double? amountDeducted,
    String? unit,
    Value<String?> previousLastUsedAt = const Value.absent(),
    String? createdAt,
  }) => CookedAdjustment(
    id: id ?? this.id,
    userId: userId ?? this.userId,
    mealPlanEntryId: mealPlanEntryId ?? this.mealPlanEntryId,
    ingredientId: ingredientId ?? this.ingredientId,
    amountDeducted: amountDeducted ?? this.amountDeducted,
    unit: unit ?? this.unit,
    previousLastUsedAt: previousLastUsedAt.present
        ? previousLastUsedAt.value
        : this.previousLastUsedAt,
    createdAt: createdAt ?? this.createdAt,
  );
  CookedAdjustment copyWithCompanion(CookedAdjustmentsCompanion data) {
    return CookedAdjustment(
      id: data.id.present ? data.id.value : this.id,
      userId: data.userId.present ? data.userId.value : this.userId,
      mealPlanEntryId: data.mealPlanEntryId.present
          ? data.mealPlanEntryId.value
          : this.mealPlanEntryId,
      ingredientId: data.ingredientId.present
          ? data.ingredientId.value
          : this.ingredientId,
      amountDeducted: data.amountDeducted.present
          ? data.amountDeducted.value
          : this.amountDeducted,
      unit: data.unit.present ? data.unit.value : this.unit,
      previousLastUsedAt: data.previousLastUsedAt.present
          ? data.previousLastUsedAt.value
          : this.previousLastUsedAt,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CookedAdjustment(')
          ..write('id: $id, ')
          ..write('userId: $userId, ')
          ..write('mealPlanEntryId: $mealPlanEntryId, ')
          ..write('ingredientId: $ingredientId, ')
          ..write('amountDeducted: $amountDeducted, ')
          ..write('unit: $unit, ')
          ..write('previousLastUsedAt: $previousLastUsedAt, ')
          ..write('createdAt: $createdAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    userId,
    mealPlanEntryId,
    ingredientId,
    amountDeducted,
    unit,
    previousLastUsedAt,
    createdAt,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CookedAdjustment &&
          other.id == this.id &&
          other.userId == this.userId &&
          other.mealPlanEntryId == this.mealPlanEntryId &&
          other.ingredientId == this.ingredientId &&
          other.amountDeducted == this.amountDeducted &&
          other.unit == this.unit &&
          other.previousLastUsedAt == this.previousLastUsedAt &&
          other.createdAt == this.createdAt);
}

class CookedAdjustmentsCompanion extends UpdateCompanion<CookedAdjustment> {
  final Value<int> id;
  final Value<String> userId;
  final Value<int> mealPlanEntryId;
  final Value<int> ingredientId;
  final Value<double> amountDeducted;
  final Value<String> unit;
  final Value<String?> previousLastUsedAt;
  final Value<String> createdAt;
  const CookedAdjustmentsCompanion({
    this.id = const Value.absent(),
    this.userId = const Value.absent(),
    this.mealPlanEntryId = const Value.absent(),
    this.ingredientId = const Value.absent(),
    this.amountDeducted = const Value.absent(),
    this.unit = const Value.absent(),
    this.previousLastUsedAt = const Value.absent(),
    this.createdAt = const Value.absent(),
  });
  CookedAdjustmentsCompanion.insert({
    this.id = const Value.absent(),
    required String userId,
    required int mealPlanEntryId,
    required int ingredientId,
    required double amountDeducted,
    required String unit,
    this.previousLastUsedAt = const Value.absent(),
    required String createdAt,
  }) : userId = Value(userId),
       mealPlanEntryId = Value(mealPlanEntryId),
       ingredientId = Value(ingredientId),
       amountDeducted = Value(amountDeducted),
       unit = Value(unit),
       createdAt = Value(createdAt);
  static Insertable<CookedAdjustment> custom({
    Expression<int>? id,
    Expression<String>? userId,
    Expression<int>? mealPlanEntryId,
    Expression<int>? ingredientId,
    Expression<double>? amountDeducted,
    Expression<String>? unit,
    Expression<String>? previousLastUsedAt,
    Expression<String>? createdAt,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (userId != null) 'user_id': userId,
      if (mealPlanEntryId != null) 'meal_plan_entry_id': mealPlanEntryId,
      if (ingredientId != null) 'ingredient_id': ingredientId,
      if (amountDeducted != null) 'amount_deducted': amountDeducted,
      if (unit != null) 'unit': unit,
      if (previousLastUsedAt != null)
        'previous_last_used_at': previousLastUsedAt,
      if (createdAt != null) 'created_at': createdAt,
    });
  }

  CookedAdjustmentsCompanion copyWith({
    Value<int>? id,
    Value<String>? userId,
    Value<int>? mealPlanEntryId,
    Value<int>? ingredientId,
    Value<double>? amountDeducted,
    Value<String>? unit,
    Value<String?>? previousLastUsedAt,
    Value<String>? createdAt,
  }) {
    return CookedAdjustmentsCompanion(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      mealPlanEntryId: mealPlanEntryId ?? this.mealPlanEntryId,
      ingredientId: ingredientId ?? this.ingredientId,
      amountDeducted: amountDeducted ?? this.amountDeducted,
      unit: unit ?? this.unit,
      previousLastUsedAt: previousLastUsedAt ?? this.previousLastUsedAt,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (userId.present) {
      map['user_id'] = Variable<String>(userId.value);
    }
    if (mealPlanEntryId.present) {
      map['meal_plan_entry_id'] = Variable<int>(mealPlanEntryId.value);
    }
    if (ingredientId.present) {
      map['ingredient_id'] = Variable<int>(ingredientId.value);
    }
    if (amountDeducted.present) {
      map['amount_deducted'] = Variable<double>(amountDeducted.value);
    }
    if (unit.present) {
      map['unit'] = Variable<String>(unit.value);
    }
    if (previousLastUsedAt.present) {
      map['previous_last_used_at'] = Variable<String>(previousLastUsedAt.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<String>(createdAt.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CookedAdjustmentsCompanion(')
          ..write('id: $id, ')
          ..write('userId: $userId, ')
          ..write('mealPlanEntryId: $mealPlanEntryId, ')
          ..write('ingredientId: $ingredientId, ')
          ..write('amountDeducted: $amountDeducted, ')
          ..write('unit: $unit, ')
          ..write('previousLastUsedAt: $previousLastUsedAt, ')
          ..write('createdAt: $createdAt')
          ..write(')'))
        .toString();
  }
}

class $ShoppingListItemsTable extends ShoppingListItems
    with TableInfo<$ShoppingListItemsTable, ShoppingListItem> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $ShoppingListItemsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _userIdMeta = const VerificationMeta('userId');
  @override
  late final GeneratedColumn<String> userId = GeneratedColumn<String>(
    'user_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _ingredientIdMeta = const VerificationMeta(
    'ingredientId',
  );
  @override
  late final GeneratedColumn<int> ingredientId = GeneratedColumn<int>(
    'ingredient_id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES ingredients (id)',
    ),
  );
  static const VerificationMeta _nameMeta = const VerificationMeta('name');
  @override
  late final GeneratedColumn<String> name = GeneratedColumn<String>(
    'name',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _quantityMeta = const VerificationMeta(
    'quantity',
  );
  @override
  late final GeneratedColumn<double> quantity = GeneratedColumn<double>(
    'quantity',
    aliasedName,
    true,
    type: DriftSqlType.double,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _unitMeta = const VerificationMeta('unit');
  @override
  late final GeneratedColumn<String> unit = GeneratedColumn<String>(
    'unit',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _sourceMeta = const VerificationMeta('source');
  @override
  late final GeneratedColumn<String> source = GeneratedColumn<String>(
    'source',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('manual'),
  );
  static const VerificationMeta _isRequirementMeta = const VerificationMeta(
    'isRequirement',
  );
  @override
  late final GeneratedColumn<bool> isRequirement = GeneratedColumn<bool>(
    'is_requirement',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("is_requirement" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  static const VerificationMeta _isCheckedMeta = const VerificationMeta(
    'isChecked',
  );
  @override
  late final GeneratedColumn<bool> isChecked = GeneratedColumn<bool>(
    'is_checked',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("is_checked" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  static const VerificationMeta _sourceMealPlanEntryIdMeta =
      const VerificationMeta('sourceMealPlanEntryId');
  @override
  late final GeneratedColumn<int> sourceMealPlanEntryId = GeneratedColumn<int>(
    'source_meal_plan_entry_id',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES meal_plan_entries (id) ON DELETE CASCADE',
    ),
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    userId,
    ingredientId,
    name,
    quantity,
    unit,
    source,
    isRequirement,
    isChecked,
    sourceMealPlanEntryId,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'shopping_list_items';
  @override
  VerificationContext validateIntegrity(
    Insertable<ShoppingListItem> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('user_id')) {
      context.handle(
        _userIdMeta,
        userId.isAcceptableOrUnknown(data['user_id']!, _userIdMeta),
      );
    } else if (isInserting) {
      context.missing(_userIdMeta);
    }
    if (data.containsKey('ingredient_id')) {
      context.handle(
        _ingredientIdMeta,
        ingredientId.isAcceptableOrUnknown(
          data['ingredient_id']!,
          _ingredientIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_ingredientIdMeta);
    }
    if (data.containsKey('name')) {
      context.handle(
        _nameMeta,
        name.isAcceptableOrUnknown(data['name']!, _nameMeta),
      );
    } else if (isInserting) {
      context.missing(_nameMeta);
    }
    if (data.containsKey('quantity')) {
      context.handle(
        _quantityMeta,
        quantity.isAcceptableOrUnknown(data['quantity']!, _quantityMeta),
      );
    }
    if (data.containsKey('unit')) {
      context.handle(
        _unitMeta,
        unit.isAcceptableOrUnknown(data['unit']!, _unitMeta),
      );
    }
    if (data.containsKey('source')) {
      context.handle(
        _sourceMeta,
        source.isAcceptableOrUnknown(data['source']!, _sourceMeta),
      );
    }
    if (data.containsKey('is_requirement')) {
      context.handle(
        _isRequirementMeta,
        isRequirement.isAcceptableOrUnknown(
          data['is_requirement']!,
          _isRequirementMeta,
        ),
      );
    }
    if (data.containsKey('is_checked')) {
      context.handle(
        _isCheckedMeta,
        isChecked.isAcceptableOrUnknown(data['is_checked']!, _isCheckedMeta),
      );
    }
    if (data.containsKey('source_meal_plan_entry_id')) {
      context.handle(
        _sourceMealPlanEntryIdMeta,
        sourceMealPlanEntryId.isAcceptableOrUnknown(
          data['source_meal_plan_entry_id']!,
          _sourceMealPlanEntryIdMeta,
        ),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  ShoppingListItem map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return ShoppingListItem(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      userId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}user_id'],
      )!,
      ingredientId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}ingredient_id'],
      )!,
      name: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}name'],
      )!,
      quantity: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}quantity'],
      ),
      unit: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}unit'],
      ),
      source: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}source'],
      )!,
      isRequirement: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}is_requirement'],
      )!,
      isChecked: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}is_checked'],
      )!,
      sourceMealPlanEntryId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}source_meal_plan_entry_id'],
      ),
    );
  }

  @override
  $ShoppingListItemsTable createAlias(String alias) {
    return $ShoppingListItemsTable(attachedDatabase, alias);
  }
}

class ShoppingListItem extends DataClass
    implements Insertable<ShoppingListItem> {
  final int id;
  final String userId;
  final int ingredientId;
  final String name;
  final double? quantity;
  final String? unit;
  final String source;
  final bool isRequirement;
  final bool isChecked;
  final int? sourceMealPlanEntryId;
  const ShoppingListItem({
    required this.id,
    required this.userId,
    required this.ingredientId,
    required this.name,
    this.quantity,
    this.unit,
    required this.source,
    required this.isRequirement,
    required this.isChecked,
    this.sourceMealPlanEntryId,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['user_id'] = Variable<String>(userId);
    map['ingredient_id'] = Variable<int>(ingredientId);
    map['name'] = Variable<String>(name);
    if (!nullToAbsent || quantity != null) {
      map['quantity'] = Variable<double>(quantity);
    }
    if (!nullToAbsent || unit != null) {
      map['unit'] = Variable<String>(unit);
    }
    map['source'] = Variable<String>(source);
    map['is_requirement'] = Variable<bool>(isRequirement);
    map['is_checked'] = Variable<bool>(isChecked);
    if (!nullToAbsent || sourceMealPlanEntryId != null) {
      map['source_meal_plan_entry_id'] = Variable<int>(sourceMealPlanEntryId);
    }
    return map;
  }

  ShoppingListItemsCompanion toCompanion(bool nullToAbsent) {
    return ShoppingListItemsCompanion(
      id: Value(id),
      userId: Value(userId),
      ingredientId: Value(ingredientId),
      name: Value(name),
      quantity: quantity == null && nullToAbsent
          ? const Value.absent()
          : Value(quantity),
      unit: unit == null && nullToAbsent ? const Value.absent() : Value(unit),
      source: Value(source),
      isRequirement: Value(isRequirement),
      isChecked: Value(isChecked),
      sourceMealPlanEntryId: sourceMealPlanEntryId == null && nullToAbsent
          ? const Value.absent()
          : Value(sourceMealPlanEntryId),
    );
  }

  factory ShoppingListItem.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return ShoppingListItem(
      id: serializer.fromJson<int>(json['id']),
      userId: serializer.fromJson<String>(json['userId']),
      ingredientId: serializer.fromJson<int>(json['ingredientId']),
      name: serializer.fromJson<String>(json['name']),
      quantity: serializer.fromJson<double?>(json['quantity']),
      unit: serializer.fromJson<String?>(json['unit']),
      source: serializer.fromJson<String>(json['source']),
      isRequirement: serializer.fromJson<bool>(json['isRequirement']),
      isChecked: serializer.fromJson<bool>(json['isChecked']),
      sourceMealPlanEntryId: serializer.fromJson<int?>(
        json['sourceMealPlanEntryId'],
      ),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'userId': serializer.toJson<String>(userId),
      'ingredientId': serializer.toJson<int>(ingredientId),
      'name': serializer.toJson<String>(name),
      'quantity': serializer.toJson<double?>(quantity),
      'unit': serializer.toJson<String?>(unit),
      'source': serializer.toJson<String>(source),
      'isRequirement': serializer.toJson<bool>(isRequirement),
      'isChecked': serializer.toJson<bool>(isChecked),
      'sourceMealPlanEntryId': serializer.toJson<int?>(sourceMealPlanEntryId),
    };
  }

  ShoppingListItem copyWith({
    int? id,
    String? userId,
    int? ingredientId,
    String? name,
    Value<double?> quantity = const Value.absent(),
    Value<String?> unit = const Value.absent(),
    String? source,
    bool? isRequirement,
    bool? isChecked,
    Value<int?> sourceMealPlanEntryId = const Value.absent(),
  }) => ShoppingListItem(
    id: id ?? this.id,
    userId: userId ?? this.userId,
    ingredientId: ingredientId ?? this.ingredientId,
    name: name ?? this.name,
    quantity: quantity.present ? quantity.value : this.quantity,
    unit: unit.present ? unit.value : this.unit,
    source: source ?? this.source,
    isRequirement: isRequirement ?? this.isRequirement,
    isChecked: isChecked ?? this.isChecked,
    sourceMealPlanEntryId: sourceMealPlanEntryId.present
        ? sourceMealPlanEntryId.value
        : this.sourceMealPlanEntryId,
  );
  ShoppingListItem copyWithCompanion(ShoppingListItemsCompanion data) {
    return ShoppingListItem(
      id: data.id.present ? data.id.value : this.id,
      userId: data.userId.present ? data.userId.value : this.userId,
      ingredientId: data.ingredientId.present
          ? data.ingredientId.value
          : this.ingredientId,
      name: data.name.present ? data.name.value : this.name,
      quantity: data.quantity.present ? data.quantity.value : this.quantity,
      unit: data.unit.present ? data.unit.value : this.unit,
      source: data.source.present ? data.source.value : this.source,
      isRequirement: data.isRequirement.present
          ? data.isRequirement.value
          : this.isRequirement,
      isChecked: data.isChecked.present ? data.isChecked.value : this.isChecked,
      sourceMealPlanEntryId: data.sourceMealPlanEntryId.present
          ? data.sourceMealPlanEntryId.value
          : this.sourceMealPlanEntryId,
    );
  }

  @override
  String toString() {
    return (StringBuffer('ShoppingListItem(')
          ..write('id: $id, ')
          ..write('userId: $userId, ')
          ..write('ingredientId: $ingredientId, ')
          ..write('name: $name, ')
          ..write('quantity: $quantity, ')
          ..write('unit: $unit, ')
          ..write('source: $source, ')
          ..write('isRequirement: $isRequirement, ')
          ..write('isChecked: $isChecked, ')
          ..write('sourceMealPlanEntryId: $sourceMealPlanEntryId')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    userId,
    ingredientId,
    name,
    quantity,
    unit,
    source,
    isRequirement,
    isChecked,
    sourceMealPlanEntryId,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is ShoppingListItem &&
          other.id == this.id &&
          other.userId == this.userId &&
          other.ingredientId == this.ingredientId &&
          other.name == this.name &&
          other.quantity == this.quantity &&
          other.unit == this.unit &&
          other.source == this.source &&
          other.isRequirement == this.isRequirement &&
          other.isChecked == this.isChecked &&
          other.sourceMealPlanEntryId == this.sourceMealPlanEntryId);
}

class ShoppingListItemsCompanion extends UpdateCompanion<ShoppingListItem> {
  final Value<int> id;
  final Value<String> userId;
  final Value<int> ingredientId;
  final Value<String> name;
  final Value<double?> quantity;
  final Value<String?> unit;
  final Value<String> source;
  final Value<bool> isRequirement;
  final Value<bool> isChecked;
  final Value<int?> sourceMealPlanEntryId;
  const ShoppingListItemsCompanion({
    this.id = const Value.absent(),
    this.userId = const Value.absent(),
    this.ingredientId = const Value.absent(),
    this.name = const Value.absent(),
    this.quantity = const Value.absent(),
    this.unit = const Value.absent(),
    this.source = const Value.absent(),
    this.isRequirement = const Value.absent(),
    this.isChecked = const Value.absent(),
    this.sourceMealPlanEntryId = const Value.absent(),
  });
  ShoppingListItemsCompanion.insert({
    this.id = const Value.absent(),
    required String userId,
    required int ingredientId,
    required String name,
    this.quantity = const Value.absent(),
    this.unit = const Value.absent(),
    this.source = const Value.absent(),
    this.isRequirement = const Value.absent(),
    this.isChecked = const Value.absent(),
    this.sourceMealPlanEntryId = const Value.absent(),
  }) : userId = Value(userId),
       ingredientId = Value(ingredientId),
       name = Value(name);
  static Insertable<ShoppingListItem> custom({
    Expression<int>? id,
    Expression<String>? userId,
    Expression<int>? ingredientId,
    Expression<String>? name,
    Expression<double>? quantity,
    Expression<String>? unit,
    Expression<String>? source,
    Expression<bool>? isRequirement,
    Expression<bool>? isChecked,
    Expression<int>? sourceMealPlanEntryId,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (userId != null) 'user_id': userId,
      if (ingredientId != null) 'ingredient_id': ingredientId,
      if (name != null) 'name': name,
      if (quantity != null) 'quantity': quantity,
      if (unit != null) 'unit': unit,
      if (source != null) 'source': source,
      if (isRequirement != null) 'is_requirement': isRequirement,
      if (isChecked != null) 'is_checked': isChecked,
      if (sourceMealPlanEntryId != null)
        'source_meal_plan_entry_id': sourceMealPlanEntryId,
    });
  }

  ShoppingListItemsCompanion copyWith({
    Value<int>? id,
    Value<String>? userId,
    Value<int>? ingredientId,
    Value<String>? name,
    Value<double?>? quantity,
    Value<String?>? unit,
    Value<String>? source,
    Value<bool>? isRequirement,
    Value<bool>? isChecked,
    Value<int?>? sourceMealPlanEntryId,
  }) {
    return ShoppingListItemsCompanion(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      ingredientId: ingredientId ?? this.ingredientId,
      name: name ?? this.name,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      source: source ?? this.source,
      isRequirement: isRequirement ?? this.isRequirement,
      isChecked: isChecked ?? this.isChecked,
      sourceMealPlanEntryId:
          sourceMealPlanEntryId ?? this.sourceMealPlanEntryId,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (userId.present) {
      map['user_id'] = Variable<String>(userId.value);
    }
    if (ingredientId.present) {
      map['ingredient_id'] = Variable<int>(ingredientId.value);
    }
    if (name.present) {
      map['name'] = Variable<String>(name.value);
    }
    if (quantity.present) {
      map['quantity'] = Variable<double>(quantity.value);
    }
    if (unit.present) {
      map['unit'] = Variable<String>(unit.value);
    }
    if (source.present) {
      map['source'] = Variable<String>(source.value);
    }
    if (isRequirement.present) {
      map['is_requirement'] = Variable<bool>(isRequirement.value);
    }
    if (isChecked.present) {
      map['is_checked'] = Variable<bool>(isChecked.value);
    }
    if (sourceMealPlanEntryId.present) {
      map['source_meal_plan_entry_id'] = Variable<int>(
        sourceMealPlanEntryId.value,
      );
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('ShoppingListItemsCompanion(')
          ..write('id: $id, ')
          ..write('userId: $userId, ')
          ..write('ingredientId: $ingredientId, ')
          ..write('name: $name, ')
          ..write('quantity: $quantity, ')
          ..write('unit: $unit, ')
          ..write('source: $source, ')
          ..write('isRequirement: $isRequirement, ')
          ..write('isChecked: $isChecked, ')
          ..write('sourceMealPlanEntryId: $sourceMealPlanEntryId')
          ..write(')'))
        .toString();
  }
}

class $UserConfigTable extends UserConfig
    with TableInfo<$UserConfigTable, UserConfigData> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $UserConfigTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
    'id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _purchaseToleranceMeta = const VerificationMeta(
    'purchaseTolerance',
  );
  @override
  late final GeneratedColumn<double> purchaseTolerance =
      GeneratedColumn<double>(
        'purchase_tolerance',
        aliasedName,
        false,
        type: DriftSqlType.double,
        requiredDuringInsert: false,
        defaultValue: const Constant(0.5),
      );
  static const VerificationMeta _preferredServingsMeta = const VerificationMeta(
    'preferredServings',
  );
  @override
  late final GeneratedColumn<int> preferredServings = GeneratedColumn<int>(
    'preferred_servings',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(2),
  );
  static const VerificationMeta _mealsPerWeekMeta = const VerificationMeta(
    'mealsPerWeek',
  );
  @override
  late final GeneratedColumn<int> mealsPerWeek = GeneratedColumn<int>(
    'meals_per_week',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(5),
  );
  static const VerificationMeta _dietaryFlagsMeta = const VerificationMeta(
    'dietaryFlags',
  );
  @override
  late final GeneratedColumn<String> dietaryFlags = GeneratedColumn<String>(
    'dietary_flags',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('[]'),
  );
  static const VerificationMeta _maxActiveTimeMinsMeta = const VerificationMeta(
    'maxActiveTimeMins',
  );
  @override
  late final GeneratedColumn<int> maxActiveTimeMins = GeneratedColumn<int>(
    'max_active_time_mins',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _onboardingCompletedMeta =
      const VerificationMeta('onboardingCompleted');
  @override
  late final GeneratedColumn<bool> onboardingCompleted = GeneratedColumn<bool>(
    'onboarding_completed',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("onboarding_completed" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    purchaseTolerance,
    preferredServings,
    mealsPerWeek,
    dietaryFlags,
    maxActiveTimeMins,
    onboardingCompleted,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'user_config';
  @override
  VerificationContext validateIntegrity(
    Insertable<UserConfigData> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('purchase_tolerance')) {
      context.handle(
        _purchaseToleranceMeta,
        purchaseTolerance.isAcceptableOrUnknown(
          data['purchase_tolerance']!,
          _purchaseToleranceMeta,
        ),
      );
    }
    if (data.containsKey('preferred_servings')) {
      context.handle(
        _preferredServingsMeta,
        preferredServings.isAcceptableOrUnknown(
          data['preferred_servings']!,
          _preferredServingsMeta,
        ),
      );
    }
    if (data.containsKey('meals_per_week')) {
      context.handle(
        _mealsPerWeekMeta,
        mealsPerWeek.isAcceptableOrUnknown(
          data['meals_per_week']!,
          _mealsPerWeekMeta,
        ),
      );
    }
    if (data.containsKey('dietary_flags')) {
      context.handle(
        _dietaryFlagsMeta,
        dietaryFlags.isAcceptableOrUnknown(
          data['dietary_flags']!,
          _dietaryFlagsMeta,
        ),
      );
    }
    if (data.containsKey('max_active_time_mins')) {
      context.handle(
        _maxActiveTimeMinsMeta,
        maxActiveTimeMins.isAcceptableOrUnknown(
          data['max_active_time_mins']!,
          _maxActiveTimeMinsMeta,
        ),
      );
    }
    if (data.containsKey('onboarding_completed')) {
      context.handle(
        _onboardingCompletedMeta,
        onboardingCompleted.isAcceptableOrUnknown(
          data['onboarding_completed']!,
          _onboardingCompletedMeta,
        ),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  UserConfigData map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return UserConfigData(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}id'],
      )!,
      purchaseTolerance: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}purchase_tolerance'],
      )!,
      preferredServings: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}preferred_servings'],
      )!,
      mealsPerWeek: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}meals_per_week'],
      )!,
      dietaryFlags: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}dietary_flags'],
      )!,
      maxActiveTimeMins: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}max_active_time_mins'],
      ),
      onboardingCompleted: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}onboarding_completed'],
      )!,
    );
  }

  @override
  $UserConfigTable createAlias(String alias) {
    return $UserConfigTable(attachedDatabase, alias);
  }
}

class UserConfigData extends DataClass implements Insertable<UserConfigData> {
  final String id;
  final double purchaseTolerance;
  final int preferredServings;
  final int mealsPerWeek;
  final String dietaryFlags;
  final int? maxActiveTimeMins;
  final bool onboardingCompleted;
  const UserConfigData({
    required this.id,
    required this.purchaseTolerance,
    required this.preferredServings,
    required this.mealsPerWeek,
    required this.dietaryFlags,
    this.maxActiveTimeMins,
    required this.onboardingCompleted,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<String>(id);
    map['purchase_tolerance'] = Variable<double>(purchaseTolerance);
    map['preferred_servings'] = Variable<int>(preferredServings);
    map['meals_per_week'] = Variable<int>(mealsPerWeek);
    map['dietary_flags'] = Variable<String>(dietaryFlags);
    if (!nullToAbsent || maxActiveTimeMins != null) {
      map['max_active_time_mins'] = Variable<int>(maxActiveTimeMins);
    }
    map['onboarding_completed'] = Variable<bool>(onboardingCompleted);
    return map;
  }

  UserConfigCompanion toCompanion(bool nullToAbsent) {
    return UserConfigCompanion(
      id: Value(id),
      purchaseTolerance: Value(purchaseTolerance),
      preferredServings: Value(preferredServings),
      mealsPerWeek: Value(mealsPerWeek),
      dietaryFlags: Value(dietaryFlags),
      maxActiveTimeMins: maxActiveTimeMins == null && nullToAbsent
          ? const Value.absent()
          : Value(maxActiveTimeMins),
      onboardingCompleted: Value(onboardingCompleted),
    );
  }

  factory UserConfigData.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return UserConfigData(
      id: serializer.fromJson<String>(json['id']),
      purchaseTolerance: serializer.fromJson<double>(json['purchaseTolerance']),
      preferredServings: serializer.fromJson<int>(json['preferredServings']),
      mealsPerWeek: serializer.fromJson<int>(json['mealsPerWeek']),
      dietaryFlags: serializer.fromJson<String>(json['dietaryFlags']),
      maxActiveTimeMins: serializer.fromJson<int?>(json['maxActiveTimeMins']),
      onboardingCompleted: serializer.fromJson<bool>(
        json['onboardingCompleted'],
      ),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<String>(id),
      'purchaseTolerance': serializer.toJson<double>(purchaseTolerance),
      'preferredServings': serializer.toJson<int>(preferredServings),
      'mealsPerWeek': serializer.toJson<int>(mealsPerWeek),
      'dietaryFlags': serializer.toJson<String>(dietaryFlags),
      'maxActiveTimeMins': serializer.toJson<int?>(maxActiveTimeMins),
      'onboardingCompleted': serializer.toJson<bool>(onboardingCompleted),
    };
  }

  UserConfigData copyWith({
    String? id,
    double? purchaseTolerance,
    int? preferredServings,
    int? mealsPerWeek,
    String? dietaryFlags,
    Value<int?> maxActiveTimeMins = const Value.absent(),
    bool? onboardingCompleted,
  }) => UserConfigData(
    id: id ?? this.id,
    purchaseTolerance: purchaseTolerance ?? this.purchaseTolerance,
    preferredServings: preferredServings ?? this.preferredServings,
    mealsPerWeek: mealsPerWeek ?? this.mealsPerWeek,
    dietaryFlags: dietaryFlags ?? this.dietaryFlags,
    maxActiveTimeMins: maxActiveTimeMins.present
        ? maxActiveTimeMins.value
        : this.maxActiveTimeMins,
    onboardingCompleted: onboardingCompleted ?? this.onboardingCompleted,
  );
  UserConfigData copyWithCompanion(UserConfigCompanion data) {
    return UserConfigData(
      id: data.id.present ? data.id.value : this.id,
      purchaseTolerance: data.purchaseTolerance.present
          ? data.purchaseTolerance.value
          : this.purchaseTolerance,
      preferredServings: data.preferredServings.present
          ? data.preferredServings.value
          : this.preferredServings,
      mealsPerWeek: data.mealsPerWeek.present
          ? data.mealsPerWeek.value
          : this.mealsPerWeek,
      dietaryFlags: data.dietaryFlags.present
          ? data.dietaryFlags.value
          : this.dietaryFlags,
      maxActiveTimeMins: data.maxActiveTimeMins.present
          ? data.maxActiveTimeMins.value
          : this.maxActiveTimeMins,
      onboardingCompleted: data.onboardingCompleted.present
          ? data.onboardingCompleted.value
          : this.onboardingCompleted,
    );
  }

  @override
  String toString() {
    return (StringBuffer('UserConfigData(')
          ..write('id: $id, ')
          ..write('purchaseTolerance: $purchaseTolerance, ')
          ..write('preferredServings: $preferredServings, ')
          ..write('mealsPerWeek: $mealsPerWeek, ')
          ..write('dietaryFlags: $dietaryFlags, ')
          ..write('maxActiveTimeMins: $maxActiveTimeMins, ')
          ..write('onboardingCompleted: $onboardingCompleted')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    purchaseTolerance,
    preferredServings,
    mealsPerWeek,
    dietaryFlags,
    maxActiveTimeMins,
    onboardingCompleted,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is UserConfigData &&
          other.id == this.id &&
          other.purchaseTolerance == this.purchaseTolerance &&
          other.preferredServings == this.preferredServings &&
          other.mealsPerWeek == this.mealsPerWeek &&
          other.dietaryFlags == this.dietaryFlags &&
          other.maxActiveTimeMins == this.maxActiveTimeMins &&
          other.onboardingCompleted == this.onboardingCompleted);
}

class UserConfigCompanion extends UpdateCompanion<UserConfigData> {
  final Value<String> id;
  final Value<double> purchaseTolerance;
  final Value<int> preferredServings;
  final Value<int> mealsPerWeek;
  final Value<String> dietaryFlags;
  final Value<int?> maxActiveTimeMins;
  final Value<bool> onboardingCompleted;
  final Value<int> rowid;
  const UserConfigCompanion({
    this.id = const Value.absent(),
    this.purchaseTolerance = const Value.absent(),
    this.preferredServings = const Value.absent(),
    this.mealsPerWeek = const Value.absent(),
    this.dietaryFlags = const Value.absent(),
    this.maxActiveTimeMins = const Value.absent(),
    this.onboardingCompleted = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  UserConfigCompanion.insert({
    required String id,
    this.purchaseTolerance = const Value.absent(),
    this.preferredServings = const Value.absent(),
    this.mealsPerWeek = const Value.absent(),
    this.dietaryFlags = const Value.absent(),
    this.maxActiveTimeMins = const Value.absent(),
    this.onboardingCompleted = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : id = Value(id);
  static Insertable<UserConfigData> custom({
    Expression<String>? id,
    Expression<double>? purchaseTolerance,
    Expression<int>? preferredServings,
    Expression<int>? mealsPerWeek,
    Expression<String>? dietaryFlags,
    Expression<int>? maxActiveTimeMins,
    Expression<bool>? onboardingCompleted,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (purchaseTolerance != null) 'purchase_tolerance': purchaseTolerance,
      if (preferredServings != null) 'preferred_servings': preferredServings,
      if (mealsPerWeek != null) 'meals_per_week': mealsPerWeek,
      if (dietaryFlags != null) 'dietary_flags': dietaryFlags,
      if (maxActiveTimeMins != null) 'max_active_time_mins': maxActiveTimeMins,
      if (onboardingCompleted != null)
        'onboarding_completed': onboardingCompleted,
      if (rowid != null) 'rowid': rowid,
    });
  }

  UserConfigCompanion copyWith({
    Value<String>? id,
    Value<double>? purchaseTolerance,
    Value<int>? preferredServings,
    Value<int>? mealsPerWeek,
    Value<String>? dietaryFlags,
    Value<int?>? maxActiveTimeMins,
    Value<bool>? onboardingCompleted,
    Value<int>? rowid,
  }) {
    return UserConfigCompanion(
      id: id ?? this.id,
      purchaseTolerance: purchaseTolerance ?? this.purchaseTolerance,
      preferredServings: preferredServings ?? this.preferredServings,
      mealsPerWeek: mealsPerWeek ?? this.mealsPerWeek,
      dietaryFlags: dietaryFlags ?? this.dietaryFlags,
      maxActiveTimeMins: maxActiveTimeMins ?? this.maxActiveTimeMins,
      onboardingCompleted: onboardingCompleted ?? this.onboardingCompleted,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (purchaseTolerance.present) {
      map['purchase_tolerance'] = Variable<double>(purchaseTolerance.value);
    }
    if (preferredServings.present) {
      map['preferred_servings'] = Variable<int>(preferredServings.value);
    }
    if (mealsPerWeek.present) {
      map['meals_per_week'] = Variable<int>(mealsPerWeek.value);
    }
    if (dietaryFlags.present) {
      map['dietary_flags'] = Variable<String>(dietaryFlags.value);
    }
    if (maxActiveTimeMins.present) {
      map['max_active_time_mins'] = Variable<int>(maxActiveTimeMins.value);
    }
    if (onboardingCompleted.present) {
      map['onboarding_completed'] = Variable<bool>(onboardingCompleted.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('UserConfigCompanion(')
          ..write('id: $id, ')
          ..write('purchaseTolerance: $purchaseTolerance, ')
          ..write('preferredServings: $preferredServings, ')
          ..write('mealsPerWeek: $mealsPerWeek, ')
          ..write('dietaryFlags: $dietaryFlags, ')
          ..write('maxActiveTimeMins: $maxActiveTimeMins, ')
          ..write('onboardingCompleted: $onboardingCompleted, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

abstract class _$GleanDatabase extends GeneratedDatabase {
  _$GleanDatabase(QueryExecutor e) : super(e);
  $GleanDatabaseManager get managers => $GleanDatabaseManager(this);
  late final $IngredientCategoriesTable ingredientCategories =
      $IngredientCategoriesTable(this);
  late final $IngredientsTable ingredients = $IngredientsTable(this);
  late final $PantryItemsTable pantryItems = $PantryItemsTable(this);
  late final $RecipesTable recipes = $RecipesTable(this);
  late final $RecipeDietaryFlagsTable recipeDietaryFlags =
      $RecipeDietaryFlagsTable(this);
  late final $RecipeIngredientsTable recipeIngredients =
      $RecipeIngredientsTable(this);
  late final $MealPlanEntriesTable mealPlanEntries = $MealPlanEntriesTable(
    this,
  );
  late final $CookedAdjustmentsTable cookedAdjustments =
      $CookedAdjustmentsTable(this);
  late final $ShoppingListItemsTable shoppingListItems =
      $ShoppingListItemsTable(this);
  late final $UserConfigTable userConfig = $UserConfigTable(this);
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
    ingredientCategories,
    ingredients,
    pantryItems,
    recipes,
    recipeDietaryFlags,
    recipeIngredients,
    mealPlanEntries,
    cookedAdjustments,
    shoppingListItems,
    userConfig,
  ];
  @override
  StreamQueryUpdateRules get streamUpdateRules => const StreamQueryUpdateRules([
    WritePropagation(
      on: TableUpdateQuery.onTableName(
        'recipes',
        limitUpdateKind: UpdateKind.delete,
      ),
      result: [TableUpdate('recipe_dietary_flags', kind: UpdateKind.delete)],
    ),
    WritePropagation(
      on: TableUpdateQuery.onTableName(
        'recipes',
        limitUpdateKind: UpdateKind.delete,
      ),
      result: [TableUpdate('recipe_ingredients', kind: UpdateKind.delete)],
    ),
    WritePropagation(
      on: TableUpdateQuery.onTableName(
        'recipes',
        limitUpdateKind: UpdateKind.delete,
      ),
      result: [TableUpdate('meal_plan_entries', kind: UpdateKind.update)],
    ),
    WritePropagation(
      on: TableUpdateQuery.onTableName(
        'meal_plan_entries',
        limitUpdateKind: UpdateKind.delete,
      ),
      result: [TableUpdate('cooked_adjustments', kind: UpdateKind.delete)],
    ),
    WritePropagation(
      on: TableUpdateQuery.onTableName(
        'meal_plan_entries',
        limitUpdateKind: UpdateKind.delete,
      ),
      result: [TableUpdate('shopping_list_items', kind: UpdateKind.delete)],
    ),
  ]);
}

typedef $$IngredientCategoriesTableCreateCompanionBuilder =
    IngredientCategoriesCompanion Function({
      required String category,
      required String foodGroup,
      required int shelfLifeDays,
      Value<int> rowid,
    });
typedef $$IngredientCategoriesTableUpdateCompanionBuilder =
    IngredientCategoriesCompanion Function({
      Value<String> category,
      Value<String> foodGroup,
      Value<int> shelfLifeDays,
      Value<int> rowid,
    });

final class $$IngredientCategoriesTableReferences
    extends
        BaseReferences<
          _$GleanDatabase,
          $IngredientCategoriesTable,
          IngredientCategory
        > {
  $$IngredientCategoriesTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static MultiTypedResultKey<$IngredientsTable, List<Ingredient>>
  _ingredientsRefsTable(_$GleanDatabase db) => MultiTypedResultKey.fromTable(
    db.ingredients,
    aliasName: 'ingredient_categories__category__ingredients__category',
  );

  $$IngredientsTableProcessedTableManager get ingredientsRefs {
    final manager = $$IngredientsTableTableManager($_db, $_db.ingredients)
        .filter(
          (f) =>
              f.category.category.sqlEquals($_itemColumn<String>('category')!),
        );

    final cache = $_typedResult.readTableOrNull(_ingredientsRefsTable($_db));
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$IngredientCategoriesTableFilterComposer
    extends Composer<_$GleanDatabase, $IngredientCategoriesTable> {
  $$IngredientCategoriesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get category => $composableBuilder(
    column: $table.category,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get foodGroup => $composableBuilder(
    column: $table.foodGroup,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get shelfLifeDays => $composableBuilder(
    column: $table.shelfLifeDays,
    builder: (column) => ColumnFilters(column),
  );

  Expression<bool> ingredientsRefs(
    Expression<bool> Function($$IngredientsTableFilterComposer f) f,
  ) {
    final $$IngredientsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.category,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.category,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableFilterComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$IngredientCategoriesTableOrderingComposer
    extends Composer<_$GleanDatabase, $IngredientCategoriesTable> {
  $$IngredientCategoriesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get category => $composableBuilder(
    column: $table.category,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get foodGroup => $composableBuilder(
    column: $table.foodGroup,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get shelfLifeDays => $composableBuilder(
    column: $table.shelfLifeDays,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$IngredientCategoriesTableAnnotationComposer
    extends Composer<_$GleanDatabase, $IngredientCategoriesTable> {
  $$IngredientCategoriesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get category =>
      $composableBuilder(column: $table.category, builder: (column) => column);

  GeneratedColumn<String> get foodGroup =>
      $composableBuilder(column: $table.foodGroup, builder: (column) => column);

  GeneratedColumn<int> get shelfLifeDays => $composableBuilder(
    column: $table.shelfLifeDays,
    builder: (column) => column,
  );

  Expression<T> ingredientsRefs<T extends Object>(
    Expression<T> Function($$IngredientsTableAnnotationComposer a) f,
  ) {
    final $$IngredientsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.category,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.category,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableAnnotationComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$IngredientCategoriesTableTableManager
    extends
        RootTableManager<
          _$GleanDatabase,
          $IngredientCategoriesTable,
          IngredientCategory,
          $$IngredientCategoriesTableFilterComposer,
          $$IngredientCategoriesTableOrderingComposer,
          $$IngredientCategoriesTableAnnotationComposer,
          $$IngredientCategoriesTableCreateCompanionBuilder,
          $$IngredientCategoriesTableUpdateCompanionBuilder,
          (IngredientCategory, $$IngredientCategoriesTableReferences),
          IngredientCategory,
          PrefetchHooks Function({bool ingredientsRefs})
        > {
  $$IngredientCategoriesTableTableManager(
    _$GleanDatabase db,
    $IngredientCategoriesTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$IngredientCategoriesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$IngredientCategoriesTableOrderingComposer(
                $db: db,
                $table: table,
              ),
          createComputedFieldComposer: () =>
              $$IngredientCategoriesTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<String> category = const Value.absent(),
                Value<String> foodGroup = const Value.absent(),
                Value<int> shelfLifeDays = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => IngredientCategoriesCompanion(
                category: category,
                foodGroup: foodGroup,
                shelfLifeDays: shelfLifeDays,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String category,
                required String foodGroup,
                required int shelfLifeDays,
                Value<int> rowid = const Value.absent(),
              }) => IngredientCategoriesCompanion.insert(
                category: category,
                foodGroup: foodGroup,
                shelfLifeDays: shelfLifeDays,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$IngredientCategoriesTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({ingredientsRefs = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [if (ingredientsRefs) db.ingredients],
              addJoins: null,
              getPrefetchedDataCallback: (items) async {
                return [
                  if (ingredientsRefs)
                    await $_getPrefetchedData<
                      IngredientCategory,
                      $IngredientCategoriesTable,
                      Ingredient
                    >(
                      currentTable: table,
                      referencedTable: $$IngredientCategoriesTableReferences
                          ._ingredientsRefsTable(db),
                      managerFromTypedResult: (p0) =>
                          $$IngredientCategoriesTableReferences(
                            db,
                            table,
                            p0,
                          ).ingredientsRefs,
                      referencedItemsForCurrentItem: (item, referencedItems) =>
                          referencedItems.where(
                            (e) => e.category == item.category,
                          ),
                      typedResults: items,
                    ),
                ];
              },
            );
          },
        ),
      );
}

typedef $$IngredientCategoriesTableProcessedTableManager =
    ProcessedTableManager<
      _$GleanDatabase,
      $IngredientCategoriesTable,
      IngredientCategory,
      $$IngredientCategoriesTableFilterComposer,
      $$IngredientCategoriesTableOrderingComposer,
      $$IngredientCategoriesTableAnnotationComposer,
      $$IngredientCategoriesTableCreateCompanionBuilder,
      $$IngredientCategoriesTableUpdateCompanionBuilder,
      (IngredientCategory, $$IngredientCategoriesTableReferences),
      IngredientCategory,
      PrefetchHooks Function({bool ingredientsRefs})
    >;
typedef $$IngredientsTableCreateCompanionBuilder =
    IngredientsCompanion Function({
      Value<int> id,
      required String canonicalName,
      Value<String?> apiIngredientId,
      Value<String?> apiName,
      Value<String?> category,
      Value<String?> canonicalUnit,
      Value<bool> isStaple,
    });
typedef $$IngredientsTableUpdateCompanionBuilder =
    IngredientsCompanion Function({
      Value<int> id,
      Value<String> canonicalName,
      Value<String?> apiIngredientId,
      Value<String?> apiName,
      Value<String?> category,
      Value<String?> canonicalUnit,
      Value<bool> isStaple,
    });

final class $$IngredientsTableReferences
    extends BaseReferences<_$GleanDatabase, $IngredientsTable, Ingredient> {
  $$IngredientsTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static $IngredientCategoriesTable _categoryTable(_$GleanDatabase db) => db
      .ingredientCategories
      .createAlias('ingredients__category__ingredient_categories__category');

  $$IngredientCategoriesTableProcessedTableManager? get category {
    final $_column = $_itemColumn<String>('category');
    if ($_column == null) return null;
    final manager = $$IngredientCategoriesTableTableManager(
      $_db,
      $_db.ingredientCategories,
    ).filter((f) => f.category.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_categoryTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static MultiTypedResultKey<$PantryItemsTable, List<PantryItem>>
  _pantryItemsRefsTable(_$GleanDatabase db) => MultiTypedResultKey.fromTable(
    db.pantryItems,
    aliasName: 'ingredients__id__pantry_items__ingredient_id',
  );

  $$PantryItemsTableProcessedTableManager get pantryItemsRefs {
    final manager = $$PantryItemsTableTableManager(
      $_db,
      $_db.pantryItems,
    ).filter((f) => f.ingredientId.id.sqlEquals($_itemColumn<int>('id')!));

    final cache = $_typedResult.readTableOrNull(_pantryItemsRefsTable($_db));
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$RecipeIngredientsTable, List<RecipeIngredient>>
  _recipeIngredientsRefsTable(_$GleanDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.recipeIngredients,
        aliasName: 'ingredients__id__recipe_ingredients__ingredient_id',
      );

  $$RecipeIngredientsTableProcessedTableManager get recipeIngredientsRefs {
    final manager = $$RecipeIngredientsTableTableManager(
      $_db,
      $_db.recipeIngredients,
    ).filter((f) => f.ingredientId.id.sqlEquals($_itemColumn<int>('id')!));

    final cache = $_typedResult.readTableOrNull(
      _recipeIngredientsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$CookedAdjustmentsTable, List<CookedAdjustment>>
  _cookedAdjustmentsRefsTable(_$GleanDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.cookedAdjustments,
        aliasName: 'ingredients__id__cooked_adjustments__ingredient_id',
      );

  $$CookedAdjustmentsTableProcessedTableManager get cookedAdjustmentsRefs {
    final manager = $$CookedAdjustmentsTableTableManager(
      $_db,
      $_db.cookedAdjustments,
    ).filter((f) => f.ingredientId.id.sqlEquals($_itemColumn<int>('id')!));

    final cache = $_typedResult.readTableOrNull(
      _cookedAdjustmentsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$ShoppingListItemsTable, List<ShoppingListItem>>
  _shoppingListItemsRefsTable(_$GleanDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.shoppingListItems,
        aliasName: 'ingredients__id__shopping_list_items__ingredient_id',
      );

  $$ShoppingListItemsTableProcessedTableManager get shoppingListItemsRefs {
    final manager = $$ShoppingListItemsTableTableManager(
      $_db,
      $_db.shoppingListItems,
    ).filter((f) => f.ingredientId.id.sqlEquals($_itemColumn<int>('id')!));

    final cache = $_typedResult.readTableOrNull(
      _shoppingListItemsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$IngredientsTableFilterComposer
    extends Composer<_$GleanDatabase, $IngredientsTable> {
  $$IngredientsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get canonicalName => $composableBuilder(
    column: $table.canonicalName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get apiIngredientId => $composableBuilder(
    column: $table.apiIngredientId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get apiName => $composableBuilder(
    column: $table.apiName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get canonicalUnit => $composableBuilder(
    column: $table.canonicalUnit,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get isStaple => $composableBuilder(
    column: $table.isStaple,
    builder: (column) => ColumnFilters(column),
  );

  $$IngredientCategoriesTableFilterComposer get category {
    final $$IngredientCategoriesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.category,
      referencedTable: $db.ingredientCategories,
      getReferencedColumn: (t) => t.category,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientCategoriesTableFilterComposer(
            $db: $db,
            $table: $db.ingredientCategories,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<bool> pantryItemsRefs(
    Expression<bool> Function($$PantryItemsTableFilterComposer f) f,
  ) {
    final $$PantryItemsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.id,
      referencedTable: $db.pantryItems,
      getReferencedColumn: (t) => t.ingredientId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$PantryItemsTableFilterComposer(
            $db: $db,
            $table: $db.pantryItems,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> recipeIngredientsRefs(
    Expression<bool> Function($$RecipeIngredientsTableFilterComposer f) f,
  ) {
    final $$RecipeIngredientsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.id,
      referencedTable: $db.recipeIngredients,
      getReferencedColumn: (t) => t.ingredientId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipeIngredientsTableFilterComposer(
            $db: $db,
            $table: $db.recipeIngredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> cookedAdjustmentsRefs(
    Expression<bool> Function($$CookedAdjustmentsTableFilterComposer f) f,
  ) {
    final $$CookedAdjustmentsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.id,
      referencedTable: $db.cookedAdjustments,
      getReferencedColumn: (t) => t.ingredientId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CookedAdjustmentsTableFilterComposer(
            $db: $db,
            $table: $db.cookedAdjustments,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> shoppingListItemsRefs(
    Expression<bool> Function($$ShoppingListItemsTableFilterComposer f) f,
  ) {
    final $$ShoppingListItemsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.id,
      referencedTable: $db.shoppingListItems,
      getReferencedColumn: (t) => t.ingredientId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ShoppingListItemsTableFilterComposer(
            $db: $db,
            $table: $db.shoppingListItems,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$IngredientsTableOrderingComposer
    extends Composer<_$GleanDatabase, $IngredientsTable> {
  $$IngredientsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get canonicalName => $composableBuilder(
    column: $table.canonicalName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get apiIngredientId => $composableBuilder(
    column: $table.apiIngredientId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get apiName => $composableBuilder(
    column: $table.apiName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get canonicalUnit => $composableBuilder(
    column: $table.canonicalUnit,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get isStaple => $composableBuilder(
    column: $table.isStaple,
    builder: (column) => ColumnOrderings(column),
  );

  $$IngredientCategoriesTableOrderingComposer get category {
    final $$IngredientCategoriesTableOrderingComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.category,
          referencedTable: $db.ingredientCategories,
          getReferencedColumn: (t) => t.category,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$IngredientCategoriesTableOrderingComposer(
                $db: $db,
                $table: $db.ingredientCategories,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return composer;
  }
}

class $$IngredientsTableAnnotationComposer
    extends Composer<_$GleanDatabase, $IngredientsTable> {
  $$IngredientsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get canonicalName => $composableBuilder(
    column: $table.canonicalName,
    builder: (column) => column,
  );

  GeneratedColumn<String> get apiIngredientId => $composableBuilder(
    column: $table.apiIngredientId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get apiName =>
      $composableBuilder(column: $table.apiName, builder: (column) => column);

  GeneratedColumn<String> get canonicalUnit => $composableBuilder(
    column: $table.canonicalUnit,
    builder: (column) => column,
  );

  GeneratedColumn<bool> get isStaple =>
      $composableBuilder(column: $table.isStaple, builder: (column) => column);

  $$IngredientCategoriesTableAnnotationComposer get category {
    final $$IngredientCategoriesTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.category,
          referencedTable: $db.ingredientCategories,
          getReferencedColumn: (t) => t.category,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$IngredientCategoriesTableAnnotationComposer(
                $db: $db,
                $table: $db.ingredientCategories,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return composer;
  }

  Expression<T> pantryItemsRefs<T extends Object>(
    Expression<T> Function($$PantryItemsTableAnnotationComposer a) f,
  ) {
    final $$PantryItemsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.id,
      referencedTable: $db.pantryItems,
      getReferencedColumn: (t) => t.ingredientId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$PantryItemsTableAnnotationComposer(
            $db: $db,
            $table: $db.pantryItems,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> recipeIngredientsRefs<T extends Object>(
    Expression<T> Function($$RecipeIngredientsTableAnnotationComposer a) f,
  ) {
    final $$RecipeIngredientsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.id,
          referencedTable: $db.recipeIngredients,
          getReferencedColumn: (t) => t.ingredientId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$RecipeIngredientsTableAnnotationComposer(
                $db: $db,
                $table: $db.recipeIngredients,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }

  Expression<T> cookedAdjustmentsRefs<T extends Object>(
    Expression<T> Function($$CookedAdjustmentsTableAnnotationComposer a) f,
  ) {
    final $$CookedAdjustmentsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.id,
          referencedTable: $db.cookedAdjustments,
          getReferencedColumn: (t) => t.ingredientId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$CookedAdjustmentsTableAnnotationComposer(
                $db: $db,
                $table: $db.cookedAdjustments,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }

  Expression<T> shoppingListItemsRefs<T extends Object>(
    Expression<T> Function($$ShoppingListItemsTableAnnotationComposer a) f,
  ) {
    final $$ShoppingListItemsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.id,
          referencedTable: $db.shoppingListItems,
          getReferencedColumn: (t) => t.ingredientId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$ShoppingListItemsTableAnnotationComposer(
                $db: $db,
                $table: $db.shoppingListItems,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }
}

class $$IngredientsTableTableManager
    extends
        RootTableManager<
          _$GleanDatabase,
          $IngredientsTable,
          Ingredient,
          $$IngredientsTableFilterComposer,
          $$IngredientsTableOrderingComposer,
          $$IngredientsTableAnnotationComposer,
          $$IngredientsTableCreateCompanionBuilder,
          $$IngredientsTableUpdateCompanionBuilder,
          (Ingredient, $$IngredientsTableReferences),
          Ingredient,
          PrefetchHooks Function({
            bool category,
            bool pantryItemsRefs,
            bool recipeIngredientsRefs,
            bool cookedAdjustmentsRefs,
            bool shoppingListItemsRefs,
          })
        > {
  $$IngredientsTableTableManager(_$GleanDatabase db, $IngredientsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$IngredientsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$IngredientsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$IngredientsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> canonicalName = const Value.absent(),
                Value<String?> apiIngredientId = const Value.absent(),
                Value<String?> apiName = const Value.absent(),
                Value<String?> category = const Value.absent(),
                Value<String?> canonicalUnit = const Value.absent(),
                Value<bool> isStaple = const Value.absent(),
              }) => IngredientsCompanion(
                id: id,
                canonicalName: canonicalName,
                apiIngredientId: apiIngredientId,
                apiName: apiName,
                category: category,
                canonicalUnit: canonicalUnit,
                isStaple: isStaple,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String canonicalName,
                Value<String?> apiIngredientId = const Value.absent(),
                Value<String?> apiName = const Value.absent(),
                Value<String?> category = const Value.absent(),
                Value<String?> canonicalUnit = const Value.absent(),
                Value<bool> isStaple = const Value.absent(),
              }) => IngredientsCompanion.insert(
                id: id,
                canonicalName: canonicalName,
                apiIngredientId: apiIngredientId,
                apiName: apiName,
                category: category,
                canonicalUnit: canonicalUnit,
                isStaple: isStaple,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$IngredientsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({
                category = false,
                pantryItemsRefs = false,
                recipeIngredientsRefs = false,
                cookedAdjustmentsRefs = false,
                shoppingListItemsRefs = false,
              }) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [
                    if (pantryItemsRefs) db.pantryItems,
                    if (recipeIngredientsRefs) db.recipeIngredients,
                    if (cookedAdjustmentsRefs) db.cookedAdjustments,
                    if (shoppingListItemsRefs) db.shoppingListItems,
                  ],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (category) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.category,
                                    referencedTable:
                                        $$IngredientsTableReferences
                                            ._categoryTable(db),
                                    referencedColumn:
                                        $$IngredientsTableReferences
                                            ._categoryTable(db)
                                            .category,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [
                      if (pantryItemsRefs)
                        await $_getPrefetchedData<
                          Ingredient,
                          $IngredientsTable,
                          PantryItem
                        >(
                          currentTable: table,
                          referencedTable: $$IngredientsTableReferences
                              ._pantryItemsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$IngredientsTableReferences(
                                db,
                                table,
                                p0,
                              ).pantryItemsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.ingredientId == item.id,
                              ),
                          typedResults: items,
                        ),
                      if (recipeIngredientsRefs)
                        await $_getPrefetchedData<
                          Ingredient,
                          $IngredientsTable,
                          RecipeIngredient
                        >(
                          currentTable: table,
                          referencedTable: $$IngredientsTableReferences
                              ._recipeIngredientsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$IngredientsTableReferences(
                                db,
                                table,
                                p0,
                              ).recipeIngredientsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.ingredientId == item.id,
                              ),
                          typedResults: items,
                        ),
                      if (cookedAdjustmentsRefs)
                        await $_getPrefetchedData<
                          Ingredient,
                          $IngredientsTable,
                          CookedAdjustment
                        >(
                          currentTable: table,
                          referencedTable: $$IngredientsTableReferences
                              ._cookedAdjustmentsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$IngredientsTableReferences(
                                db,
                                table,
                                p0,
                              ).cookedAdjustmentsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.ingredientId == item.id,
                              ),
                          typedResults: items,
                        ),
                      if (shoppingListItemsRefs)
                        await $_getPrefetchedData<
                          Ingredient,
                          $IngredientsTable,
                          ShoppingListItem
                        >(
                          currentTable: table,
                          referencedTable: $$IngredientsTableReferences
                              ._shoppingListItemsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$IngredientsTableReferences(
                                db,
                                table,
                                p0,
                              ).shoppingListItemsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.ingredientId == item.id,
                              ),
                          typedResults: items,
                        ),
                    ];
                  },
                );
              },
        ),
      );
}

typedef $$IngredientsTableProcessedTableManager =
    ProcessedTableManager<
      _$GleanDatabase,
      $IngredientsTable,
      Ingredient,
      $$IngredientsTableFilterComposer,
      $$IngredientsTableOrderingComposer,
      $$IngredientsTableAnnotationComposer,
      $$IngredientsTableCreateCompanionBuilder,
      $$IngredientsTableUpdateCompanionBuilder,
      (Ingredient, $$IngredientsTableReferences),
      Ingredient,
      PrefetchHooks Function({
        bool category,
        bool pantryItemsRefs,
        bool recipeIngredientsRefs,
        bool cookedAdjustmentsRefs,
        bool shoppingListItemsRefs,
      })
    >;
typedef $$PantryItemsTableCreateCompanionBuilder =
    PantryItemsCompanion Function({
      Value<int> id,
      required String userId,
      required int ingredientId,
      required double quantity,
      required String unit,
      Value<double?> unitPrice,
      Value<String?> expiryDate,
      Value<String?> lastUsedAt,
      required String updatedAt,
    });
typedef $$PantryItemsTableUpdateCompanionBuilder =
    PantryItemsCompanion Function({
      Value<int> id,
      Value<String> userId,
      Value<int> ingredientId,
      Value<double> quantity,
      Value<String> unit,
      Value<double?> unitPrice,
      Value<String?> expiryDate,
      Value<String?> lastUsedAt,
      Value<String> updatedAt,
    });

final class $$PantryItemsTableReferences
    extends BaseReferences<_$GleanDatabase, $PantryItemsTable, PantryItem> {
  $$PantryItemsTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static $IngredientsTable _ingredientIdTable(_$GleanDatabase db) => db
      .ingredients
      .createAlias('pantry_items__ingredient_id__ingredients__id');

  $$IngredientsTableProcessedTableManager get ingredientId {
    final $_column = $_itemColumn<int>('ingredient_id')!;

    final manager = $$IngredientsTableTableManager(
      $_db,
      $_db.ingredients,
    ).filter((f) => f.id.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_ingredientIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$PantryItemsTableFilterComposer
    extends Composer<_$GleanDatabase, $PantryItemsTable> {
  $$PantryItemsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get userId => $composableBuilder(
    column: $table.userId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get quantity => $composableBuilder(
    column: $table.quantity,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get unit => $composableBuilder(
    column: $table.unit,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get unitPrice => $composableBuilder(
    column: $table.unitPrice,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get expiryDate => $composableBuilder(
    column: $table.expiryDate,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get lastUsedAt => $composableBuilder(
    column: $table.lastUsedAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnFilters(column),
  );

  $$IngredientsTableFilterComposer get ingredientId {
    final $$IngredientsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableFilterComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$PantryItemsTableOrderingComposer
    extends Composer<_$GleanDatabase, $PantryItemsTable> {
  $$PantryItemsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get userId => $composableBuilder(
    column: $table.userId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get quantity => $composableBuilder(
    column: $table.quantity,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get unit => $composableBuilder(
    column: $table.unit,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get unitPrice => $composableBuilder(
    column: $table.unitPrice,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get expiryDate => $composableBuilder(
    column: $table.expiryDate,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get lastUsedAt => $composableBuilder(
    column: $table.lastUsedAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnOrderings(column),
  );

  $$IngredientsTableOrderingComposer get ingredientId {
    final $$IngredientsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableOrderingComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$PantryItemsTableAnnotationComposer
    extends Composer<_$GleanDatabase, $PantryItemsTable> {
  $$PantryItemsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get userId =>
      $composableBuilder(column: $table.userId, builder: (column) => column);

  GeneratedColumn<double> get quantity =>
      $composableBuilder(column: $table.quantity, builder: (column) => column);

  GeneratedColumn<String> get unit =>
      $composableBuilder(column: $table.unit, builder: (column) => column);

  GeneratedColumn<double> get unitPrice =>
      $composableBuilder(column: $table.unitPrice, builder: (column) => column);

  GeneratedColumn<String> get expiryDate => $composableBuilder(
    column: $table.expiryDate,
    builder: (column) => column,
  );

  GeneratedColumn<String> get lastUsedAt => $composableBuilder(
    column: $table.lastUsedAt,
    builder: (column) => column,
  );

  GeneratedColumn<String> get updatedAt =>
      $composableBuilder(column: $table.updatedAt, builder: (column) => column);

  $$IngredientsTableAnnotationComposer get ingredientId {
    final $$IngredientsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableAnnotationComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$PantryItemsTableTableManager
    extends
        RootTableManager<
          _$GleanDatabase,
          $PantryItemsTable,
          PantryItem,
          $$PantryItemsTableFilterComposer,
          $$PantryItemsTableOrderingComposer,
          $$PantryItemsTableAnnotationComposer,
          $$PantryItemsTableCreateCompanionBuilder,
          $$PantryItemsTableUpdateCompanionBuilder,
          (PantryItem, $$PantryItemsTableReferences),
          PantryItem,
          PrefetchHooks Function({bool ingredientId})
        > {
  $$PantryItemsTableTableManager(_$GleanDatabase db, $PantryItemsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$PantryItemsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$PantryItemsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$PantryItemsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> userId = const Value.absent(),
                Value<int> ingredientId = const Value.absent(),
                Value<double> quantity = const Value.absent(),
                Value<String> unit = const Value.absent(),
                Value<double?> unitPrice = const Value.absent(),
                Value<String?> expiryDate = const Value.absent(),
                Value<String?> lastUsedAt = const Value.absent(),
                Value<String> updatedAt = const Value.absent(),
              }) => PantryItemsCompanion(
                id: id,
                userId: userId,
                ingredientId: ingredientId,
                quantity: quantity,
                unit: unit,
                unitPrice: unitPrice,
                expiryDate: expiryDate,
                lastUsedAt: lastUsedAt,
                updatedAt: updatedAt,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String userId,
                required int ingredientId,
                required double quantity,
                required String unit,
                Value<double?> unitPrice = const Value.absent(),
                Value<String?> expiryDate = const Value.absent(),
                Value<String?> lastUsedAt = const Value.absent(),
                required String updatedAt,
              }) => PantryItemsCompanion.insert(
                id: id,
                userId: userId,
                ingredientId: ingredientId,
                quantity: quantity,
                unit: unit,
                unitPrice: unitPrice,
                expiryDate: expiryDate,
                lastUsedAt: lastUsedAt,
                updatedAt: updatedAt,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$PantryItemsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({ingredientId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins:
                  <
                    T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic
                    >
                  >(state) {
                    if (ingredientId) {
                      state =
                          state.withJoin(
                                currentTable: table,
                                currentColumn: table.ingredientId,
                                referencedTable: $$PantryItemsTableReferences
                                    ._ingredientIdTable(db),
                                referencedColumn: $$PantryItemsTableReferences
                                    ._ingredientIdTable(db)
                                    .id,
                              )
                              as T;
                    }

                    return state;
                  },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ),
      );
}

typedef $$PantryItemsTableProcessedTableManager =
    ProcessedTableManager<
      _$GleanDatabase,
      $PantryItemsTable,
      PantryItem,
      $$PantryItemsTableFilterComposer,
      $$PantryItemsTableOrderingComposer,
      $$PantryItemsTableAnnotationComposer,
      $$PantryItemsTableCreateCompanionBuilder,
      $$PantryItemsTableUpdateCompanionBuilder,
      (PantryItem, $$PantryItemsTableReferences),
      PantryItem,
      PrefetchHooks Function({bool ingredientId})
    >;
typedef $$RecipesTableCreateCompanionBuilder =
    RecipesCompanion Function({
      Value<int> id,
      required String userId,
      Value<String?> externalId,
      required String title,
      Value<String?> sourceUrl,
      Value<String?> cuisine,
      Value<String?> difficulty,
      Value<int?> activeTimeMins,
      Value<int?> totalTimeMins,
      Value<String> notSuitableFor,
      Value<int?> yieldCount,
      Value<String?> nutrition,
      Value<String> instructions,
      Value<String?> lastCookedAt,
    });
typedef $$RecipesTableUpdateCompanionBuilder =
    RecipesCompanion Function({
      Value<int> id,
      Value<String> userId,
      Value<String?> externalId,
      Value<String> title,
      Value<String?> sourceUrl,
      Value<String?> cuisine,
      Value<String?> difficulty,
      Value<int?> activeTimeMins,
      Value<int?> totalTimeMins,
      Value<String> notSuitableFor,
      Value<int?> yieldCount,
      Value<String?> nutrition,
      Value<String> instructions,
      Value<String?> lastCookedAt,
    });

final class $$RecipesTableReferences
    extends BaseReferences<_$GleanDatabase, $RecipesTable, Recipe> {
  $$RecipesTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static MultiTypedResultKey<$RecipeDietaryFlagsTable, List<RecipeDietaryFlag>>
  _recipeDietaryFlagsRefsTable(_$GleanDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.recipeDietaryFlags,
        aliasName: 'recipes__id__recipe_dietary_flags__recipe_id',
      );

  $$RecipeDietaryFlagsTableProcessedTableManager get recipeDietaryFlagsRefs {
    final manager = $$RecipeDietaryFlagsTableTableManager(
      $_db,
      $_db.recipeDietaryFlags,
    ).filter((f) => f.recipeId.id.sqlEquals($_itemColumn<int>('id')!));

    final cache = $_typedResult.readTableOrNull(
      _recipeDietaryFlagsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$RecipeIngredientsTable, List<RecipeIngredient>>
  _recipeIngredientsRefsTable(_$GleanDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.recipeIngredients,
        aliasName: 'recipes__id__recipe_ingredients__recipe_id',
      );

  $$RecipeIngredientsTableProcessedTableManager get recipeIngredientsRefs {
    final manager = $$RecipeIngredientsTableTableManager(
      $_db,
      $_db.recipeIngredients,
    ).filter((f) => f.recipeId.id.sqlEquals($_itemColumn<int>('id')!));

    final cache = $_typedResult.readTableOrNull(
      _recipeIngredientsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$MealPlanEntriesTable, List<MealPlanEntry>>
  _mealPlanEntriesRefsTable(_$GleanDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.mealPlanEntries,
        aliasName: 'recipes__id__meal_plan_entries__recipe_id',
      );

  $$MealPlanEntriesTableProcessedTableManager get mealPlanEntriesRefs {
    final manager = $$MealPlanEntriesTableTableManager(
      $_db,
      $_db.mealPlanEntries,
    ).filter((f) => f.recipeId.id.sqlEquals($_itemColumn<int>('id')!));

    final cache = $_typedResult.readTableOrNull(
      _mealPlanEntriesRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$RecipesTableFilterComposer
    extends Composer<_$GleanDatabase, $RecipesTable> {
  $$RecipesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get userId => $composableBuilder(
    column: $table.userId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get externalId => $composableBuilder(
    column: $table.externalId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get title => $composableBuilder(
    column: $table.title,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get sourceUrl => $composableBuilder(
    column: $table.sourceUrl,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get cuisine => $composableBuilder(
    column: $table.cuisine,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get difficulty => $composableBuilder(
    column: $table.difficulty,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get activeTimeMins => $composableBuilder(
    column: $table.activeTimeMins,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get totalTimeMins => $composableBuilder(
    column: $table.totalTimeMins,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get notSuitableFor => $composableBuilder(
    column: $table.notSuitableFor,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get yieldCount => $composableBuilder(
    column: $table.yieldCount,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get nutrition => $composableBuilder(
    column: $table.nutrition,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get instructions => $composableBuilder(
    column: $table.instructions,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get lastCookedAt => $composableBuilder(
    column: $table.lastCookedAt,
    builder: (column) => ColumnFilters(column),
  );

  Expression<bool> recipeDietaryFlagsRefs(
    Expression<bool> Function($$RecipeDietaryFlagsTableFilterComposer f) f,
  ) {
    final $$RecipeDietaryFlagsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.id,
      referencedTable: $db.recipeDietaryFlags,
      getReferencedColumn: (t) => t.recipeId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipeDietaryFlagsTableFilterComposer(
            $db: $db,
            $table: $db.recipeDietaryFlags,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> recipeIngredientsRefs(
    Expression<bool> Function($$RecipeIngredientsTableFilterComposer f) f,
  ) {
    final $$RecipeIngredientsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.id,
      referencedTable: $db.recipeIngredients,
      getReferencedColumn: (t) => t.recipeId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipeIngredientsTableFilterComposer(
            $db: $db,
            $table: $db.recipeIngredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> mealPlanEntriesRefs(
    Expression<bool> Function($$MealPlanEntriesTableFilterComposer f) f,
  ) {
    final $$MealPlanEntriesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.id,
      referencedTable: $db.mealPlanEntries,
      getReferencedColumn: (t) => t.recipeId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$MealPlanEntriesTableFilterComposer(
            $db: $db,
            $table: $db.mealPlanEntries,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$RecipesTableOrderingComposer
    extends Composer<_$GleanDatabase, $RecipesTable> {
  $$RecipesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get userId => $composableBuilder(
    column: $table.userId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get externalId => $composableBuilder(
    column: $table.externalId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get title => $composableBuilder(
    column: $table.title,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get sourceUrl => $composableBuilder(
    column: $table.sourceUrl,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get cuisine => $composableBuilder(
    column: $table.cuisine,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get difficulty => $composableBuilder(
    column: $table.difficulty,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get activeTimeMins => $composableBuilder(
    column: $table.activeTimeMins,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get totalTimeMins => $composableBuilder(
    column: $table.totalTimeMins,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get notSuitableFor => $composableBuilder(
    column: $table.notSuitableFor,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get yieldCount => $composableBuilder(
    column: $table.yieldCount,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get nutrition => $composableBuilder(
    column: $table.nutrition,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get instructions => $composableBuilder(
    column: $table.instructions,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get lastCookedAt => $composableBuilder(
    column: $table.lastCookedAt,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$RecipesTableAnnotationComposer
    extends Composer<_$GleanDatabase, $RecipesTable> {
  $$RecipesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get userId =>
      $composableBuilder(column: $table.userId, builder: (column) => column);

  GeneratedColumn<String> get externalId => $composableBuilder(
    column: $table.externalId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get title =>
      $composableBuilder(column: $table.title, builder: (column) => column);

  GeneratedColumn<String> get sourceUrl =>
      $composableBuilder(column: $table.sourceUrl, builder: (column) => column);

  GeneratedColumn<String> get cuisine =>
      $composableBuilder(column: $table.cuisine, builder: (column) => column);

  GeneratedColumn<String> get difficulty => $composableBuilder(
    column: $table.difficulty,
    builder: (column) => column,
  );

  GeneratedColumn<int> get activeTimeMins => $composableBuilder(
    column: $table.activeTimeMins,
    builder: (column) => column,
  );

  GeneratedColumn<int> get totalTimeMins => $composableBuilder(
    column: $table.totalTimeMins,
    builder: (column) => column,
  );

  GeneratedColumn<String> get notSuitableFor => $composableBuilder(
    column: $table.notSuitableFor,
    builder: (column) => column,
  );

  GeneratedColumn<int> get yieldCount => $composableBuilder(
    column: $table.yieldCount,
    builder: (column) => column,
  );

  GeneratedColumn<String> get nutrition =>
      $composableBuilder(column: $table.nutrition, builder: (column) => column);

  GeneratedColumn<String> get instructions => $composableBuilder(
    column: $table.instructions,
    builder: (column) => column,
  );

  GeneratedColumn<String> get lastCookedAt => $composableBuilder(
    column: $table.lastCookedAt,
    builder: (column) => column,
  );

  Expression<T> recipeDietaryFlagsRefs<T extends Object>(
    Expression<T> Function($$RecipeDietaryFlagsTableAnnotationComposer a) f,
  ) {
    final $$RecipeDietaryFlagsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.id,
          referencedTable: $db.recipeDietaryFlags,
          getReferencedColumn: (t) => t.recipeId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$RecipeDietaryFlagsTableAnnotationComposer(
                $db: $db,
                $table: $db.recipeDietaryFlags,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }

  Expression<T> recipeIngredientsRefs<T extends Object>(
    Expression<T> Function($$RecipeIngredientsTableAnnotationComposer a) f,
  ) {
    final $$RecipeIngredientsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.id,
          referencedTable: $db.recipeIngredients,
          getReferencedColumn: (t) => t.recipeId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$RecipeIngredientsTableAnnotationComposer(
                $db: $db,
                $table: $db.recipeIngredients,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }

  Expression<T> mealPlanEntriesRefs<T extends Object>(
    Expression<T> Function($$MealPlanEntriesTableAnnotationComposer a) f,
  ) {
    final $$MealPlanEntriesTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.id,
      referencedTable: $db.mealPlanEntries,
      getReferencedColumn: (t) => t.recipeId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$MealPlanEntriesTableAnnotationComposer(
            $db: $db,
            $table: $db.mealPlanEntries,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$RecipesTableTableManager
    extends
        RootTableManager<
          _$GleanDatabase,
          $RecipesTable,
          Recipe,
          $$RecipesTableFilterComposer,
          $$RecipesTableOrderingComposer,
          $$RecipesTableAnnotationComposer,
          $$RecipesTableCreateCompanionBuilder,
          $$RecipesTableUpdateCompanionBuilder,
          (Recipe, $$RecipesTableReferences),
          Recipe,
          PrefetchHooks Function({
            bool recipeDietaryFlagsRefs,
            bool recipeIngredientsRefs,
            bool mealPlanEntriesRefs,
          })
        > {
  $$RecipesTableTableManager(_$GleanDatabase db, $RecipesTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$RecipesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$RecipesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$RecipesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> userId = const Value.absent(),
                Value<String?> externalId = const Value.absent(),
                Value<String> title = const Value.absent(),
                Value<String?> sourceUrl = const Value.absent(),
                Value<String?> cuisine = const Value.absent(),
                Value<String?> difficulty = const Value.absent(),
                Value<int?> activeTimeMins = const Value.absent(),
                Value<int?> totalTimeMins = const Value.absent(),
                Value<String> notSuitableFor = const Value.absent(),
                Value<int?> yieldCount = const Value.absent(),
                Value<String?> nutrition = const Value.absent(),
                Value<String> instructions = const Value.absent(),
                Value<String?> lastCookedAt = const Value.absent(),
              }) => RecipesCompanion(
                id: id,
                userId: userId,
                externalId: externalId,
                title: title,
                sourceUrl: sourceUrl,
                cuisine: cuisine,
                difficulty: difficulty,
                activeTimeMins: activeTimeMins,
                totalTimeMins: totalTimeMins,
                notSuitableFor: notSuitableFor,
                yieldCount: yieldCount,
                nutrition: nutrition,
                instructions: instructions,
                lastCookedAt: lastCookedAt,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String userId,
                Value<String?> externalId = const Value.absent(),
                required String title,
                Value<String?> sourceUrl = const Value.absent(),
                Value<String?> cuisine = const Value.absent(),
                Value<String?> difficulty = const Value.absent(),
                Value<int?> activeTimeMins = const Value.absent(),
                Value<int?> totalTimeMins = const Value.absent(),
                Value<String> notSuitableFor = const Value.absent(),
                Value<int?> yieldCount = const Value.absent(),
                Value<String?> nutrition = const Value.absent(),
                Value<String> instructions = const Value.absent(),
                Value<String?> lastCookedAt = const Value.absent(),
              }) => RecipesCompanion.insert(
                id: id,
                userId: userId,
                externalId: externalId,
                title: title,
                sourceUrl: sourceUrl,
                cuisine: cuisine,
                difficulty: difficulty,
                activeTimeMins: activeTimeMins,
                totalTimeMins: totalTimeMins,
                notSuitableFor: notSuitableFor,
                yieldCount: yieldCount,
                nutrition: nutrition,
                instructions: instructions,
                lastCookedAt: lastCookedAt,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$RecipesTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({
                recipeDietaryFlagsRefs = false,
                recipeIngredientsRefs = false,
                mealPlanEntriesRefs = false,
              }) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [
                    if (recipeDietaryFlagsRefs) db.recipeDietaryFlags,
                    if (recipeIngredientsRefs) db.recipeIngredients,
                    if (mealPlanEntriesRefs) db.mealPlanEntries,
                  ],
                  addJoins: null,
                  getPrefetchedDataCallback: (items) async {
                    return [
                      if (recipeDietaryFlagsRefs)
                        await $_getPrefetchedData<
                          Recipe,
                          $RecipesTable,
                          RecipeDietaryFlag
                        >(
                          currentTable: table,
                          referencedTable: $$RecipesTableReferences
                              ._recipeDietaryFlagsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$RecipesTableReferences(
                                db,
                                table,
                                p0,
                              ).recipeDietaryFlagsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.recipeId == item.id,
                              ),
                          typedResults: items,
                        ),
                      if (recipeIngredientsRefs)
                        await $_getPrefetchedData<
                          Recipe,
                          $RecipesTable,
                          RecipeIngredient
                        >(
                          currentTable: table,
                          referencedTable: $$RecipesTableReferences
                              ._recipeIngredientsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$RecipesTableReferences(
                                db,
                                table,
                                p0,
                              ).recipeIngredientsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.recipeId == item.id,
                              ),
                          typedResults: items,
                        ),
                      if (mealPlanEntriesRefs)
                        await $_getPrefetchedData<
                          Recipe,
                          $RecipesTable,
                          MealPlanEntry
                        >(
                          currentTable: table,
                          referencedTable: $$RecipesTableReferences
                              ._mealPlanEntriesRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$RecipesTableReferences(
                                db,
                                table,
                                p0,
                              ).mealPlanEntriesRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.recipeId == item.id,
                              ),
                          typedResults: items,
                        ),
                    ];
                  },
                );
              },
        ),
      );
}

typedef $$RecipesTableProcessedTableManager =
    ProcessedTableManager<
      _$GleanDatabase,
      $RecipesTable,
      Recipe,
      $$RecipesTableFilterComposer,
      $$RecipesTableOrderingComposer,
      $$RecipesTableAnnotationComposer,
      $$RecipesTableCreateCompanionBuilder,
      $$RecipesTableUpdateCompanionBuilder,
      (Recipe, $$RecipesTableReferences),
      Recipe,
      PrefetchHooks Function({
        bool recipeDietaryFlagsRefs,
        bool recipeIngredientsRefs,
        bool mealPlanEntriesRefs,
      })
    >;
typedef $$RecipeDietaryFlagsTableCreateCompanionBuilder =
    RecipeDietaryFlagsCompanion Function({
      required int recipeId,
      required String flag,
      Value<int> rowid,
    });
typedef $$RecipeDietaryFlagsTableUpdateCompanionBuilder =
    RecipeDietaryFlagsCompanion Function({
      Value<int> recipeId,
      Value<String> flag,
      Value<int> rowid,
    });

final class $$RecipeDietaryFlagsTableReferences
    extends
        BaseReferences<
          _$GleanDatabase,
          $RecipeDietaryFlagsTable,
          RecipeDietaryFlag
        > {
  $$RecipeDietaryFlagsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $RecipesTable _recipeIdTable(_$GleanDatabase db) =>
      db.recipes.createAlias('recipe_dietary_flags__recipe_id__recipes__id');

  $$RecipesTableProcessedTableManager get recipeId {
    final $_column = $_itemColumn<int>('recipe_id')!;

    final manager = $$RecipesTableTableManager(
      $_db,
      $_db.recipes,
    ).filter((f) => f.id.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_recipeIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$RecipeDietaryFlagsTableFilterComposer
    extends Composer<_$GleanDatabase, $RecipeDietaryFlagsTable> {
  $$RecipeDietaryFlagsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get flag => $composableBuilder(
    column: $table.flag,
    builder: (column) => ColumnFilters(column),
  );

  $$RecipesTableFilterComposer get recipeId {
    final $$RecipesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.recipeId,
      referencedTable: $db.recipes,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipesTableFilterComposer(
            $db: $db,
            $table: $db.recipes,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$RecipeDietaryFlagsTableOrderingComposer
    extends Composer<_$GleanDatabase, $RecipeDietaryFlagsTable> {
  $$RecipeDietaryFlagsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get flag => $composableBuilder(
    column: $table.flag,
    builder: (column) => ColumnOrderings(column),
  );

  $$RecipesTableOrderingComposer get recipeId {
    final $$RecipesTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.recipeId,
      referencedTable: $db.recipes,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipesTableOrderingComposer(
            $db: $db,
            $table: $db.recipes,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$RecipeDietaryFlagsTableAnnotationComposer
    extends Composer<_$GleanDatabase, $RecipeDietaryFlagsTable> {
  $$RecipeDietaryFlagsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get flag =>
      $composableBuilder(column: $table.flag, builder: (column) => column);

  $$RecipesTableAnnotationComposer get recipeId {
    final $$RecipesTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.recipeId,
      referencedTable: $db.recipes,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipesTableAnnotationComposer(
            $db: $db,
            $table: $db.recipes,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$RecipeDietaryFlagsTableTableManager
    extends
        RootTableManager<
          _$GleanDatabase,
          $RecipeDietaryFlagsTable,
          RecipeDietaryFlag,
          $$RecipeDietaryFlagsTableFilterComposer,
          $$RecipeDietaryFlagsTableOrderingComposer,
          $$RecipeDietaryFlagsTableAnnotationComposer,
          $$RecipeDietaryFlagsTableCreateCompanionBuilder,
          $$RecipeDietaryFlagsTableUpdateCompanionBuilder,
          (RecipeDietaryFlag, $$RecipeDietaryFlagsTableReferences),
          RecipeDietaryFlag,
          PrefetchHooks Function({bool recipeId})
        > {
  $$RecipeDietaryFlagsTableTableManager(
    _$GleanDatabase db,
    $RecipeDietaryFlagsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$RecipeDietaryFlagsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$RecipeDietaryFlagsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$RecipeDietaryFlagsTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<int> recipeId = const Value.absent(),
                Value<String> flag = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => RecipeDietaryFlagsCompanion(
                recipeId: recipeId,
                flag: flag,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required int recipeId,
                required String flag,
                Value<int> rowid = const Value.absent(),
              }) => RecipeDietaryFlagsCompanion.insert(
                recipeId: recipeId,
                flag: flag,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$RecipeDietaryFlagsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({recipeId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins:
                  <
                    T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic
                    >
                  >(state) {
                    if (recipeId) {
                      state =
                          state.withJoin(
                                currentTable: table,
                                currentColumn: table.recipeId,
                                referencedTable:
                                    $$RecipeDietaryFlagsTableReferences
                                        ._recipeIdTable(db),
                                referencedColumn:
                                    $$RecipeDietaryFlagsTableReferences
                                        ._recipeIdTable(db)
                                        .id,
                              )
                              as T;
                    }

                    return state;
                  },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ),
      );
}

typedef $$RecipeDietaryFlagsTableProcessedTableManager =
    ProcessedTableManager<
      _$GleanDatabase,
      $RecipeDietaryFlagsTable,
      RecipeDietaryFlag,
      $$RecipeDietaryFlagsTableFilterComposer,
      $$RecipeDietaryFlagsTableOrderingComposer,
      $$RecipeDietaryFlagsTableAnnotationComposer,
      $$RecipeDietaryFlagsTableCreateCompanionBuilder,
      $$RecipeDietaryFlagsTableUpdateCompanionBuilder,
      (RecipeDietaryFlag, $$RecipeDietaryFlagsTableReferences),
      RecipeDietaryFlag,
      PrefetchHooks Function({bool recipeId})
    >;
typedef $$RecipeIngredientsTableCreateCompanionBuilder =
    RecipeIngredientsCompanion Function({
      Value<int> id,
      required int recipeId,
      required int ingredientId,
      required double quantity,
      required String unit,
      Value<String?> preparation,
      Value<bool> isOptional,
      Value<String> substitutions,
    });
typedef $$RecipeIngredientsTableUpdateCompanionBuilder =
    RecipeIngredientsCompanion Function({
      Value<int> id,
      Value<int> recipeId,
      Value<int> ingredientId,
      Value<double> quantity,
      Value<String> unit,
      Value<String?> preparation,
      Value<bool> isOptional,
      Value<String> substitutions,
    });

final class $$RecipeIngredientsTableReferences
    extends
        BaseReferences<
          _$GleanDatabase,
          $RecipeIngredientsTable,
          RecipeIngredient
        > {
  $$RecipeIngredientsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $RecipesTable _recipeIdTable(_$GleanDatabase db) =>
      db.recipes.createAlias('recipe_ingredients__recipe_id__recipes__id');

  $$RecipesTableProcessedTableManager get recipeId {
    final $_column = $_itemColumn<int>('recipe_id')!;

    final manager = $$RecipesTableTableManager(
      $_db,
      $_db.recipes,
    ).filter((f) => f.id.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_recipeIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $IngredientsTable _ingredientIdTable(_$GleanDatabase db) => db
      .ingredients
      .createAlias('recipe_ingredients__ingredient_id__ingredients__id');

  $$IngredientsTableProcessedTableManager get ingredientId {
    final $_column = $_itemColumn<int>('ingredient_id')!;

    final manager = $$IngredientsTableTableManager(
      $_db,
      $_db.ingredients,
    ).filter((f) => f.id.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_ingredientIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$RecipeIngredientsTableFilterComposer
    extends Composer<_$GleanDatabase, $RecipeIngredientsTable> {
  $$RecipeIngredientsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get quantity => $composableBuilder(
    column: $table.quantity,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get unit => $composableBuilder(
    column: $table.unit,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get preparation => $composableBuilder(
    column: $table.preparation,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get isOptional => $composableBuilder(
    column: $table.isOptional,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get substitutions => $composableBuilder(
    column: $table.substitutions,
    builder: (column) => ColumnFilters(column),
  );

  $$RecipesTableFilterComposer get recipeId {
    final $$RecipesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.recipeId,
      referencedTable: $db.recipes,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipesTableFilterComposer(
            $db: $db,
            $table: $db.recipes,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$IngredientsTableFilterComposer get ingredientId {
    final $$IngredientsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableFilterComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$RecipeIngredientsTableOrderingComposer
    extends Composer<_$GleanDatabase, $RecipeIngredientsTable> {
  $$RecipeIngredientsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get quantity => $composableBuilder(
    column: $table.quantity,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get unit => $composableBuilder(
    column: $table.unit,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get preparation => $composableBuilder(
    column: $table.preparation,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get isOptional => $composableBuilder(
    column: $table.isOptional,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get substitutions => $composableBuilder(
    column: $table.substitutions,
    builder: (column) => ColumnOrderings(column),
  );

  $$RecipesTableOrderingComposer get recipeId {
    final $$RecipesTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.recipeId,
      referencedTable: $db.recipes,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipesTableOrderingComposer(
            $db: $db,
            $table: $db.recipes,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$IngredientsTableOrderingComposer get ingredientId {
    final $$IngredientsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableOrderingComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$RecipeIngredientsTableAnnotationComposer
    extends Composer<_$GleanDatabase, $RecipeIngredientsTable> {
  $$RecipeIngredientsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<double> get quantity =>
      $composableBuilder(column: $table.quantity, builder: (column) => column);

  GeneratedColumn<String> get unit =>
      $composableBuilder(column: $table.unit, builder: (column) => column);

  GeneratedColumn<String> get preparation => $composableBuilder(
    column: $table.preparation,
    builder: (column) => column,
  );

  GeneratedColumn<bool> get isOptional => $composableBuilder(
    column: $table.isOptional,
    builder: (column) => column,
  );

  GeneratedColumn<String> get substitutions => $composableBuilder(
    column: $table.substitutions,
    builder: (column) => column,
  );

  $$RecipesTableAnnotationComposer get recipeId {
    final $$RecipesTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.recipeId,
      referencedTable: $db.recipes,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipesTableAnnotationComposer(
            $db: $db,
            $table: $db.recipes,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$IngredientsTableAnnotationComposer get ingredientId {
    final $$IngredientsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableAnnotationComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$RecipeIngredientsTableTableManager
    extends
        RootTableManager<
          _$GleanDatabase,
          $RecipeIngredientsTable,
          RecipeIngredient,
          $$RecipeIngredientsTableFilterComposer,
          $$RecipeIngredientsTableOrderingComposer,
          $$RecipeIngredientsTableAnnotationComposer,
          $$RecipeIngredientsTableCreateCompanionBuilder,
          $$RecipeIngredientsTableUpdateCompanionBuilder,
          (RecipeIngredient, $$RecipeIngredientsTableReferences),
          RecipeIngredient,
          PrefetchHooks Function({bool recipeId, bool ingredientId})
        > {
  $$RecipeIngredientsTableTableManager(
    _$GleanDatabase db,
    $RecipeIngredientsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$RecipeIngredientsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$RecipeIngredientsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$RecipeIngredientsTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<int> recipeId = const Value.absent(),
                Value<int> ingredientId = const Value.absent(),
                Value<double> quantity = const Value.absent(),
                Value<String> unit = const Value.absent(),
                Value<String?> preparation = const Value.absent(),
                Value<bool> isOptional = const Value.absent(),
                Value<String> substitutions = const Value.absent(),
              }) => RecipeIngredientsCompanion(
                id: id,
                recipeId: recipeId,
                ingredientId: ingredientId,
                quantity: quantity,
                unit: unit,
                preparation: preparation,
                isOptional: isOptional,
                substitutions: substitutions,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required int recipeId,
                required int ingredientId,
                required double quantity,
                required String unit,
                Value<String?> preparation = const Value.absent(),
                Value<bool> isOptional = const Value.absent(),
                Value<String> substitutions = const Value.absent(),
              }) => RecipeIngredientsCompanion.insert(
                id: id,
                recipeId: recipeId,
                ingredientId: ingredientId,
                quantity: quantity,
                unit: unit,
                preparation: preparation,
                isOptional: isOptional,
                substitutions: substitutions,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$RecipeIngredientsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({recipeId = false, ingredientId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins:
                  <
                    T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic
                    >
                  >(state) {
                    if (recipeId) {
                      state =
                          state.withJoin(
                                currentTable: table,
                                currentColumn: table.recipeId,
                                referencedTable:
                                    $$RecipeIngredientsTableReferences
                                        ._recipeIdTable(db),
                                referencedColumn:
                                    $$RecipeIngredientsTableReferences
                                        ._recipeIdTable(db)
                                        .id,
                              )
                              as T;
                    }
                    if (ingredientId) {
                      state =
                          state.withJoin(
                                currentTable: table,
                                currentColumn: table.ingredientId,
                                referencedTable:
                                    $$RecipeIngredientsTableReferences
                                        ._ingredientIdTable(db),
                                referencedColumn:
                                    $$RecipeIngredientsTableReferences
                                        ._ingredientIdTable(db)
                                        .id,
                              )
                              as T;
                    }

                    return state;
                  },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ),
      );
}

typedef $$RecipeIngredientsTableProcessedTableManager =
    ProcessedTableManager<
      _$GleanDatabase,
      $RecipeIngredientsTable,
      RecipeIngredient,
      $$RecipeIngredientsTableFilterComposer,
      $$RecipeIngredientsTableOrderingComposer,
      $$RecipeIngredientsTableAnnotationComposer,
      $$RecipeIngredientsTableCreateCompanionBuilder,
      $$RecipeIngredientsTableUpdateCompanionBuilder,
      (RecipeIngredient, $$RecipeIngredientsTableReferences),
      RecipeIngredient,
      PrefetchHooks Function({bool recipeId, bool ingredientId})
    >;
typedef $$MealPlanEntriesTableCreateCompanionBuilder =
    MealPlanEntriesCompanion Function({
      Value<int> id,
      required String userId,
      Value<int?> recipeId,
      required String recipeTitle,
      required String plannedDate,
      Value<String?> cookedAt,
      Value<String?> externalIdSnapshot,
      Value<String?> previousRecipeCookedAt,
      required int servings,
    });
typedef $$MealPlanEntriesTableUpdateCompanionBuilder =
    MealPlanEntriesCompanion Function({
      Value<int> id,
      Value<String> userId,
      Value<int?> recipeId,
      Value<String> recipeTitle,
      Value<String> plannedDate,
      Value<String?> cookedAt,
      Value<String?> externalIdSnapshot,
      Value<String?> previousRecipeCookedAt,
      Value<int> servings,
    });

final class $$MealPlanEntriesTableReferences
    extends
        BaseReferences<_$GleanDatabase, $MealPlanEntriesTable, MealPlanEntry> {
  $$MealPlanEntriesTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $RecipesTable _recipeIdTable(_$GleanDatabase db) =>
      db.recipes.createAlias('meal_plan_entries__recipe_id__recipes__id');

  $$RecipesTableProcessedTableManager? get recipeId {
    final $_column = $_itemColumn<int>('recipe_id');
    if ($_column == null) return null;
    final manager = $$RecipesTableTableManager(
      $_db,
      $_db.recipes,
    ).filter((f) => f.id.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_recipeIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static MultiTypedResultKey<$CookedAdjustmentsTable, List<CookedAdjustment>>
  _cookedAdjustmentsRefsTable(_$GleanDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.cookedAdjustments,
        aliasName:
            'meal_plan_entries__id__cooked_adjustments__meal_plan_entry_id',
      );

  $$CookedAdjustmentsTableProcessedTableManager get cookedAdjustmentsRefs {
    final manager = $$CookedAdjustmentsTableTableManager(
      $_db,
      $_db.cookedAdjustments,
    ).filter((f) => f.mealPlanEntryId.id.sqlEquals($_itemColumn<int>('id')!));

    final cache = $_typedResult.readTableOrNull(
      _cookedAdjustmentsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$ShoppingListItemsTable, List<ShoppingListItem>>
  _shoppingListItemsRefsTable(
    _$GleanDatabase db,
  ) => MultiTypedResultKey.fromTable(
    db.shoppingListItems,
    aliasName:
        'meal_plan_entries__id__shopping_list_items__source_meal_plan_entry_id',
  );

  $$ShoppingListItemsTableProcessedTableManager get shoppingListItemsRefs {
    final manager =
        $$ShoppingListItemsTableTableManager(
          $_db,
          $_db.shoppingListItems,
        ).filter(
          (f) => f.sourceMealPlanEntryId.id.sqlEquals($_itemColumn<int>('id')!),
        );

    final cache = $_typedResult.readTableOrNull(
      _shoppingListItemsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$MealPlanEntriesTableFilterComposer
    extends Composer<_$GleanDatabase, $MealPlanEntriesTable> {
  $$MealPlanEntriesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get userId => $composableBuilder(
    column: $table.userId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get recipeTitle => $composableBuilder(
    column: $table.recipeTitle,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get plannedDate => $composableBuilder(
    column: $table.plannedDate,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get cookedAt => $composableBuilder(
    column: $table.cookedAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get externalIdSnapshot => $composableBuilder(
    column: $table.externalIdSnapshot,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get previousRecipeCookedAt => $composableBuilder(
    column: $table.previousRecipeCookedAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get servings => $composableBuilder(
    column: $table.servings,
    builder: (column) => ColumnFilters(column),
  );

  $$RecipesTableFilterComposer get recipeId {
    final $$RecipesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.recipeId,
      referencedTable: $db.recipes,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipesTableFilterComposer(
            $db: $db,
            $table: $db.recipes,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<bool> cookedAdjustmentsRefs(
    Expression<bool> Function($$CookedAdjustmentsTableFilterComposer f) f,
  ) {
    final $$CookedAdjustmentsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.id,
      referencedTable: $db.cookedAdjustments,
      getReferencedColumn: (t) => t.mealPlanEntryId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CookedAdjustmentsTableFilterComposer(
            $db: $db,
            $table: $db.cookedAdjustments,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> shoppingListItemsRefs(
    Expression<bool> Function($$ShoppingListItemsTableFilterComposer f) f,
  ) {
    final $$ShoppingListItemsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.id,
      referencedTable: $db.shoppingListItems,
      getReferencedColumn: (t) => t.sourceMealPlanEntryId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ShoppingListItemsTableFilterComposer(
            $db: $db,
            $table: $db.shoppingListItems,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$MealPlanEntriesTableOrderingComposer
    extends Composer<_$GleanDatabase, $MealPlanEntriesTable> {
  $$MealPlanEntriesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get userId => $composableBuilder(
    column: $table.userId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get recipeTitle => $composableBuilder(
    column: $table.recipeTitle,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get plannedDate => $composableBuilder(
    column: $table.plannedDate,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get cookedAt => $composableBuilder(
    column: $table.cookedAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get externalIdSnapshot => $composableBuilder(
    column: $table.externalIdSnapshot,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get previousRecipeCookedAt => $composableBuilder(
    column: $table.previousRecipeCookedAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get servings => $composableBuilder(
    column: $table.servings,
    builder: (column) => ColumnOrderings(column),
  );

  $$RecipesTableOrderingComposer get recipeId {
    final $$RecipesTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.recipeId,
      referencedTable: $db.recipes,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipesTableOrderingComposer(
            $db: $db,
            $table: $db.recipes,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$MealPlanEntriesTableAnnotationComposer
    extends Composer<_$GleanDatabase, $MealPlanEntriesTable> {
  $$MealPlanEntriesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get userId =>
      $composableBuilder(column: $table.userId, builder: (column) => column);

  GeneratedColumn<String> get recipeTitle => $composableBuilder(
    column: $table.recipeTitle,
    builder: (column) => column,
  );

  GeneratedColumn<String> get plannedDate => $composableBuilder(
    column: $table.plannedDate,
    builder: (column) => column,
  );

  GeneratedColumn<String> get cookedAt =>
      $composableBuilder(column: $table.cookedAt, builder: (column) => column);

  GeneratedColumn<String> get externalIdSnapshot => $composableBuilder(
    column: $table.externalIdSnapshot,
    builder: (column) => column,
  );

  GeneratedColumn<String> get previousRecipeCookedAt => $composableBuilder(
    column: $table.previousRecipeCookedAt,
    builder: (column) => column,
  );

  GeneratedColumn<int> get servings =>
      $composableBuilder(column: $table.servings, builder: (column) => column);

  $$RecipesTableAnnotationComposer get recipeId {
    final $$RecipesTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.recipeId,
      referencedTable: $db.recipes,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RecipesTableAnnotationComposer(
            $db: $db,
            $table: $db.recipes,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<T> cookedAdjustmentsRefs<T extends Object>(
    Expression<T> Function($$CookedAdjustmentsTableAnnotationComposer a) f,
  ) {
    final $$CookedAdjustmentsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.id,
          referencedTable: $db.cookedAdjustments,
          getReferencedColumn: (t) => t.mealPlanEntryId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$CookedAdjustmentsTableAnnotationComposer(
                $db: $db,
                $table: $db.cookedAdjustments,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }

  Expression<T> shoppingListItemsRefs<T extends Object>(
    Expression<T> Function($$ShoppingListItemsTableAnnotationComposer a) f,
  ) {
    final $$ShoppingListItemsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.id,
          referencedTable: $db.shoppingListItems,
          getReferencedColumn: (t) => t.sourceMealPlanEntryId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$ShoppingListItemsTableAnnotationComposer(
                $db: $db,
                $table: $db.shoppingListItems,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }
}

class $$MealPlanEntriesTableTableManager
    extends
        RootTableManager<
          _$GleanDatabase,
          $MealPlanEntriesTable,
          MealPlanEntry,
          $$MealPlanEntriesTableFilterComposer,
          $$MealPlanEntriesTableOrderingComposer,
          $$MealPlanEntriesTableAnnotationComposer,
          $$MealPlanEntriesTableCreateCompanionBuilder,
          $$MealPlanEntriesTableUpdateCompanionBuilder,
          (MealPlanEntry, $$MealPlanEntriesTableReferences),
          MealPlanEntry,
          PrefetchHooks Function({
            bool recipeId,
            bool cookedAdjustmentsRefs,
            bool shoppingListItemsRefs,
          })
        > {
  $$MealPlanEntriesTableTableManager(
    _$GleanDatabase db,
    $MealPlanEntriesTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$MealPlanEntriesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$MealPlanEntriesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$MealPlanEntriesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> userId = const Value.absent(),
                Value<int?> recipeId = const Value.absent(),
                Value<String> recipeTitle = const Value.absent(),
                Value<String> plannedDate = const Value.absent(),
                Value<String?> cookedAt = const Value.absent(),
                Value<String?> externalIdSnapshot = const Value.absent(),
                Value<String?> previousRecipeCookedAt = const Value.absent(),
                Value<int> servings = const Value.absent(),
              }) => MealPlanEntriesCompanion(
                id: id,
                userId: userId,
                recipeId: recipeId,
                recipeTitle: recipeTitle,
                plannedDate: plannedDate,
                cookedAt: cookedAt,
                externalIdSnapshot: externalIdSnapshot,
                previousRecipeCookedAt: previousRecipeCookedAt,
                servings: servings,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String userId,
                Value<int?> recipeId = const Value.absent(),
                required String recipeTitle,
                required String plannedDate,
                Value<String?> cookedAt = const Value.absent(),
                Value<String?> externalIdSnapshot = const Value.absent(),
                Value<String?> previousRecipeCookedAt = const Value.absent(),
                required int servings,
              }) => MealPlanEntriesCompanion.insert(
                id: id,
                userId: userId,
                recipeId: recipeId,
                recipeTitle: recipeTitle,
                plannedDate: plannedDate,
                cookedAt: cookedAt,
                externalIdSnapshot: externalIdSnapshot,
                previousRecipeCookedAt: previousRecipeCookedAt,
                servings: servings,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$MealPlanEntriesTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({
                recipeId = false,
                cookedAdjustmentsRefs = false,
                shoppingListItemsRefs = false,
              }) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [
                    if (cookedAdjustmentsRefs) db.cookedAdjustments,
                    if (shoppingListItemsRefs) db.shoppingListItems,
                  ],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (recipeId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.recipeId,
                                    referencedTable:
                                        $$MealPlanEntriesTableReferences
                                            ._recipeIdTable(db),
                                    referencedColumn:
                                        $$MealPlanEntriesTableReferences
                                            ._recipeIdTable(db)
                                            .id,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [
                      if (cookedAdjustmentsRefs)
                        await $_getPrefetchedData<
                          MealPlanEntry,
                          $MealPlanEntriesTable,
                          CookedAdjustment
                        >(
                          currentTable: table,
                          referencedTable: $$MealPlanEntriesTableReferences
                              ._cookedAdjustmentsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$MealPlanEntriesTableReferences(
                                db,
                                table,
                                p0,
                              ).cookedAdjustmentsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.mealPlanEntryId == item.id,
                              ),
                          typedResults: items,
                        ),
                      if (shoppingListItemsRefs)
                        await $_getPrefetchedData<
                          MealPlanEntry,
                          $MealPlanEntriesTable,
                          ShoppingListItem
                        >(
                          currentTable: table,
                          referencedTable: $$MealPlanEntriesTableReferences
                              ._shoppingListItemsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$MealPlanEntriesTableReferences(
                                db,
                                table,
                                p0,
                              ).shoppingListItemsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.sourceMealPlanEntryId == item.id,
                              ),
                          typedResults: items,
                        ),
                    ];
                  },
                );
              },
        ),
      );
}

typedef $$MealPlanEntriesTableProcessedTableManager =
    ProcessedTableManager<
      _$GleanDatabase,
      $MealPlanEntriesTable,
      MealPlanEntry,
      $$MealPlanEntriesTableFilterComposer,
      $$MealPlanEntriesTableOrderingComposer,
      $$MealPlanEntriesTableAnnotationComposer,
      $$MealPlanEntriesTableCreateCompanionBuilder,
      $$MealPlanEntriesTableUpdateCompanionBuilder,
      (MealPlanEntry, $$MealPlanEntriesTableReferences),
      MealPlanEntry,
      PrefetchHooks Function({
        bool recipeId,
        bool cookedAdjustmentsRefs,
        bool shoppingListItemsRefs,
      })
    >;
typedef $$CookedAdjustmentsTableCreateCompanionBuilder =
    CookedAdjustmentsCompanion Function({
      Value<int> id,
      required String userId,
      required int mealPlanEntryId,
      required int ingredientId,
      required double amountDeducted,
      required String unit,
      Value<String?> previousLastUsedAt,
      required String createdAt,
    });
typedef $$CookedAdjustmentsTableUpdateCompanionBuilder =
    CookedAdjustmentsCompanion Function({
      Value<int> id,
      Value<String> userId,
      Value<int> mealPlanEntryId,
      Value<int> ingredientId,
      Value<double> amountDeducted,
      Value<String> unit,
      Value<String?> previousLastUsedAt,
      Value<String> createdAt,
    });

final class $$CookedAdjustmentsTableReferences
    extends
        BaseReferences<
          _$GleanDatabase,
          $CookedAdjustmentsTable,
          CookedAdjustment
        > {
  $$CookedAdjustmentsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $MealPlanEntriesTable _mealPlanEntryIdTable(_$GleanDatabase db) =>
      db.mealPlanEntries.createAlias(
        'cooked_adjustments__meal_plan_entry_id__meal_plan_entries__id',
      );

  $$MealPlanEntriesTableProcessedTableManager get mealPlanEntryId {
    final $_column = $_itemColumn<int>('meal_plan_entry_id')!;

    final manager = $$MealPlanEntriesTableTableManager(
      $_db,
      $_db.mealPlanEntries,
    ).filter((f) => f.id.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_mealPlanEntryIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $IngredientsTable _ingredientIdTable(_$GleanDatabase db) => db
      .ingredients
      .createAlias('cooked_adjustments__ingredient_id__ingredients__id');

  $$IngredientsTableProcessedTableManager get ingredientId {
    final $_column = $_itemColumn<int>('ingredient_id')!;

    final manager = $$IngredientsTableTableManager(
      $_db,
      $_db.ingredients,
    ).filter((f) => f.id.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_ingredientIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$CookedAdjustmentsTableFilterComposer
    extends Composer<_$GleanDatabase, $CookedAdjustmentsTable> {
  $$CookedAdjustmentsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get userId => $composableBuilder(
    column: $table.userId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get amountDeducted => $composableBuilder(
    column: $table.amountDeducted,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get unit => $composableBuilder(
    column: $table.unit,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get previousLastUsedAt => $composableBuilder(
    column: $table.previousLastUsedAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnFilters(column),
  );

  $$MealPlanEntriesTableFilterComposer get mealPlanEntryId {
    final $$MealPlanEntriesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.mealPlanEntryId,
      referencedTable: $db.mealPlanEntries,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$MealPlanEntriesTableFilterComposer(
            $db: $db,
            $table: $db.mealPlanEntries,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$IngredientsTableFilterComposer get ingredientId {
    final $$IngredientsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableFilterComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$CookedAdjustmentsTableOrderingComposer
    extends Composer<_$GleanDatabase, $CookedAdjustmentsTable> {
  $$CookedAdjustmentsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get userId => $composableBuilder(
    column: $table.userId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get amountDeducted => $composableBuilder(
    column: $table.amountDeducted,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get unit => $composableBuilder(
    column: $table.unit,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get previousLastUsedAt => $composableBuilder(
    column: $table.previousLastUsedAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnOrderings(column),
  );

  $$MealPlanEntriesTableOrderingComposer get mealPlanEntryId {
    final $$MealPlanEntriesTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.mealPlanEntryId,
      referencedTable: $db.mealPlanEntries,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$MealPlanEntriesTableOrderingComposer(
            $db: $db,
            $table: $db.mealPlanEntries,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$IngredientsTableOrderingComposer get ingredientId {
    final $$IngredientsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableOrderingComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$CookedAdjustmentsTableAnnotationComposer
    extends Composer<_$GleanDatabase, $CookedAdjustmentsTable> {
  $$CookedAdjustmentsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get userId =>
      $composableBuilder(column: $table.userId, builder: (column) => column);

  GeneratedColumn<double> get amountDeducted => $composableBuilder(
    column: $table.amountDeducted,
    builder: (column) => column,
  );

  GeneratedColumn<String> get unit =>
      $composableBuilder(column: $table.unit, builder: (column) => column);

  GeneratedColumn<String> get previousLastUsedAt => $composableBuilder(
    column: $table.previousLastUsedAt,
    builder: (column) => column,
  );

  GeneratedColumn<String> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);

  $$MealPlanEntriesTableAnnotationComposer get mealPlanEntryId {
    final $$MealPlanEntriesTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.mealPlanEntryId,
      referencedTable: $db.mealPlanEntries,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$MealPlanEntriesTableAnnotationComposer(
            $db: $db,
            $table: $db.mealPlanEntries,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$IngredientsTableAnnotationComposer get ingredientId {
    final $$IngredientsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableAnnotationComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$CookedAdjustmentsTableTableManager
    extends
        RootTableManager<
          _$GleanDatabase,
          $CookedAdjustmentsTable,
          CookedAdjustment,
          $$CookedAdjustmentsTableFilterComposer,
          $$CookedAdjustmentsTableOrderingComposer,
          $$CookedAdjustmentsTableAnnotationComposer,
          $$CookedAdjustmentsTableCreateCompanionBuilder,
          $$CookedAdjustmentsTableUpdateCompanionBuilder,
          (CookedAdjustment, $$CookedAdjustmentsTableReferences),
          CookedAdjustment,
          PrefetchHooks Function({bool mealPlanEntryId, bool ingredientId})
        > {
  $$CookedAdjustmentsTableTableManager(
    _$GleanDatabase db,
    $CookedAdjustmentsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$CookedAdjustmentsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$CookedAdjustmentsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$CookedAdjustmentsTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> userId = const Value.absent(),
                Value<int> mealPlanEntryId = const Value.absent(),
                Value<int> ingredientId = const Value.absent(),
                Value<double> amountDeducted = const Value.absent(),
                Value<String> unit = const Value.absent(),
                Value<String?> previousLastUsedAt = const Value.absent(),
                Value<String> createdAt = const Value.absent(),
              }) => CookedAdjustmentsCompanion(
                id: id,
                userId: userId,
                mealPlanEntryId: mealPlanEntryId,
                ingredientId: ingredientId,
                amountDeducted: amountDeducted,
                unit: unit,
                previousLastUsedAt: previousLastUsedAt,
                createdAt: createdAt,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String userId,
                required int mealPlanEntryId,
                required int ingredientId,
                required double amountDeducted,
                required String unit,
                Value<String?> previousLastUsedAt = const Value.absent(),
                required String createdAt,
              }) => CookedAdjustmentsCompanion.insert(
                id: id,
                userId: userId,
                mealPlanEntryId: mealPlanEntryId,
                ingredientId: ingredientId,
                amountDeducted: amountDeducted,
                unit: unit,
                previousLastUsedAt: previousLastUsedAt,
                createdAt: createdAt,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$CookedAdjustmentsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({mealPlanEntryId = false, ingredientId = false}) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (mealPlanEntryId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.mealPlanEntryId,
                                    referencedTable:
                                        $$CookedAdjustmentsTableReferences
                                            ._mealPlanEntryIdTable(db),
                                    referencedColumn:
                                        $$CookedAdjustmentsTableReferences
                                            ._mealPlanEntryIdTable(db)
                                            .id,
                                  )
                                  as T;
                        }
                        if (ingredientId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.ingredientId,
                                    referencedTable:
                                        $$CookedAdjustmentsTableReferences
                                            ._ingredientIdTable(db),
                                    referencedColumn:
                                        $$CookedAdjustmentsTableReferences
                                            ._ingredientIdTable(db)
                                            .id,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [];
                  },
                );
              },
        ),
      );
}

typedef $$CookedAdjustmentsTableProcessedTableManager =
    ProcessedTableManager<
      _$GleanDatabase,
      $CookedAdjustmentsTable,
      CookedAdjustment,
      $$CookedAdjustmentsTableFilterComposer,
      $$CookedAdjustmentsTableOrderingComposer,
      $$CookedAdjustmentsTableAnnotationComposer,
      $$CookedAdjustmentsTableCreateCompanionBuilder,
      $$CookedAdjustmentsTableUpdateCompanionBuilder,
      (CookedAdjustment, $$CookedAdjustmentsTableReferences),
      CookedAdjustment,
      PrefetchHooks Function({bool mealPlanEntryId, bool ingredientId})
    >;
typedef $$ShoppingListItemsTableCreateCompanionBuilder =
    ShoppingListItemsCompanion Function({
      Value<int> id,
      required String userId,
      required int ingredientId,
      required String name,
      Value<double?> quantity,
      Value<String?> unit,
      Value<String> source,
      Value<bool> isRequirement,
      Value<bool> isChecked,
      Value<int?> sourceMealPlanEntryId,
    });
typedef $$ShoppingListItemsTableUpdateCompanionBuilder =
    ShoppingListItemsCompanion Function({
      Value<int> id,
      Value<String> userId,
      Value<int> ingredientId,
      Value<String> name,
      Value<double?> quantity,
      Value<String?> unit,
      Value<String> source,
      Value<bool> isRequirement,
      Value<bool> isChecked,
      Value<int?> sourceMealPlanEntryId,
    });

final class $$ShoppingListItemsTableReferences
    extends
        BaseReferences<
          _$GleanDatabase,
          $ShoppingListItemsTable,
          ShoppingListItem
        > {
  $$ShoppingListItemsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $IngredientsTable _ingredientIdTable(_$GleanDatabase db) => db
      .ingredients
      .createAlias('shopping_list_items__ingredient_id__ingredients__id');

  $$IngredientsTableProcessedTableManager get ingredientId {
    final $_column = $_itemColumn<int>('ingredient_id')!;

    final manager = $$IngredientsTableTableManager(
      $_db,
      $_db.ingredients,
    ).filter((f) => f.id.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_ingredientIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $MealPlanEntriesTable _sourceMealPlanEntryIdTable(
    _$GleanDatabase db,
  ) => db.mealPlanEntries.createAlias(
    'shopping_list_items__source_meal_plan_entry_id__meal_plan_entries__id',
  );

  $$MealPlanEntriesTableProcessedTableManager? get sourceMealPlanEntryId {
    final $_column = $_itemColumn<int>('source_meal_plan_entry_id');
    if ($_column == null) return null;
    final manager = $$MealPlanEntriesTableTableManager(
      $_db,
      $_db.mealPlanEntries,
    ).filter((f) => f.id.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(
      _sourceMealPlanEntryIdTable($_db),
    );
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$ShoppingListItemsTableFilterComposer
    extends Composer<_$GleanDatabase, $ShoppingListItemsTable> {
  $$ShoppingListItemsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get userId => $composableBuilder(
    column: $table.userId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get quantity => $composableBuilder(
    column: $table.quantity,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get unit => $composableBuilder(
    column: $table.unit,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get source => $composableBuilder(
    column: $table.source,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get isRequirement => $composableBuilder(
    column: $table.isRequirement,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get isChecked => $composableBuilder(
    column: $table.isChecked,
    builder: (column) => ColumnFilters(column),
  );

  $$IngredientsTableFilterComposer get ingredientId {
    final $$IngredientsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableFilterComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$MealPlanEntriesTableFilterComposer get sourceMealPlanEntryId {
    final $$MealPlanEntriesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sourceMealPlanEntryId,
      referencedTable: $db.mealPlanEntries,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$MealPlanEntriesTableFilterComposer(
            $db: $db,
            $table: $db.mealPlanEntries,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$ShoppingListItemsTableOrderingComposer
    extends Composer<_$GleanDatabase, $ShoppingListItemsTable> {
  $$ShoppingListItemsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get userId => $composableBuilder(
    column: $table.userId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get quantity => $composableBuilder(
    column: $table.quantity,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get unit => $composableBuilder(
    column: $table.unit,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get source => $composableBuilder(
    column: $table.source,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get isRequirement => $composableBuilder(
    column: $table.isRequirement,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get isChecked => $composableBuilder(
    column: $table.isChecked,
    builder: (column) => ColumnOrderings(column),
  );

  $$IngredientsTableOrderingComposer get ingredientId {
    final $$IngredientsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableOrderingComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$MealPlanEntriesTableOrderingComposer get sourceMealPlanEntryId {
    final $$MealPlanEntriesTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sourceMealPlanEntryId,
      referencedTable: $db.mealPlanEntries,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$MealPlanEntriesTableOrderingComposer(
            $db: $db,
            $table: $db.mealPlanEntries,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$ShoppingListItemsTableAnnotationComposer
    extends Composer<_$GleanDatabase, $ShoppingListItemsTable> {
  $$ShoppingListItemsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get userId =>
      $composableBuilder(column: $table.userId, builder: (column) => column);

  GeneratedColumn<String> get name =>
      $composableBuilder(column: $table.name, builder: (column) => column);

  GeneratedColumn<double> get quantity =>
      $composableBuilder(column: $table.quantity, builder: (column) => column);

  GeneratedColumn<String> get unit =>
      $composableBuilder(column: $table.unit, builder: (column) => column);

  GeneratedColumn<String> get source =>
      $composableBuilder(column: $table.source, builder: (column) => column);

  GeneratedColumn<bool> get isRequirement => $composableBuilder(
    column: $table.isRequirement,
    builder: (column) => column,
  );

  GeneratedColumn<bool> get isChecked =>
      $composableBuilder(column: $table.isChecked, builder: (column) => column);

  $$IngredientsTableAnnotationComposer get ingredientId {
    final $$IngredientsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.ingredientId,
      referencedTable: $db.ingredients,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$IngredientsTableAnnotationComposer(
            $db: $db,
            $table: $db.ingredients,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$MealPlanEntriesTableAnnotationComposer get sourceMealPlanEntryId {
    final $$MealPlanEntriesTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sourceMealPlanEntryId,
      referencedTable: $db.mealPlanEntries,
      getReferencedColumn: (t) => t.id,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$MealPlanEntriesTableAnnotationComposer(
            $db: $db,
            $table: $db.mealPlanEntries,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$ShoppingListItemsTableTableManager
    extends
        RootTableManager<
          _$GleanDatabase,
          $ShoppingListItemsTable,
          ShoppingListItem,
          $$ShoppingListItemsTableFilterComposer,
          $$ShoppingListItemsTableOrderingComposer,
          $$ShoppingListItemsTableAnnotationComposer,
          $$ShoppingListItemsTableCreateCompanionBuilder,
          $$ShoppingListItemsTableUpdateCompanionBuilder,
          (ShoppingListItem, $$ShoppingListItemsTableReferences),
          ShoppingListItem,
          PrefetchHooks Function({
            bool ingredientId,
            bool sourceMealPlanEntryId,
          })
        > {
  $$ShoppingListItemsTableTableManager(
    _$GleanDatabase db,
    $ShoppingListItemsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$ShoppingListItemsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$ShoppingListItemsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$ShoppingListItemsTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> userId = const Value.absent(),
                Value<int> ingredientId = const Value.absent(),
                Value<String> name = const Value.absent(),
                Value<double?> quantity = const Value.absent(),
                Value<String?> unit = const Value.absent(),
                Value<String> source = const Value.absent(),
                Value<bool> isRequirement = const Value.absent(),
                Value<bool> isChecked = const Value.absent(),
                Value<int?> sourceMealPlanEntryId = const Value.absent(),
              }) => ShoppingListItemsCompanion(
                id: id,
                userId: userId,
                ingredientId: ingredientId,
                name: name,
                quantity: quantity,
                unit: unit,
                source: source,
                isRequirement: isRequirement,
                isChecked: isChecked,
                sourceMealPlanEntryId: sourceMealPlanEntryId,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String userId,
                required int ingredientId,
                required String name,
                Value<double?> quantity = const Value.absent(),
                Value<String?> unit = const Value.absent(),
                Value<String> source = const Value.absent(),
                Value<bool> isRequirement = const Value.absent(),
                Value<bool> isChecked = const Value.absent(),
                Value<int?> sourceMealPlanEntryId = const Value.absent(),
              }) => ShoppingListItemsCompanion.insert(
                id: id,
                userId: userId,
                ingredientId: ingredientId,
                name: name,
                quantity: quantity,
                unit: unit,
                source: source,
                isRequirement: isRequirement,
                isChecked: isChecked,
                sourceMealPlanEntryId: sourceMealPlanEntryId,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$ShoppingListItemsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({ingredientId = false, sourceMealPlanEntryId = false}) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (ingredientId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.ingredientId,
                                    referencedTable:
                                        $$ShoppingListItemsTableReferences
                                            ._ingredientIdTable(db),
                                    referencedColumn:
                                        $$ShoppingListItemsTableReferences
                                            ._ingredientIdTable(db)
                                            .id,
                                  )
                                  as T;
                        }
                        if (sourceMealPlanEntryId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.sourceMealPlanEntryId,
                                    referencedTable:
                                        $$ShoppingListItemsTableReferences
                                            ._sourceMealPlanEntryIdTable(db),
                                    referencedColumn:
                                        $$ShoppingListItemsTableReferences
                                            ._sourceMealPlanEntryIdTable(db)
                                            .id,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [];
                  },
                );
              },
        ),
      );
}

typedef $$ShoppingListItemsTableProcessedTableManager =
    ProcessedTableManager<
      _$GleanDatabase,
      $ShoppingListItemsTable,
      ShoppingListItem,
      $$ShoppingListItemsTableFilterComposer,
      $$ShoppingListItemsTableOrderingComposer,
      $$ShoppingListItemsTableAnnotationComposer,
      $$ShoppingListItemsTableCreateCompanionBuilder,
      $$ShoppingListItemsTableUpdateCompanionBuilder,
      (ShoppingListItem, $$ShoppingListItemsTableReferences),
      ShoppingListItem,
      PrefetchHooks Function({bool ingredientId, bool sourceMealPlanEntryId})
    >;
typedef $$UserConfigTableCreateCompanionBuilder =
    UserConfigCompanion Function({
      required String id,
      Value<double> purchaseTolerance,
      Value<int> preferredServings,
      Value<int> mealsPerWeek,
      Value<String> dietaryFlags,
      Value<int?> maxActiveTimeMins,
      Value<bool> onboardingCompleted,
      Value<int> rowid,
    });
typedef $$UserConfigTableUpdateCompanionBuilder =
    UserConfigCompanion Function({
      Value<String> id,
      Value<double> purchaseTolerance,
      Value<int> preferredServings,
      Value<int> mealsPerWeek,
      Value<String> dietaryFlags,
      Value<int?> maxActiveTimeMins,
      Value<bool> onboardingCompleted,
      Value<int> rowid,
    });

class $$UserConfigTableFilterComposer
    extends Composer<_$GleanDatabase, $UserConfigTable> {
  $$UserConfigTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get purchaseTolerance => $composableBuilder(
    column: $table.purchaseTolerance,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get preferredServings => $composableBuilder(
    column: $table.preferredServings,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get mealsPerWeek => $composableBuilder(
    column: $table.mealsPerWeek,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get dietaryFlags => $composableBuilder(
    column: $table.dietaryFlags,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get maxActiveTimeMins => $composableBuilder(
    column: $table.maxActiveTimeMins,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get onboardingCompleted => $composableBuilder(
    column: $table.onboardingCompleted,
    builder: (column) => ColumnFilters(column),
  );
}

class $$UserConfigTableOrderingComposer
    extends Composer<_$GleanDatabase, $UserConfigTable> {
  $$UserConfigTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get purchaseTolerance => $composableBuilder(
    column: $table.purchaseTolerance,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get preferredServings => $composableBuilder(
    column: $table.preferredServings,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get mealsPerWeek => $composableBuilder(
    column: $table.mealsPerWeek,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get dietaryFlags => $composableBuilder(
    column: $table.dietaryFlags,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get maxActiveTimeMins => $composableBuilder(
    column: $table.maxActiveTimeMins,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get onboardingCompleted => $composableBuilder(
    column: $table.onboardingCompleted,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$UserConfigTableAnnotationComposer
    extends Composer<_$GleanDatabase, $UserConfigTable> {
  $$UserConfigTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<double> get purchaseTolerance => $composableBuilder(
    column: $table.purchaseTolerance,
    builder: (column) => column,
  );

  GeneratedColumn<int> get preferredServings => $composableBuilder(
    column: $table.preferredServings,
    builder: (column) => column,
  );

  GeneratedColumn<int> get mealsPerWeek => $composableBuilder(
    column: $table.mealsPerWeek,
    builder: (column) => column,
  );

  GeneratedColumn<String> get dietaryFlags => $composableBuilder(
    column: $table.dietaryFlags,
    builder: (column) => column,
  );

  GeneratedColumn<int> get maxActiveTimeMins => $composableBuilder(
    column: $table.maxActiveTimeMins,
    builder: (column) => column,
  );

  GeneratedColumn<bool> get onboardingCompleted => $composableBuilder(
    column: $table.onboardingCompleted,
    builder: (column) => column,
  );
}

class $$UserConfigTableTableManager
    extends
        RootTableManager<
          _$GleanDatabase,
          $UserConfigTable,
          UserConfigData,
          $$UserConfigTableFilterComposer,
          $$UserConfigTableOrderingComposer,
          $$UserConfigTableAnnotationComposer,
          $$UserConfigTableCreateCompanionBuilder,
          $$UserConfigTableUpdateCompanionBuilder,
          (
            UserConfigData,
            BaseReferences<_$GleanDatabase, $UserConfigTable, UserConfigData>,
          ),
          UserConfigData,
          PrefetchHooks Function()
        > {
  $$UserConfigTableTableManager(_$GleanDatabase db, $UserConfigTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$UserConfigTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$UserConfigTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$UserConfigTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> id = const Value.absent(),
                Value<double> purchaseTolerance = const Value.absent(),
                Value<int> preferredServings = const Value.absent(),
                Value<int> mealsPerWeek = const Value.absent(),
                Value<String> dietaryFlags = const Value.absent(),
                Value<int?> maxActiveTimeMins = const Value.absent(),
                Value<bool> onboardingCompleted = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => UserConfigCompanion(
                id: id,
                purchaseTolerance: purchaseTolerance,
                preferredServings: preferredServings,
                mealsPerWeek: mealsPerWeek,
                dietaryFlags: dietaryFlags,
                maxActiveTimeMins: maxActiveTimeMins,
                onboardingCompleted: onboardingCompleted,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String id,
                Value<double> purchaseTolerance = const Value.absent(),
                Value<int> preferredServings = const Value.absent(),
                Value<int> mealsPerWeek = const Value.absent(),
                Value<String> dietaryFlags = const Value.absent(),
                Value<int?> maxActiveTimeMins = const Value.absent(),
                Value<bool> onboardingCompleted = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => UserConfigCompanion.insert(
                id: id,
                purchaseTolerance: purchaseTolerance,
                preferredServings: preferredServings,
                mealsPerWeek: mealsPerWeek,
                dietaryFlags: dietaryFlags,
                maxActiveTimeMins: maxActiveTimeMins,
                onboardingCompleted: onboardingCompleted,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$UserConfigTableProcessedTableManager =
    ProcessedTableManager<
      _$GleanDatabase,
      $UserConfigTable,
      UserConfigData,
      $$UserConfigTableFilterComposer,
      $$UserConfigTableOrderingComposer,
      $$UserConfigTableAnnotationComposer,
      $$UserConfigTableCreateCompanionBuilder,
      $$UserConfigTableUpdateCompanionBuilder,
      (
        UserConfigData,
        BaseReferences<_$GleanDatabase, $UserConfigTable, UserConfigData>,
      ),
      UserConfigData,
      PrefetchHooks Function()
    >;

class $GleanDatabaseManager {
  final _$GleanDatabase _db;
  $GleanDatabaseManager(this._db);
  $$IngredientCategoriesTableTableManager get ingredientCategories =>
      $$IngredientCategoriesTableTableManager(_db, _db.ingredientCategories);
  $$IngredientsTableTableManager get ingredients =>
      $$IngredientsTableTableManager(_db, _db.ingredients);
  $$PantryItemsTableTableManager get pantryItems =>
      $$PantryItemsTableTableManager(_db, _db.pantryItems);
  $$RecipesTableTableManager get recipes =>
      $$RecipesTableTableManager(_db, _db.recipes);
  $$RecipeDietaryFlagsTableTableManager get recipeDietaryFlags =>
      $$RecipeDietaryFlagsTableTableManager(_db, _db.recipeDietaryFlags);
  $$RecipeIngredientsTableTableManager get recipeIngredients =>
      $$RecipeIngredientsTableTableManager(_db, _db.recipeIngredients);
  $$MealPlanEntriesTableTableManager get mealPlanEntries =>
      $$MealPlanEntriesTableTableManager(_db, _db.mealPlanEntries);
  $$CookedAdjustmentsTableTableManager get cookedAdjustments =>
      $$CookedAdjustmentsTableTableManager(_db, _db.cookedAdjustments);
  $$ShoppingListItemsTableTableManager get shoppingListItems =>
      $$ShoppingListItemsTableTableManager(_db, _db.shoppingListItems);
  $$UserConfigTableTableManager get userConfig =>
      $$UserConfigTableTableManager(_db, _db.userConfig);
}
