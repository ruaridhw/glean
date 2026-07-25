# Cross-wave findings

Issues surfaced by porting agents that don't belong to one wave. Recorded here so they
survive context compaction and get resolved before the final review, rather than being
lost in an agent report.

Status: `OPEN` needs action · `RESOLVED` done · `ACCEPTED` deliberate, no action

---

## F-01 — Brand SVGs contain `<filter>` elements `flutter_svg` cannot render
**Status:** OPEN · surfaced by: design-system agent · affects: AC-DS-07

All three vendored brand SVGs (`app/assets/brand/glean-b1-{icon,splash-logo,adaptive-foreground}.svg`)
contain `<filter>` elements that `flutter_svg` 2.3.0 does not support. It logs
`unhandled element <filter/>`, skips the filter and renders the rest. Almost certainly
drops an authored drop-shadow.

Not a crash, but it is a **silent visual regression against the RN app** and it spams the
console. Options: bake the shadow into the path/gradient at export time, or drop the filter
from the SVG and reapply it in Flutter (`BoxShadow`/`DropShadow`) where the mark is used.
Decide during the polish/verification wave — do not leave the warning in place.

## F-02 — Spec names a brand asset that does not exist
**Status:** RESOLVED (spec inaccuracy, not a code problem) · affects: AC-DS-07

`FLUTTER_MIGRATION.md` §2 cites `assets/source/glean-mark.svg`. No such file exists; the real
assets are the three `glean-b1-*.svg` files. Code uses the real ones and documents it.
The spec line is wrong, not the implementation.

## F-03 — `Override` is not importable from `flutter_riverpod` 3.3.2
**Status:** ACCEPTED (worked around) · surfaced by: design-system agent

`ProviderScope.overrides` documents its element type as `Override`, but that name does not
resolve as an import from `flutter_riverpod` 3.3.2, so a `List<Override>` cannot be written
explicitly. Worked around by letting the list literal infer. Harmless, but if a later wave
needs the explicit type, import it from `package:riverpod` directly rather than re-deriving
the workaround.

## F-04 — Flutter has no `text-transform: uppercase`
**Status:** ACCEPTED · surfaced by: design-system agent

The RN `sectionLabel` style relied on CSS-style uppercasing. Flutter's `TextStyle` has no
equivalent, so any screen wanting that look must call `.toUpperCase()` on the string.
Documented in `theme.dart`. Feature agents must not reintroduce a wrapper widget for this.

## F-05 — `add_recipe_id` has no routing equivalent, by design
**Status:** ACCEPTED · surfaced by: router agent · affects: AC-MEAL-08, AC-PLAN-11

The RN app passed `add_recipe_id` as a nav param and re-added the recipe inside
`useFocusEffect`, which is the **duplicate-plan-entry bug** (§11): leaving the Plan tab and
returning re-added the recipe every time. §6 instead requires staying on the recipe after
"Add to plan" with the button reflecting "In plan", so add-to-plan is a same-screen mutation
with **no navigation and no param**. The Plan wave must not reintroduce the param.

## F-06 — `sqlite3_flutter_libs` is end-of-life upstream
**Status:** RESOLVED · affects: AC-BUILD-02

Its own pub description reads *"Not used anymore, update to version 3.x of package:sqlite3"*.
Native sqlite comes via `drift_flutter` instead. A forced deviation from the spec's literal
package list in §2; `drift_flutter` is the drift team's current Flutter integration package.

## F-07 — `category` stays nullable while `food_group` does not
**Status:** RESOLVED · affects: AC-BE-01, AC-DATA-11

The backend's first cut let an out-of-taxonomy LLM value coerce `category` to null, which made
`food_group` null too and left the meal-plan 422 reachable — the exact failure §9 exists to
remove. Now `food_group` is non-nullable and falls back to `"other"` (already a client-side
bucket, so zero client work), while `category` stays nullable to stay honest about an unknown
fine-grained category. Consequence the Pantry wave must handle: **expiry inference cannot fire
for a null category**, so it must degrade gracefully rather than assume a category is present.

## F-08 — The parse-endpoint contract is deliberately asymmetric
**Status:** RESOLVED · affects: AC-BE-04, AC-DATA-11, AC-PAN-01

**Every wave touching parsed ingredients must model it this way:**

| Field | Nullability | On absence |
|---|---|---|
| `food_group` | **non-nullable `String`** | contract violation — throw |
| `category` | **nullable `String?`** | fine, degrade |

The asymmetry is the point. `food_group` is what `POST /meal-plan` validates non-nullably, so it
is the field whose absence caused the 422; it always resolves, worst case to `"other"`.
`category` is finer-grained (pantry grouping detail, per-category shelf life) and its absence
degrades acceptably.

The API agent initially had this exactly inverted — `category` required and throwing, `food_group`
absent from the model altogether — which would have failed an entire 20-item receipt parse on one
unclassifiable item, i.e. worse than the bug §9 set out to fix. Corrected. Watch for this
inversion recurring in the data layer and the Pantry/Shop review flows.
