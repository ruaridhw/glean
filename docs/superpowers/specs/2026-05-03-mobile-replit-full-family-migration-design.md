# Mobile Replit Full Family Migration Design

## Summary

This project continues the Replit-to-production mobile reconciliation after the Pantry proof screen in PR #40. The work should happen on a fresh branch from the PR #40 baseline, using the Pantry UI foundation as the starting point.

The branch will migrate the remaining main screen families toward the Replit visual and UX direction: Meals, Plan, Shop, and Settings. This includes their visible nested routes, modals, forms, and handoffs where needed for a coherent migrated experience.

The Replit prototype remains the visual and UX target. The real `mobile/` app remains canonical for auth, SQLite/Drizzle ownership, backend integration, production API semantics, and existing critical behavior. Replit's `AppContext`, seed data, AsyncStorage state model, and mock-only shortcuts must not be copied into production.

DB migrations are allowed selectively. A migration must directly support a visible migrated screen or flow, avoid overloading unrelated fields, stay small, and include Drizzle/schema tests plus at least one helper or screen test.

## Goals

- Start a fresh feature branch from the Pantry/PR #40 baseline.
- Migrate the full remaining screen families:
  - Meals index, detail, search, import, and add-to-plan handoff.
  - Plan index, recipe add/picker behavior, progress, cooked state, delete, generate plan, and shopping-list handoff.
  - Shop index, grouped list, add-item UI, checked/unchecked state, checkout, move/clear checked behavior, and receipt-scan handoff.
  - Settings index, preferences, stats, dietary choices, sign-out, export DB, and existing account/dev actions.
- Extend the shared UI foundation only where multiple families need the primitive.
- Keep screen files focused on orchestration while moving formatting, grouping, labels, and presentation models into testable helper modules.
- Preserve real production data paths and critical behavior.
- Use selective DB migrations only when directly required by migrated visible behavior.
- Verify with lower-level tests, focused screen tests, CI, and Android launch/navigation checks.

## Non-goals

- Do not copy Replit seed data or prototype state management into `mobile/`.
- Do not replace Cognito auth, backend API semantics, or production DB ownership.
- Do not add backend/API changes in this branch unless a later explicit decision changes the scope.
- Do not build a large component library ahead of actual screen needs.
- Do not chase detailed e2e/Maestro coverage for every migrated screen; keep e2e at highest-level smoke unless smoke is blocked.
- Do not persist nice-to-have prototype fields unless they directly unblock a migrated screen.

## Branch strategy

Create the implementation branch from the Pantry/PR #40 baseline: `feature/mobile-replit-reconciliation` at or after commit `ade9269`.

The expected new branch name is:

`feature/mobile-replit-full-family-migration`

The dirty `e2e-tests` root worktree should not be used for implementation changes. Use the existing clean PR #40 worktree or a new isolated worktree based on the PR #40 branch.

## Scope

### Meals family

Files in scope:

- `mobile/app/(tabs)/meals/index.tsx`
- `mobile/app/(tabs)/meals/[id].tsx`
- `mobile/app/(tabs)/meals/search.tsx`
- `mobile/app/(tabs)/meals/import.tsx`

The migrated Meals family should adapt Replit's recipe cards, saved/suggested style, rich metadata, tags, and detail presentation onto real production recipe data. Search and import should receive enough visual treatment that they do not feel like old screens when reached from the migrated tab.

### Plan family

Files in scope:

- `mobile/app/(tabs)/plan/index.tsx`
- any existing route-param handoffs from Meals to Plan
- any recipe add/picker behavior that is needed inside the current route structure

The migrated Plan family should adapt Replit's weekly planning feel, progress indicator, empty slots, cooked state, delete behavior, generate-plan action, and shopping-list handoff while preserving production meal-plan, suggestion, pantry compression, and shopping-gap behavior.

### Shop family

Files in scope:

- `mobile/app/(tabs)/shop/index.tsx`
- add-item form/modal UI if it remains local to the screen
- checkout and receipt-scan handoff behavior

The migrated Shop family should adapt Replit's grouped shopping list, checked/unchecked presentation, category treatment, add-item interaction, and checked-item actions. Existing shopping mutations remain canonical.

### Settings family

Files in scope:

- `mobile/app/(tabs)/settings/index.tsx`

The migrated Settings family should adapt Replit's stats card, preference chips, settings rows, dietary preferences, and data/account actions while preserving existing config persistence, sign-out, and export DB behavior.

## Architecture

Keep the current Expo Router families and real data modules. Add a broader but still small UI layer on top of the Pantry primitives from PR #40.

Shared UI additions should be demand-driven:

- `SegmentedControl` for Meals tabs, Settings option groups, and any future multi-option filters.
- `SectionHeader` for consistent section title/subtitle/action rows.
- `StatCard` or `StatsRow` for Plan progress and Settings stats.
- `ListCard` or variants around the existing `Card` for recipe cards, plan slots, shopping rows, and settings rows.
- `Sheet` or modal wrapper if route/modal behavior needs a consistent page-sheet/full-screen fallback.
- `ChipGroup` for dietary preferences, recipe tags, unit chips, and category chips where reused.

Add presentation helper modules per family where useful:

