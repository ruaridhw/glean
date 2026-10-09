import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Repo standards from `app/AGENTS.md` §Standards, enforced as a ratchet:
/// each allowlist names files that violated the rule when the rule was
/// introduced. Entries may only ever be removed.
const Set<String> _featureDataImportAllowlist = <String>{};
const Set<String> _rawColourAllowlist = <String>{};

const Set<String> _citationAllowlist = <String>{
  'lib/api/api_client.dart',
  'lib/api/api_exception.dart',
  'lib/api/models/meal_plan.dart',
  'lib/api/models/parsed_ingredient.dart',
  'lib/api/models/recipes.dart',
  'lib/api/providers/api_providers.dart',
  'lib/api/providers/recipe_providers.dart',
  'lib/app.dart',
  'lib/auth/auth_bypass.dart',
  'lib/auth/auth_controller.dart',
  'lib/auth/auth.dart',
  'lib/auth/auth_mode.dart',
  'lib/auth/cognito_auth_client.dart',
  'lib/auth/token_storage.dart',
  'lib/bootstrap.dart',
  'lib/data/database.dart',
  'lib/data/models/meal_plan_entry_view.dart',
  'lib/data/models/pantry_item_view.dart',
  'lib/data/models/recipe_view.dart',
  'lib/data/models/shopping_list_item_view.dart',
  'lib/data/providers/database_providers.dart',
  'lib/data/providers/pantry_providers.dart',
  'lib/data/providers/plan_providers.dart',
  'lib/data/providers/repository_providers.dart',
  'lib/data/repositories/ingredients_repository.dart',
  'lib/data/repositories/pantry_repository.dart',
  'lib/data/repositories/plan_repository.dart',
  'lib/data/repositories/recipes_repository.dart',
  'lib/data/repositories/shopping_repository.dart',
  'lib/data/seed/taxonomy.dart',
  'lib/data/tables.dart',
  'lib/data/util/unit_normalization.dart',
  'lib/data/util/week.dart',
  'lib/design_system/badge.dart',
  'lib/design_system/brand_mark.dart',
  'lib/design_system/design_system.dart',
  'lib/design_system/haptics.dart',
  'lib/design_system/skeleton.dart',
  'lib/design_system/snackbar.dart',
  'lib/design_system/swipe_to_delete.dart',
  'lib/design_system/theme.dart',
  'lib/design_system/tokens.dart',
  'lib/features/auth/sign_in_screen.dart',
  'lib/features/auth/widgets/signed_out_banner.dart',
  'lib/features/intake/camera/receipt_camera_controller.dart',
  'lib/features/intake/manual_entry_screen.dart',
  'lib/features/intake/review_row.dart',
  'lib/features/intake/review_screen.dart',
  'lib/features/intake/scan_screen.dart',
  'lib/features/intake/widgets/camera_permission_prompt.dart',
  'lib/features/intake/widgets/describe_form.dart',
  'lib/features/intake/widgets/review_item_row.dart',
  'lib/features/intake/widgets/scan_back_button.dart',
  'lib/features/intake/widgets/scan_progress_body.dart',
  'lib/features/meals/meal_detail_screen.dart',
  'lib/features/meals/presentation.dart',
  'lib/features/meals/providers/meal_providers.dart',
  'lib/features/meals/recipe_preview_screen.dart',
  'lib/features/meals/saved_recipe_detail.dart',
  'lib/features/meals/widgets/meals_search_panel.dart',
  'lib/features/meals/widgets/meals_states.dart',
  'lib/features/meals/widgets/recipe_card.dart',
  'lib/features/meals/widgets/recipe_detail_sections.dart',
  'lib/features/meals/widgets/recipe_detail_view.dart',
  'lib/features/meals/widgets/search_result_card.dart',
  'lib/features/onboarding/onboarding_gate.dart',
  'lib/features/onboarding/onboarding_screen.dart',
  'lib/features/onboarding/widgets/onboarding_footer.dart',
  'lib/features/onboarding/widgets/onboarding_step_body.dart',
  'lib/features/pantry/pantry_presentation.dart',
  'lib/features/pantry/pantry_screen.dart',
  'lib/features/pantry/widgets/pantry_add_sheet.dart',
  'lib/features/pantry/widgets/pantry_body.dart',
  'lib/features/pantry/widgets/pantry_empty_state.dart',
  'lib/features/pantry/widgets/pantry_expiry_banner.dart',
  'lib/features/pantry/widgets/pantry_filter_chips.dart',
  'lib/features/pantry/widgets/pantry_item_row.dart',
  'lib/features/pantry/widgets/quantity_edit_sheet.dart',
  'lib/features/plan/food_groups.dart',
  'lib/features/plan/plan_screen.dart',
  'lib/features/plan/presentation.dart',
  'lib/features/plan/providers/generate_week_controller.dart',
  'lib/features/plan/widgets/generate_button.dart',
  'lib/features/plan/widgets/plan_progress_card.dart',
  'lib/features/plan/widgets/plan_slot_row.dart',
  'lib/features/plan/widgets/plan_week_pager.dart',
  'lib/features/settings/providers/sign_out_action.dart',
  'lib/features/settings/settings_presentation.dart',
  'lib/features/settings/settings_screen.dart',
  'lib/features/settings/widgets/account_section.dart',
  'lib/features/settings/widgets/dietary_flags_control.dart',
  'lib/features/settings/widgets/integer_slider_control.dart',
  'lib/features/settings/widgets/legal_links_section.dart',
  'lib/features/settings/widgets/max_time_field.dart',
  'lib/features/settings/widgets/section_label.dart',
  'lib/features/settings/widgets/tolerance_card.dart',
  'lib/features/shop/presentation.dart',
  'lib/features/shop/shop_screen.dart',
  'lib/features/shop/widgets/shop_add_field.dart',
  'lib/features/shop/widgets/shop_checkout_bar.dart',
  'lib/features/shop/widgets/shop_list_section.dart',
  'lib/features/shop/widgets/shopping_row.dart',
  'lib/main.dart',
  'lib/main_e2e.dart',
  'lib/router/app_shell.dart',
  'lib/router/auth_state.dart',
  'lib/router/route_error_screen.dart',
  'lib/router/router.dart',
};

