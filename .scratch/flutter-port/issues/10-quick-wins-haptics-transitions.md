Type: prototype
Status: resolved

## Question

Establish the house-wide patterns for haptic feedback and screen/element transitions in the Flutter app — this is a "how should it feel" question, so build a couple of cheap, concrete candidate patterns (e.g. a tab-switch transition, a primary-button-tap haptic, a modal-present animation) and react to them with the user rather than deciding in the abstract. Survey the current app first for where haptic feedback exists today (`expo-haptics` usage) and where transitions feel abrupt or missing, to ground the candidates in real gaps rather than inventing them. If any per-flow UX review tickets (11–15) are already closed, pull concrete examples from their findings.

## Answer

Resolved as a decision rather than a built prototype: this effort is planning-only and there is no Flutter project yet to prototype against, so the ticket's `prototype` type was mis-assigned at charting time. Grounded instead in a full survey of where haptics and transitions exist across all five flows (tickets 11–15).

### Correction to [ticket 08](08-decide-component-architecture.md)
Ticket 08 recorded `expo-haptics` → built-in `HapticFeedback`, no package needed. True for impacts and selection, but Flutter's built-in API offers **only** `lightImpact`, `mediumImpact`, `heavyImpact`, `selectionClick`, and `vibrate` — there is **no notification-style haptic** (success/warning/error), so `expo-haptics`' `notificationAsync` has no built-in equivalent.

**Zero-regression**: `hapticNotify` exists at `platform/haptics.ts:24` and is **never called anywhere in the app**. Notification haptics are therefore dropped, no package is taken, and ticket 08's "no package" claim stands. Success/failure is communicated by the snackbar plus a `mediumImpact()`.

### Haptics: a semantic three-weight ladder
Applied **at the design-system level** (per ticket 08's themed built-ins), so screens cannot forget it — weight signals consequence, not decoration.

| Weight | Used for |
|---|---|
| `selectionClick()` | Discrete selection changes: tab switch, segment switch, filter chip, dietary chip, slider steps |
| `lightImpact()` | Default acknowledgement for any tappable in the design system |
| `mediumImpact()` | Committing a data change: confirm, save, add-to-plan, mark-cooked, delete-commit |

`heavyImpact()` and `vibrate()` are unused.

**Gaps this closes** (all currently silent): "Sign in with Google" — the single most important tap in the app; sign-in success and sign-out; the camera shutter; scan success/failure; both review-screen confirms; the Generate tap **and generation completion**, the highest-value moment in the app; swipe-delete commit (the fling has no impact today); filter-chip selection; recipe card taps, "Go", search-result save, Import, "Add to plan"; every tab-bar switch; slider steps; tapping an empty "Add a dinner" slot; and checkout completion.

**Bug it fixes**: tap-delete currently buzzes **twice** — `medium` at `pantry/index.tsx:245` plus `IconButton.tsx:38`'s own `light`. Centralising the ladder removes the double-fire.

### Transitions
- **Skeleton → content cross-fades** (`AnimatedSwitcher`), never a hard cut. Today every skeleton→content swap is abrupt, and loading languages are inconsistent (skeletons on lists, a bare `ActivityIndicator` on recipe detail). Standardise on skeletons everywhere.
- **Animated list mutations** — implicit animations / `AnimatedList` for insert and remove, and the gap left by a `Dismissible` animates closed rather than snapping shut. Today only Pantry animates at all (`LayoutAnimation` on load and delete); Shop's section jump on toggle, Plan's new entries, and both Meals lists all snap.
- **Animate the Plan progress ring.** It is currently fully static (`plan/index.tsx:47-67`) so it **teleports** from 0/5 to 5/5 after generation — `TweenAnimationBuilder` on the arc. Likewise the "Cooked?" pill → checkmark swap should transition rather than jump.
- **Stop using `replace` where the user is conceptually going back.** `shop/review.tsx:35` replaces to Shop, so returning slides *forward* and leaves `describe` in the stack (Android back resurrects it with stale text).
- **One splash composition** via `flutter_native_splash`. Today the native splash (`splash-icon.png` on `#2e9d63`) hands over to a *different* JS `SplashScreen` composition (116px mark + wordmark + pulsing dots) — same green, different layout, unanimated pop — and then to the tab tree with no fade. Note there is no `expo-splash-screen` dependency and no `preventAutoHideAsync` anywhere, which is why the handover is uncontrolled.
- Standard Material page transitions via `go_router`; fade the expiry banner in and out rather than popping it.
