import 'dart:convert';

import '../database.dart';

/// How long an ingredient with no catalogue item keeps, from its group alone, in days; null when it is not inferred.
///
/// A group with forms takes the fresh life while the ingredient's form is unset, because form is never defaulted on the
/// ingredient itself: beans and pulses are the exception, which have always been counted as dry stock. Other, the group
/// of an ingredient nobody could classify, gets no inferred life, as an unclassified ingredient never did. A group
/// that never expires (household items) has none either.
int? unlinkedShelfLifeDays(IngredientGroup? group, String? form) {
  if (group == null || group.id == 'other') return null;
  final unopened =
      jsonDecode(group.unopenedShelfLifeDays) as Map<String, dynamic>;
  if (form != null) return unopened[form] as int?;
  if (group.id == 'beans_and_pulses') return 180;
  final forms = jsonDecode(group.allowedForms) as List<dynamic>;
  return unopened[forms.contains('fresh') ? 'fresh' : 'not_applicable'] as int?;
}