final RegExp _forbiddenFeatureImport = RegExp(
  r'''^\s*import\s+['"](package:drift/|package:glean/data/(database|tables|deletion_snapshots)\.dart|\.\./.*data/(database|tables|deletion_snapshots)\.dart)''',
  multiLine: true,
);

final RegExp _rawColour = RegExp(
  r'\bColors\.(?!transparent\b)\w+|\bColor\(0x[0-9A-Fa-f]{8}\)',
);

final RegExp _citation = RegExp(
  r'AC-[A-Z]+-\d+|\bR-\d\d\b|\bF-\d\d\b|FINDINGS\.md|REMEDIATION\.md|\.scratch/|\bWave \d|orchestrator',
);

final RegExp _bypassImport = RegExp(
  r'''^\s*(import|export)\s+['"][^'"]*auth_bypass\.dart['"]''',
  multiLine: true,
);

Iterable<File> _dartFiles(String root) => Directory(root)
    .listSync(recursive: true)
    .whereType<File>()
    .where((f) => f.path.endsWith('.dart') && !f.path.endsWith('.g.dart'));

String _rel(File f) => f.path.replaceAll('\\', '/');

void _expectRatchet({
  required Iterable<File> files,
  required bool Function(String source) violates,
  required Set<String> allowlist,
  required String rule,
}) {
  final violations = <String>[];
  final stillNeeded = <String>{};
  for (final file in files) {
    final path = _rel(file);
    if (!violates(file.readAsStringSync())) continue;
    if (allowlist.contains(path)) {
      stillNeeded.add(path);
    } else {
      violations.add(path);
    }
  }
  expect(violations, isEmpty, reason: '$rule — see app/AGENTS.md §Standards');
  expect(
    allowlist.difference(stillNeeded),
    isEmpty,
    reason: 'Allowlist entries that no longer violate must be removed: ',
  );
}

void main() {
  test('features reach data only through providers (rule 1)', () {
    _expectRatchet(
      files: _dartFiles('lib/features'),
      violates: _forbiddenFeatureImport.hasMatch,
      allowlist: _featureDataImportAllowlist,
      rule:
          'lib/features/** must not import drift, database.dart, '
          'tables.dart or deletion_snapshots.dart',
    );
  });

  test('colours come from the theme outside design_system (rule 2)', () {
    _expectRatchet(
      files: _dartFiles(
        'lib',
      ).where((f) => !_rel(f).startsWith('lib/design_system/')),
      violates: _rawColour.hasMatch,
      allowlist: _rawColourAllowlist,
      rule:
          'no Colors.* (except transparent) or Color(0x…) outside '
          'lib/design_system/',
    );
  });

  test('no process citations in comments (rule 3)', () {
    _expectRatchet(
      files: _dartFiles('lib'),
      violates: _citation.hasMatch,
      allowlist: _citationAllowlist,
      rule:
          'no AC-/R-/F-/FINDINGS/REMEDIATION/.scratch/Wave/orchestrator '
          'references in lib/',
    );
  });

  test('only main_e2e.dart imports auth_bypass.dart', () {
    const allowed = <String>{'lib/auth/auth_bypass.dart', 'lib/main_e2e.dart'};
    final violations = <String>[
      for (final f in _dartFiles('lib'))
        if (!allowed.contains(_rel(f)) &&
            _bypassImport.hasMatch(f.readAsStringSync()))
          _rel(f),
    ];
    expect(
      violations,
      isEmpty,
      reason: 'These files would pull the test bypass into a release build',
    );
  });
}