- `mobile/src/meals/presentation.ts`
- `mobile/src/plan/presentation.ts`
- `mobile/src/shop/presentation.ts`
- `mobile/src/settings/presentation.ts`

Screen files should orchestrate loading, mutations, navigation, and local UI state. Formatting, grouping, labels, progress calculations, category metadata, and badge/chip view models should live in helper modules so they can be unit tested.

Haptics should continue to go through the safe wrapper introduced in PR #40. Direct `expo-haptics` calls should not be reintroduced in migrated screens.

## Data flow and selective migrations

### Meals

Existing recipe DB/API functions remain the source of truth. Recipe cards and detail screens should map real fields such as title, cuisine, difficulty, timing, servings, nutrition, instructions, and ingredients where available.

Replit concepts such as recipe category, tags, saved/suggested state, and bookmark semantics should only be persisted if the migrated screen needs them and current production fields cannot represent them.

### Plan

Existing meal plan entries, user config, saved recipes, suggestion API, pantry compression, and shopping-gap generation remain canonical.

Replit's week navigation and slot-index model can be adapted only if production schema supports it or a targeted migration is clearly justified by the migrated UI. Critical production behavior must stay intact: add recipes, mark cooked, delete, generate plan, and add shopping gaps.

### Shop

Existing shopping list queries and mutations remain canonical. Replit grouped categories and richer add-item form can be adapted where current fields support them.

If richer category persistence is needed for grouped UI correctness, add a small Drizzle migration and tests. Existing checkout behavior remains: checked items can be cleared, receipt scanning stays available, and pantry handoff behavior is preserved or explicitly mapped.

### Settings

Existing user config remains canonical. Replit-style chips/cards can replace raw inputs where fields already exist.

New persisted settings such as waste alerts or dark mode are deferred unless they are directly implemented, migrated, and tested in this branch. Existing sign-out and export DB actions remain available and are restyled into the Replit visual system.

### Migration rule

A DB migration is allowed only if all of these are true:

1. The migrated UI needs the value to behave correctly.
2. Existing schema cannot represent it without overloading unrelated fields.
3. The migration is small and conceptually reversible.
4. It has Drizzle/schema tests and at least one screen or helper test.

## Migration sequence

1. Shared foundation extension
   - Add only primitives needed by at least two families.
   - Add tests for each primitive before broad use.
   - Keep Pantry-compatible behavior intact.

2. Meals family
   - Validate recipe cards, tabs, tags/meta, detail presentation, search/import visual polish, and add-to-plan handoff.
   - Keep real recipe data canonical.

3. Plan family
   - Reuse migrated recipe presentation where helpful.
   - Restyle weekly planning, progress, empty slots, cooked state, generate plan, and shopping-list behavior.
   - Justify any week/slot schema change before adding it.

4. Shop family
   - Restyle grouped unchecked/checked rows, add item, checkout, and scan-receipt handoff.
   - Use real shopping DB mutations.
   - Add category helper and targeted migration only if current fields are insufficient.

5. Settings family
   - Restyle preferences, stats, dietary chips, account/dev actions.
   - Save through existing config functions.
   - Avoid displaying toggles that do not have real persisted behavior.

6. Final cross-family polish
   - Align spacing, cards, section headers, empty/loading/error states.
   - Check handoffs: Meals to Plan, Plan to Shop, Shop to Pantry scan, Settings save/sign-out/export.
   - Update audit/spec notes if selective migrations were used.

## Error handling and states

- Reuse existing skeleton components where they exist, restyled only if necessary.
- Empty states should keep real production actions:
  - Meals: search/import recipes.
  - Plan: browse recipes or generate plan.
  - Shop: go to plan, add manual item, or use an existing shopping action where supported.
  - Settings: show a lightweight loading state instead of returning `null`.
- DB/API failures should use existing toast/error patterns unless a native confirmation or alert is specifically appropriate.
- Destructive actions should use platform-native confirmation where appropriate:
  - delete recipe or plan row
  - delete shopping item
  - clear checked items
  - sign out
  - export DB failure/success
- Haptics are best-effort and must never be required for correctness.

## Testing and verification

Implementation should include:

- Pure helper tests for each new family presentation module.
- Component tests for new shared UI primitives.
- Focused screen tests for each family's key loaded, empty, and action states.
- Drizzle/schema tests for any DB migration.
- Highest-level smoke/e2e coverage only unless smoke is blocked.
- `make test-mobile` and `make lint-mobile` before PR.
- CI verification on the PR.
- Android verification that launches the migrated app and checks top-level navigation across Meals, Plan, Shop, and Settings. If emulator/manual input is flaky, document which manual checks were completed and which behaviors are covered by tests.

## Open implementation planning notes

The implementation plan should decide exact file names and task boundaries, but it should preserve this order:

1. Branch/worktree setup from PR #40 baseline.
2. Baseline verification.
3. Shared foundation tests and implementation.
4. Meals family tests and implementation.
5. Plan family tests and implementation.
6. Shop family tests and implementation.
7. Settings family tests and implementation.
8. Migration tests if any schema changes are introduced.
9. Full verification and PR creation.

The plan should prefer small commits per family and should not mix unrelated schema, backend, or e2e changes into a visual-family task.
