Type: grilling
Status: resolved

## Question

Review the current component/design-system layout (`mobile/src/components/`, `mobile/src/components/ui/`, `mobile/src/theme/`) and decide the Flutter equivalent architecture: how shared widgets are organized (e.g. a `widgets/` or `design_system/` package boundary), the theming approach (`ThemeData`/`ThemeExtension` mapping the current color tokens, Plus Jakarta Sans typography, GleanMark brand asset pipeline), and the icon strategy (current app uses `@expo/vector-icons`/Ionicons — find the Flutter equivalent). Also decide where the line sits between "reusable design-system widget" and "one-off screen-specific widget" — the user explicitly wants to know if there are reusable components missing (or over-abstracted ones) in the current app, and that judgment should carry into the Flutter component boundaries.

## Answer

### Platform look
**Material widgets everywhere on both platforms**, heavily themed — matching the current app, which renders one identical custom-branded design language (warm oat, brand green, pill shapes, Plus Jakarta Sans) rather than platform-adaptive UI. Not Cupertino-on-iOS: that would mean two widget vocabularies and would fight the brand for no user benefit. Side effect: this substantially shrinks [ticket 04](04-research-flutter-web-test-target.md)'s web-fidelity concern, since much of what diverges on web *is* the platform-adaptive layer we're not using.

### Theming
Map tokens onto **`ColorScheme` + `TextTheme`** so built-in Material widgets inherit the brand automatically, with a **`ThemeExtension`** for the leftovers that don't fit those slots (tone pairs like `warningLight`/`warning`, `ink`, `primaryLight`, radius/spacing/shadow scales). Then theme each built-in centrally (`CardTheme`, `IconButtonTheme`, `SegmentedButtonTheme`, `SnackBarThemeData`) instead of wrapping it in a bespoke widget — this is the core Flutter-esque inversion vs. the RN app, which must wrap because RN ships no themed primitives.

**Token access must go through `Theme.of(context)`**, never a global const. The RN app imports a global (`import { theme } from "@/theme"`) at every call site; replicating that in Flutter would make adding dark mode a codebase-wide refactor instead of a second `ThemeData`.

### Dark mode
**Out of scope** for the port — parity first, and it's real design work (every tone pair and tinted chip needs a dark counterpart). The context-based access pattern above keeps the door open cheaply.

### Icons
Default to Flutter's **built-in `Icons`, `_rounded` variants** — zero dependency, guaranteed maintained, stylistically compatible with the current rounded set now that Material-everywhere is settled. Accepts minor glyph drift from today's Ionicons. Where a specific glyph has no acceptable Material equivalent, **vendor that individual SVG** from Ionicons' source (MIT) through `flutter_svg`. The `ionicons` pub package was rejected: last published ~3 years ago, 70/160 pub points.

`GleanMark` ports via **`flutter_svg`** from the canonical `assets/source/glean-mark.svg` established in PR 90.

### Abstractions to DELETE, not port
These exist only to work around RN limitations that Flutter doesn't have:

- **`AppText` + `scripts/guard-text-imports.mjs`** — its own docstring states the reason: *"React Native picks the weight from the family NAME, not `fontWeight`, so a style with only fontWeight silently renders the system font."* Declare Plus Jakarta Sans's weight variants once in `pubspec.yaml` and `fontWeight` resolves natively. The primitive **and** its custom lint-guard script both go; the type scale becomes `TextTheme` entries.
- **`swipe-delete-row.tsx` (~100 lines of `PanResponder` + `Animated`) and `swipe-action.ts`** → built-in **`Dismissible`** (own `dismissThresholds` + fling handling). ⚠️ Input for [ticket 16](16-test-migration-strategy.md): `shouldRunSwipeAction`'s unit tests should be **dropped, not ported** — they test a hand-rolled gesture threshold that ceases to exist.
- **`Toast.tsx` + the `react-native-toast-message` dependency** → built-in `ScaffoldMessenger`/`SnackBar`, themed via `SnackBarThemeData`.
- **`expo-haptics`** → `HapticFeedback` from `flutter/services.dart`. Built in, no package.
- **`SkeletonBox`'s manual `Animated.loop`** → `TweenAnimationBuilder`/`AnimatedOpacity`.
- **`LayoutAnimation`** (used in `_layout.tsx` and `pantry/index.tsx` for list reflow) → implicit animations / `AnimatedList`. Feeds [ticket 10](10-quick-wins-haptics-transitions.md).

### Missing reusable component (a real gap in the current app)
**There is no `Button` primitive** — `ui/` has `IconButton` only. 12 of 15 route files hand-roll pill-shaped `Pressable` buttons with duplicated styling (`radius.pill` appears in 12 route files: `ScanButton` in pantry, the sign-in button, `EmptyState` actions, filter chips, etc.). The Flutter design system **must** include themed button widgets (`FilledButton`/`OutlinedButton`/`TextButton` via `*ButtonTheme`, plus a pill-chip variant) so this duplication doesn't carry over.

`Badge` is the one primitive likely to stay bespoke: yours is a tinted label pill (tone pairs), closer to Material's `Chip` than its `Badge` (a notification-dot overlay), and `Chip`'s anatomy — delete icon, avatar, tap affordance — may fight the design.

Kept as genuine app-level components: `AppScreen` (but shrinks — `Scaffold` handles keyboard avoidance natively via `resizeToAvoidBottomInset`, so that prop vanishes), `EmptyState`, `ErrorState`, `OfflineBanner`, `SectionHeader`, `StatsRow`, `PulsingDots`, the skeletons, `GleanMark`.

### Folder layout
**Feature-first**: `lib/features/<feature>/` holding the screen, its own `widgets/`, and its providers; shared design system in `lib/design_system/`; the `go_router` route table in `lib/router/`. Drop the vestigial `src/screens/` concept (it holds only `SplashScreen.tsx` today).

Note *why* this changes: expo-router's file-based routing **forced** screens into route files (`app/(tabs)/pantry/index.tsx` is ~400 lines holding four private sub-widgets plus all styles). `go_router`'s declarative route table removes that coupling by necessity.

**Extract private sub-widgets into their own files/classes** (`PantryItemCard`, `FilterChipRow`, `PantrySectionView`, `ScanButton`…) rather than recreating 400-line screens. In Flutter this is not merely tidiness as it is in React: separate widget classes with `const` constructors get independent rebuild scopes, making it a genuine performance property.

### Surfaced beyond this ticket
Two parallel state patterns found while reviewing (11 route files call `@/db/*` imperatively with a manual `useFocusEffect`→`load()`→refetch-after-mutation dance, while 5 use TanStack Query for server state) — raised as [ticket 20](20-decide-data-layer-architecture.md).
