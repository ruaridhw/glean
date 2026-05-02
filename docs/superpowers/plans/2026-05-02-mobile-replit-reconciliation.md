# Mobile Replit Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the Replit prototype with the real mobile app by documenting decisions, adding a small reusable UI foundation, and porting Pantry as the first Android-first proof screen.

**Architecture:** Keep SQLite/Drizzle, backend integration, and auth canonical, but compare navigation, flows, tests, and build-chain decisions against Replit before preserving them. Add focused UI primitives under `mobile/src/components/ui/` and presentation helpers under `mobile/src/pantry/`, then rewrite `mobile/app/(tabs)/pantry/index.tsx` to use real pantry queries with Replit-style cards, headers, badges, icons, and actions.

**Tech Stack:** Expo SDK 54, React Native 0.81, Expo Router, SQLite/Drizzle, Jest Expo, Testing Library React Native, Biome, TypeScript, Knip, highest-level smoke/e2e only.

---

## File structure

Create:

- `docs/mobile-replit-reconciliation-audit.md` — human-readable comparison matrix for screens, dependencies, build-chain, test strategy, and phase-one decisions.
- `mobile/src/platform/haptics.ts` — safe wrapper around optional Expo haptics calls, with no-op fallback when unavailable or failing.
- `mobile/src/pantry/presentation.ts` — pure Pantry mapping helpers for category metadata, grouped sections, quantity labels, and expiry badges.
- `mobile/tests/pantry/presentation.test.ts` — lower-level tests for Pantry presentation mapping.
- `mobile/src/components/ui/AppScreen.tsx` — screen scaffold with safe-area-aware header, optional subtitle/actions, and bottom-tab padding.
- `mobile/src/components/ui/Card.tsx` — reusable card container and row surface.
- `mobile/src/components/ui/Badge.tsx` — reusable chip/badge component for category and expiry UI.
- `mobile/src/components/ui/IconButton.tsx` — reusable icon button with accessibility label and optional haptic feedback.
- `mobile/tests/components/ui-foundation.test.tsx` — component tests for the shared foundation.
- `mobile/tests/pantry/pantry-screen.test.tsx` — focused screen test proving Pantry renders grouped real data and exposes core actions.

Modify:

- `mobile/package.json` — add `expo-haptics` only; keep npm for this phase after documenting the build-chain decision.
- `mobile/package-lock.json` — update via `npm install`.
- `mobile/src/theme/index.ts` — expand color roles, spacing/radius, category colors, and expiry colors.
- `mobile/tests/theme/theme.test.ts` — update theme assertions to cover new roles.
- `mobile/app/(tabs)/_layout.tsx` — replace emoji tab icons with vector icons, preserving route structure unless audit later says otherwise.
- `mobile/app/(tabs)/pantry/index.tsx` — port the Pantry screen to Replit-style presentation over existing DB queries.
- `mobile/e2e/smoke.yaml` — only if current smoke navigation breaks; do not maintain detailed e2e screen coverage during this migration.

Do not modify in this phase:

- DB schema or Drizzle migrations. `pantry_items.expiry_date` already exists, so expiry badges can be implemented without schema work.
- Backend APIs.
- Replit hard-coded `AppContext` state.
- Meals, Plan, Shop, or Settings screens beyond audit documentation.

---

### Task 1: Write the reconciliation audit and phase-one decisions

**Files:**
- Create: `docs/mobile-replit-reconciliation-audit.md`
- Read: `docs/superpowers/specs/2026-05-02-mobile-replit-reconciliation-design.md`
- Read: `mobile/package.json`
- Read: `mobile_replit/package.json`
- Read: `mobile_replit/artifacts/meal-planner/package.json`
- Read: `mobile/app/(tabs)/pantry/index.tsx`
- Read: `mobile_replit/artifacts/meal-planner/app/(tabs)/index.tsx`
- Read: `mobile/app/(tabs)/_layout.tsx`
- Read: `mobile_replit/artifacts/meal-planner/app/(tabs)/_layout.tsx`

- [ ] **Step 1: Create the audit document with concrete phase-one decisions**

Write `docs/mobile-replit-reconciliation-audit.md` with this content:

```markdown
# Mobile/Replit Reconciliation Audit

## Phase-one decision summary

- Source of truth for data/backend/auth: `mobile/`.
- Visual and UX target: `mobile_replit/artifacts/meal-planner`.
- Navigation and flow policy: compare first; keep or change intentionally.
- Build-chain phase-one decision: keep `mobile/` on npm for the Pantry proof-of-port. Re-evaluate pnpm/workspace after Pantry validates the UI approach.
- Dependency phase-one decision: add `expo-haptics`; keep existing `@expo/vector-icons`; defer `expo-blur`, `expo-glass-effect`, `expo-image`, and `expo-router/unstable-native-tabs`.
- Test strategy: use lower-level Jest/integration tests for presentation and Pantry behavior; keep only highest-level smoke/e2e coverage.

## Why npm stays for phase one

The Replit project uses a pnpm workspace because it manages generated artifacts, a mock API server, workspace-local packages, and Replit-specific dev scripts. The current Glean repo has one JS app under `mobile/` and a Python backend managed by `uv`. There is not yet a shared TypeScript package or multiple real JS packages that require workspace coordination. Migrating npm to pnpm during the first UI proof would mix tooling migration risk with UI migration risk. The decision is to defer pnpm/workspace migration until after the Pantry proof or until a shared JS package is introduced.

## Screen comparison matrix

| Screen | mobile/ path | Replit path | Visual/UX target | Real data source | Phase-one decision |
| --- | --- | --- | --- | --- | --- |
| Pantry | `mobile/app/(tabs)/pantry/index.tsx` | `mobile_replit/artifacts/meal-planner/app/(tabs)/index.tsx` | Large header, cards, category dots, expiry badges, polished add/delete/edit actions | `getPantryItems`, `updatePantryQuantity`, `deletePantryItem` | Port now as proof screen |
| Meals | `mobile/app/(tabs)/meals/index.tsx` | `mobile_replit/artifacts/meal-planner/app/(tabs)/meals.tsx` | Saved/suggested tabs, recipe cards, detail modal | real recipe DB/API | Defer until after Pantry |
| Plan | `mobile/app/(tabs)/plan/index.tsx` | `mobile_replit/artifacts/meal-planner/app/(tabs)/plan.tsx` | Weekly navigation, progress, shopping list generation | real meal plan DB | Defer until after Pantry |
| Shop | `mobile/app/(tabs)/shop/index.tsx` | `mobile_replit/artifacts/meal-planner/app/(tabs)/shop.tsx` | Grouped checked/unchecked list, move checked to pantry | real shopping DB | Defer until after Pantry |
| Settings | `mobile/app/(tabs)/settings/index.tsx` | `mobile_replit/artifacts/meal-planner/app/(tabs)/settings.tsx` | Stats, preferences, clear data UI | real config DB/auth | Defer until after Pantry |

## Pantry data mapping

| Replit concept | Real mobile field/source | Decision |
| --- | --- | --- |
| `item.name` | `PantryItem.canonical_name` | Adapt now |
| `item.quantity` | `PantryItem.quantity` | Adapt now |
| `item.unit` | `PantryItem.unit` | Adapt now |
| `item.category` | `PantryItem.food_group ?? "other"` | Adapt now with display metadata |
| `item.expiryDate` | `PantryItem.expiry_date` | Port now; schema already supports it |
| Add item modal | Existing add route with scan/describe/manual choices | Keep route flow for phase one; restyle later |
| Recipe quick view from expiring items | Requires recipe suggestion wiring | Defer |

## Dependency comparison

| Dependency/pattern | Replit usage | Phase-one decision | Reason |
| --- | --- | --- | --- |
| `expo-haptics` | Button feedback | Adopt | Low risk, Android/iOS support, optional wrapper prevents correctness dependency |
| Vector icons | Rich tab/action icons | Adopt/expand existing dependency | `@expo/vector-icons` already exists in `mobile/` |
| `expo-blur` | Tab/background polish | Defer | Not required for Pantry proof; Android behavior should be checked separately |
| `expo-glass-effect` | iOS glass polish | Defer | iOS enhancement only, not Android-first baseline |
| `expo-router/unstable-native-tabs` | Native tabs | Defer | Route compatibility and Android behavior need separate proof |
| pnpm workspace | Replit artifact/workspace management | Defer | Not justified before a shared JS package or multi-package JS repo need |

## Test strategy

- Add pure tests for Pantry presentation mapping.
- Add component tests for reusable UI primitives.
- Add a focused Pantry screen test with mocked DB functions.
- Keep highest-level smoke/e2e coverage only; do not chase detailed e2e updates unless the smoke path breaks.
```

- [ ] **Step 2: Verify the audit document exists and has no incomplete markers**

Run:

```bash
rg "TBD|TODO|FIXME" docs/mobile-replit-reconciliation-audit.md || true
```

Expected: no matches.

- [ ] **Step 3: Commit the audit**

```bash
git add docs/mobile-replit-reconciliation-audit.md
git commit -m "docs: add mobile replit reconciliation audit"
```

---

### Task 2: Add haptics dependency and safe wrapper

**Files:**
- Modify: `mobile/package.json`
- Modify: `mobile/package-lock.json`
- Create: `mobile/src/platform/haptics.ts`
- Test: `mobile/tests/platform/haptics.test.ts`

- [ ] **Step 1: Install haptics**

Run:

```bash
cd mobile
npx expo install expo-haptics
```

Expected: `mobile/package.json` contains `"expo-haptics"`, and `mobile/package-lock.json` changes.

- [ ] **Step 2: Write the failing haptics wrapper test**

Create `mobile/tests/platform/haptics.test.ts`:

```ts
jest.mock("expo-haptics", () => ({
  ImpactFeedbackStyle: { Light: "Light", Medium: "Medium" },
  NotificationFeedbackType: { Success: "Success", Warning: "Warning" },
  impactAsync: jest.fn().mockResolvedValue(undefined),
  notificationAsync: jest.fn().mockResolvedValue(undefined),
}));

import * as ExpoHaptics from "expo-haptics";
import { hapticImpact, hapticNotify } from "@/platform/haptics";

describe("haptics wrapper", () => {
  it("sends light impact feedback", async () => {
    await hapticImpact("light");
    expect(ExpoHaptics.impactAsync).toHaveBeenCalledWith(ExpoHaptics.ImpactFeedbackStyle.Light);
  });

  it("sends success notification feedback", async () => {
    await hapticNotify("success");
    expect(ExpoHaptics.notificationAsync).toHaveBeenCalledWith(
      ExpoHaptics.NotificationFeedbackType.Success,
    );
  });

  it("swallows haptic failures", async () => {
    (ExpoHaptics.impactAsync as jest.Mock).mockRejectedValueOnce(new Error("unavailable"));
    await expect(hapticImpact("medium")).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 3: Run the failing test**

Run:

```bash
cd mobile
npm test -- tests/platform/haptics.test.ts --runInBand
```

Expected: FAIL with module not found for `@/platform/haptics`.

- [ ] **Step 4: Implement the wrapper**

Create `mobile/src/platform/haptics.ts`:

```ts
import * as Haptics from "expo-haptics";

export type HapticImpact = "light" | "medium";
export type HapticNotification = "success" | "warning";

const impactMap: Record<HapticImpact, Haptics.ImpactFeedbackStyle> = {
  light: Haptics.ImpactFeedbackStyle.Light,
  medium: Haptics.ImpactFeedbackStyle.Medium,
};

const notificationMap: Record<HapticNotification, Haptics.NotificationFeedbackType> = {
  success: Haptics.NotificationFeedbackType.Success,
  warning: Haptics.NotificationFeedbackType.Warning,
};

export async function hapticImpact(style: HapticImpact = "light"): Promise<void> {
  try {
    await Haptics.impactAsync(impactMap[style]);
  } catch {
    // Haptics are polish only. Unsupported platforms must not break app behavior.
  }
}

export async function hapticNotify(type: HapticNotification): Promise<void> {
  try {
    await Haptics.notificationAsync(notificationMap[type]);
  } catch {
    // Haptics are polish only. Unsupported platforms must not break app behavior.
  }
}
```

- [ ] **Step 5: Run the haptics test**

Run:

```bash
cd mobile
npm test -- tests/platform/haptics.test.ts --runInBand
```

Expected: PASS.

- [ ] **Step 6: Commit haptics**

```bash
git add mobile/package.json mobile/package-lock.json mobile/src/platform/haptics.ts mobile/tests/platform/haptics.test.ts
git commit -m "feat(mobile): add safe haptics wrapper"
```

---

### Task 3: Expand theme tokens for the Replit visual direction

**Files:**
- Modify: `mobile/src/theme/index.ts`
- Modify: `mobile/tests/theme/theme.test.ts`

- [ ] **Step 1: Replace the theme test with expanded role assertions**

Update `mobile/tests/theme/theme.test.ts`:

```ts
import { theme } from "@/theme";

describe("theme", () => {
  it("exports primary colour as teal", () => {
    expect(theme.colors.primary).toBe("#2a9d8f");
  });

  it("exports warm app surfaces", () => {
    expect(theme.colors.background).toBe("#fdfaf6");
    expect(theme.colors.surface).toBe("#f0e8de");
    expect(theme.colors.card).toBe("#ffffff");
    expect(theme.colors.muted).toBe("#f3eee8");
  });

  it("exports category colors for pantry groups", () => {
    expect(theme.categoryColors.vegetables).toBe("#4CAF50");
    expect(theme.categoryColors.protein).toBe("#F44336");
    expect(theme.categoryColors.dairy).toBe("#2196F3");
    expect(theme.categoryColors.carbohydrates).toBe("#FF9800");
    expect(theme.categoryColors.other).toBe("#64748B");
  });

  it("exports expiry colors for urgency badges", () => {
    expect(theme.expiryColors.expired).toBe("#EF4444");
    expect(theme.expiryColors.soon).toBe("#E07B39");
    expect(theme.expiryColors.later).toBe("#F59E0B");
  });

  it("has all required spacing keys in order", () => {
    expect(Object.keys(theme.spacing)).toEqual(["xs", "sm", "md", "lg", "xl", "xxl"]);
  });

  it("exports card shadow with warm shadow colour", () => {
    expect(theme.shadow.card.shadowColor).toBe("#2c1a0e");
  });
});
```

- [ ] **Step 2: Run the failing theme test**

Run:

```bash
cd mobile
npm test -- tests/theme/theme.test.ts --runInBand
```

Expected: FAIL because `muted`, `categoryColors`, and `expiryColors` do not exist yet.

- [ ] **Step 3: Expand the theme**

Update `mobile/src/theme/index.ts`:

```ts
export const theme = {
  colors: {
    background: "#fdfaf6",
    surface: "#f0e8de",
    card: "#ffffff",
    border: "#ede3d8",
    muted: "#f3eee8",
    mutedForeground: "#9c7a5e",
    primary: "#2a9d8f",
    primaryLight: "#e8f5f3",
    primaryForeground: "#ffffff",
    secondary: "#f7f1ea",
    accent: "#e07c3c",
    warning: "#e07c3c",
    warningLight: "#fde8d0",
    success: "#1a6b4a",
    successLight: "#d4f0e8",
    danger: "#EF4444",
    text: "#2c1a0e",
    textSecondary: "#9c7a5e",
    textDisabled: "#c8b8a8",
  },
  categoryColors: {
    vegetables: "#4CAF50",
    fruit: "#4CAF50",
    protein: "#F44336",
    dairy: "#2196F3",
    carbohydrates: "#FF9800",
    fats: "#FF9800",
    condiments: "#8B5CF6",
    frozen: "#00BCD4",
    other: "#64748B",
  },
  expiryColors: {
    expired: "#EF4444",
    soon: "#E07B39",
    later: "#F59E0B",
    none: "#f3eee8",
  },
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  radius: { sm: 8, md: 12, lg: 16, xl: 20, pill: 999 },
  shadow: {
    card: {
      shadowColor: "#2c1a0e",
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.07,
      shadowRadius: 6,
      elevation: 2,
    },
    sheet: {
      shadowColor: "#2c1a0e",
      shadowOffset: { width: 0, height: -2 },
      shadowOpacity: 0.1,
      shadowRadius: 20,
      elevation: 8,
    },
    fab: {
      shadowColor: "#2a9d8f",
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.3,
      shadowRadius: 16,
      elevation: 8,
    },
  },
  typography: {
    largeTitle: { fontSize: 34, fontWeight: "800", letterSpacing: -0.5 },
    title2: { fontSize: 22, fontWeight: "700" },
    headline: { fontSize: 17, fontWeight: "600" },
    body: { fontSize: 17, fontWeight: "400" },
    subhead: { fontSize: 15, fontWeight: "400" },
    caption: { fontSize: 12, fontWeight: "400" },
    sectionLabel: {
      fontSize: 11,
      fontWeight: "700",
      textTransform: "uppercase",
      letterSpacing: 0.7,
    },
  },
} as const;
```

- [ ] **Step 4: Run the theme test**

Run:

```bash
cd mobile
npm test -- tests/theme/theme.test.ts --runInBand
```

Expected: PASS.

- [ ] **Step 5: Commit theme expansion**

```bash
git add mobile/src/theme/index.ts mobile/tests/theme/theme.test.ts
git commit -m "feat(mobile): expand theme tokens for replit port"
```

---

### Task 4: Add Pantry presentation mapping helpers

**Files:**
- Create: `mobile/src/pantry/presentation.ts`
- Create: `mobile/tests/pantry/presentation.test.ts`

- [ ] **Step 1: Write failing Pantry presentation tests**

Create `mobile/tests/pantry/presentation.test.ts`:

```ts
import type { PantryItem } from "@/types";
import {
  formatPantryQuantity,
  getExpiryBadge,
  getPantryCategoryMeta,
  groupPantryItems,
} from "@/pantry/presentation";

const baseItem: PantryItem = {
  id: 1,
  ingredient_id: 10,
  quantity: 2,
  unit: "kg",
  unit_price: null,
  expiry_date: null,
  last_used_at: null,
  updated_at: "2026-05-02T00:00:00Z",
  canonical_name: "broccoli",
  is_staple: false,
  food_group: "vegetables",
};

describe("pantry presentation", () => {
  it("maps known food groups to display metadata", () => {
    expect(getPantryCategoryMeta("vegetables")).toEqual({
      key: "vegetables",
      label: "Veg & Fruit",
      color: "#4CAF50",
      icon: "leaf-outline",
    });
  });

  it("falls back unknown groups to other", () => {
    expect(getPantryCategoryMeta(null)).toEqual({
      key: "other",
      label: "Other",
      color: "#64748B",
      icon: "cube-outline",
    });
  });

  it("formats quantities with a space between number and unit", () => {
    expect(formatPantryQuantity({ ...baseItem, quantity: 1.5, unit: "kg" })).toBe("1.5 kg");
    expect(formatPantryQuantity({ ...baseItem, quantity: 2, unit: "whole" })).toBe("2 whole");
  });

  it("groups pantry items by display category", () => {
    const grouped = groupPantryItems([
      baseItem,
      { ...baseItem, id: 2, canonical_name: "milk", food_group: "dairy" },
    ]);

    expect(grouped.map((section) => section.title)).toEqual(["Veg & Fruit", "Dairy"]);
    expect(grouped[0]!.items[0]!.canonical_name).toBe("broccoli");
  });

  it("returns expiry badge labels relative to a supplied date", () => {
    const today = new Date("2026-05-02T12:00:00Z");
    expect(getExpiryBadge("2026-05-01", today)).toEqual({ label: "Expired", tone: "expired" });
    expect(getExpiryBadge("2026-05-02", today)).toEqual({ label: "Today", tone: "expired" });
    expect(getExpiryBadge("2026-05-04", today)).toEqual({ label: "2d left", tone: "soon" });
    expect(getExpiryBadge("2026-05-07", today)).toEqual({ label: "5d left", tone: "later" });
    expect(getExpiryBadge(null, today)).toBeNull();
  });
});
```

- [ ] **Step 2: Run the failing presentation tests**

Run:

```bash
cd mobile
npm test -- tests/pantry/presentation.test.ts --runInBand
```

Expected: FAIL with module not found for `@/pantry/presentation`.

- [ ] **Step 3: Implement Pantry presentation helpers**

Create `mobile/src/pantry/presentation.ts`:

```ts
import { theme } from "@/theme";
import type { PantryItem } from "@/types";

type CategoryKey = keyof typeof theme.categoryColors;

export interface PantryCategoryMeta {
  key: CategoryKey;
  label: string;
  color: string;
  icon: string;
}

export interface PantrySection {
  key: string;
  title: string;
  meta: PantryCategoryMeta;
  items: PantryItem[];
}

export interface ExpiryBadgeModel {
  label: string;
  tone: "expired" | "soon" | "later";
}

const categoryMeta: Record<CategoryKey, Omit<PantryCategoryMeta, "key" | "color">> = {
  vegetables: { label: "Veg & Fruit", icon: "leaf-outline" },
  fruit: { label: "Veg & Fruit", icon: "leaf-outline" },
  protein: { label: "Meat & Fish", icon: "fish-outline" },
  dairy: { label: "Dairy", icon: "water-outline" },
  carbohydrates: { label: "Cupboard", icon: "cube-outline" },
  fats: { label: "Cupboard", icon: "cube-outline" },
  condiments: { label: "Cupboard", icon: "cube-outline" },
  frozen: { label: "Frozen", icon: "snow-outline" },
  other: { label: "Other", icon: "cube-outline" },
};

function isCategoryKey(value: string | null | undefined): value is CategoryKey {
  return Boolean(value && value in theme.categoryColors);
}

export function getPantryCategoryMeta(foodGroup: string | null | undefined): PantryCategoryMeta {
  const key: CategoryKey = isCategoryKey(foodGroup) ? foodGroup : "other";
  return {
    key,
    label: categoryMeta[key].label,
    color: theme.categoryColors[key],
    icon: categoryMeta[key].icon,
  };
}

export function formatPantryQuantity(item: Pick<PantryItem, "quantity" | "unit">): string {
  return `${Number.isInteger(item.quantity) ? item.quantity.toFixed(0) : item.quantity} ${item.unit}`;
}

export function groupPantryItems(items: PantryItem[]): PantrySection[] {
  const sections = new Map<string, PantrySection>();

  for (const item of items) {
    const meta = getPantryCategoryMeta(item.food_group);
    const existing = sections.get(meta.label);
    if (existing) {
      existing.items.push(item);
    } else {
      sections.set(meta.label, {
        key: meta.label,
        title: meta.label,
        meta,
        items: [item],
      });
    }
  }

  return Array.from(sections.values());
}

export function getExpiryBadge(
  expiryDate: string | null | undefined,
  now: Date = new Date(),
): ExpiryBadgeModel | null {
  if (!expiryDate) return null;

  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  const expiry = new Date(`${expiryDate}T00:00:00`);
  const days = Math.round((expiry.getTime() - today.getTime()) / 86_400_000);

  if (days < 0) return { label: "Expired", tone: "expired" };
  if (days === 0) return { label: "Today", tone: "expired" };
  if (days <= 2) return { label: `${days}d left`, tone: "soon" };
  return { label: `${days}d left`, tone: "later" };
}
```

- [ ] **Step 4: Run the presentation tests**

Run:

```bash
cd mobile
npm test -- tests/pantry/presentation.test.ts --runInBand
```

Expected: PASS.

- [ ] **Step 5: Commit Pantry presentation helpers**

```bash
git add mobile/src/pantry/presentation.ts mobile/tests/pantry/presentation.test.ts
git commit -m "feat(mobile): add pantry presentation helpers"
```

---

### Task 5: Add shared UI foundation components

**Files:**
- Create: `mobile/src/components/ui/AppScreen.tsx`
- Create: `mobile/src/components/ui/Card.tsx`
- Create: `mobile/src/components/ui/Badge.tsx`
- Create: `mobile/src/components/ui/IconButton.tsx`
- Create: `mobile/tests/components/ui-foundation.test.tsx`

- [ ] **Step 1: Write failing component tests**

Create `mobile/tests/components/ui-foundation.test.tsx`:

```tsx
import { fireEvent, render } from "@testing-library/react-native";
import { Text } from "react-native";
import { AppScreen } from "@/components/ui/AppScreen";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { IconButton } from "@/components/ui/IconButton";

jest.mock("@/platform/haptics", () => ({
  hapticImpact: jest.fn().mockResolvedValue(undefined),
}));

describe("UI foundation", () => {
  it("renders a screen title and subtitle", () => {
    const screen = render(
      <AppScreen title="Pantry" subtitle="4 items">
        <Text>Body</Text>
      </AppScreen>,
    );

    expect(screen.getByText("Pantry")).toBeTruthy();
    expect(screen.getByText("4 items")).toBeTruthy();
    expect(screen.getByText("Body")).toBeTruthy();
  });

  it("renders cards and badges", () => {
    const screen = render(
      <Card testID="card">
        <Badge label="2d left" tone="warning" testID="badge" />
      </Card>,
    );

    expect(screen.getByTestId("card")).toBeTruthy();
    expect(screen.getByTestId("badge")).toBeTruthy();
    expect(screen.getByText("2d left")).toBeTruthy();
  });

  it("fires icon button presses", () => {
    const onPress = jest.fn();
    const screen = render(
      <IconButton icon="add" accessibilityLabel="Add item" onPress={onPress} />,
    );

    fireEvent.press(screen.getByLabelText("Add item"));
    expect(onPress).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run the failing component tests**

Run:

```bash
cd mobile
npm test -- tests/components/ui-foundation.test.tsx --runInBand
```

Expected: FAIL with module not found for `AppScreen`, `Card`, `Badge`, or `IconButton`.

- [ ] **Step 3: Implement AppScreen**

Create `mobile/src/components/ui/AppScreen.tsx`:

```tsx
import type { ReactNode } from "react";
import { Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@/theme";

interface AppScreenProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  scroll?: boolean;
  testID?: string;
}

export function AppScreen({
  title,
  subtitle,
  actions,
  children,
  scroll = false,
  testID,
}: AppScreenProps) {
  const insets = useSafeAreaInsets();
  const bottomPadding = insets.bottom + (Platform.OS === "web" ? 100 : 90);

  const body = scroll ? (
    <ScrollView
      contentContainerStyle={[styles.scrollContent, { paddingBottom: bottomPadding }]}
      showsVerticalScrollIndicator={false}
    >
      {children}
    </ScrollView>
  ) : (
    <View style={[styles.body, { paddingBottom: bottomPadding }]}>{children}</View>
  );

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID={testID}>
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={styles.title}>{title}</Text>
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        </View>
        {actions ? <View style={styles.actions}>{actions}</View> : null}
      </View>
      {body}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.background },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.lg,
    paddingBottom: theme.spacing.md,
    backgroundColor: theme.colors.background,
  },
  headerText: { flex: 1 },
  title: { ...theme.typography.largeTitle, color: theme.colors.text },
  subtitle: { ...theme.typography.subhead, color: theme.colors.textSecondary, marginTop: 2 },
  actions: { flexDirection: "row", alignItems: "center", gap: theme.spacing.sm },
  body: { flex: 1, paddingHorizontal: theme.spacing.lg },
  scrollContent: { paddingHorizontal: theme.spacing.lg },
});
```

- [ ] **Step 4: Implement Card**

Create `mobile/src/components/ui/Card.tsx`:

```tsx
import type { ReactNode } from "react";
import { StyleSheet, View, type ViewProps } from "react-native";
import { theme } from "@/theme";

interface CardProps extends ViewProps {
  children: ReactNode;
}

export function Card({ children, style, ...props }: CardProps) {
  return (
    <View style={[styles.card, style]} {...props}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.card,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    borderWidth: 1,
    padding: theme.spacing.md,
    ...theme.shadow.card,
  },
});
```

- [ ] **Step 5: Implement Badge**

Create `mobile/src/components/ui/Badge.tsx`:

```tsx
import { StyleSheet, Text, View, type ViewProps } from "react-native";
import { theme } from "@/theme";

type BadgeTone = "neutral" | "primary" | "warning" | "danger";

interface BadgeProps extends ViewProps {
  label: string;
  tone?: BadgeTone;
}

const toneStyles: Record<BadgeTone, { backgroundColor: string; color: string }> = {
  neutral: { backgroundColor: theme.colors.muted, color: theme.colors.mutedForeground },
  primary: { backgroundColor: theme.colors.primary, color: theme.colors.primaryForeground },
  warning: { backgroundColor: theme.colors.warning, color: theme.colors.primaryForeground },
  danger: { backgroundColor: theme.colors.danger, color: theme.colors.primaryForeground },
};

export function Badge({ label, tone = "neutral", style, ...props }: BadgeProps) {
  const colors = toneStyles[tone];
  return (
    <View style={[styles.badge, { backgroundColor: colors.backgroundColor }, style]} {...props}>
      <Text style={[styles.text, { color: colors.color }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "flex-start",
    borderRadius: theme.radius.pill,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 3,
  },
  text: { fontSize: theme.typography.caption.fontSize, fontWeight: "700" },
});
```

- [ ] **Step 6: Implement IconButton**

Create `mobile/src/components/ui/IconButton.tsx`:

```tsx
import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, type PressableProps } from "react-native";
import { hapticImpact } from "@/platform/haptics";
import { theme } from "@/theme";

interface IconButtonProps extends Omit<PressableProps, "children"> {
  icon: keyof typeof Ionicons.glyphMap;
  accessibilityLabel: string;
  color?: string;
  backgroundColor?: string;
  size?: number;
}

export function IconButton({
  icon,
  accessibilityLabel,
  color = theme.colors.text,
  backgroundColor = theme.colors.muted,
  size = 20,
  onPress,
  style,
  ...props
}: IconButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      hitSlop={8}
      style={[styles.button, { backgroundColor }, style]}
      onPress={(event) => {
        void hapticImpact("light");
        onPress?.(event);
      }}
      {...props}
    >
      <Ionicons name={icon} size={size} color={color} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: "center",
    borderRadius: theme.radius.pill,
    height: 40,
    justifyContent: "center",
    width: 40,
  },
});
```

- [ ] **Step 7: Run component tests**

Run:

```bash
cd mobile
npm test -- tests/components/ui-foundation.test.tsx --runInBand
```

Expected: PASS.

- [ ] **Step 8: Commit UI foundation**

```bash
git add mobile/src/components/ui/AppScreen.tsx mobile/src/components/ui/Card.tsx mobile/src/components/ui/Badge.tsx mobile/src/components/ui/IconButton.tsx mobile/tests/components/ui-foundation.test.tsx
git commit -m "feat(mobile): add shared ui foundation"
```

---

### Task 6: Replace emoji tab icons with vector icons

**Files:**
- Modify: `mobile/app/(tabs)/_layout.tsx`

- [ ] **Step 1: Update tab layout imports and icons**

Replace `mobile/app/(tabs)/_layout.tsx` with:

```tsx
// mobile/app/(tabs)/_layout.tsx
import { Ionicons } from "@expo/vector-icons";
import { Tabs } from "expo-router";
import { theme } from "@/theme";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: theme.colors.textDisabled,
        tabBarStyle: {
          backgroundColor: theme.colors.surface,
          borderTopColor: theme.colors.border,
          borderTopWidth: 0.5,
        },
        tabBarLabelStyle: {
          fontSize: theme.typography.sectionLabel.fontSize,
          fontWeight: theme.typography.headline.fontWeight,
        },
      }}
    >
      <Tabs.Screen
        name="pantry"
        options={{
          title: "Pantry",
          tabBarButtonTestID: "tabs.pantry",
          tabBarIcon: ({ color }) => <Ionicons name="leaf-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="meals"
        options={{
          title: "Meals",
          tabBarButtonTestID: "tabs.meals",
          tabBarIcon: ({ color }) => <Ionicons name="restaurant-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="plan/index"
        options={{
          title: "Plan",
          tabBarButtonTestID: "tabs.plan",
          tabBarIcon: ({ color }) => <Ionicons name="calendar-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="shop/index"
        options={{
          title: "Shop",
          tabBarButtonTestID: "tabs.shop",
          tabBarIcon: ({ color }) => <Ionicons name="cart-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings/index"
        options={{
          title: "Settings",
          tabBarButtonTestID: "tabs.settings",
          tabBarIcon: ({ color }) => <Ionicons name="settings-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen name="pantry/add" options={{ href: null }} />
      <Tabs.Screen name="pantry/describe" options={{ href: null }} />
      <Tabs.Screen name="pantry/manual-entry" options={{ href: null }} />
      <Tabs.Screen name="pantry/review" options={{ href: null }} />
      <Tabs.Screen name="pantry/scan" options={{ href: null }} />
      <Tabs.Screen name="pantry/scan-progress" options={{ href: null }} />
      <Tabs.Screen name="meals/search" options={{ href: null }} />
      <Tabs.Screen name="meals/[id]" options={{ href: null }} />
    </Tabs>
  );
}
```

- [ ] **Step 2: Run TypeScript check**

Run:

```bash
cd mobile
npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 3: Commit tab icon polish**

```bash
git add 'mobile/app/(tabs)/_layout.tsx'
git commit -m "feat(mobile): replace tab emoji with vector icons"
```

---

### Task 7: Port Pantry screen to Replit-style real-data UI

**Files:**
- Modify: `mobile/app/(tabs)/pantry/index.tsx`
- Test: `mobile/tests/pantry/pantry-screen.test.tsx`

- [ ] **Step 1: Write focused Pantry screen test**

Create `mobile/tests/pantry/pantry-screen.test.tsx`:

```tsx
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import PantryScreen from "../../app/(tabs)/pantry";
import { deletePantryItem, getPantryItems, updatePantryQuantity } from "@/db/pantry";

jest.mock("expo-router", () => ({
  router: { push: jest.fn() },
  useFocusEffect: (callback: () => void) => callback(),
}));

jest.mock("@/db/pantry", () => ({
  getPantryItems: jest.fn(),
  updatePantryQuantity: jest.fn().mockResolvedValue(undefined),
  deletePantryItem: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/platform/haptics", () => ({
  hapticImpact: jest.fn().mockResolvedValue(undefined),
}));

describe("PantryScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getPantryItems as jest.Mock).mockResolvedValue([
      {
        id: 1,
        ingredient_id: 10,
        quantity: 2,
        unit: "kg",
        unit_price: null,
        expiry_date: "2026-05-04",
        last_used_at: null,
        updated_at: "2026-05-02T00:00:00Z",
        canonical_name: "broccoli",
        is_staple: false,
        food_group: "vegetables",
      },
      {
        id: 2,
        ingredient_id: 11,
        quantity: 1,
        unit: "L",
        unit_price: null,
        expiry_date: null,
        last_used_at: null,
        updated_at: "2026-05-02T00:00:00Z",
        canonical_name: "milk",
        is_staple: false,
        food_group: "dairy",
      },
    ]);
  });

  it("renders grouped pantry cards with real data", async () => {
    const screen = render(<PantryScreen />);

    await waitFor(() => expect(screen.getByText("broccoli")).toBeTruthy());
    expect(screen.getByText("Pantry")).toBeTruthy();
    expect(screen.getByText("2 items")).toBeTruthy();
    expect(screen.getByText("Veg & Fruit")).toBeTruthy();
    expect(screen.getByText("Dairy")).toBeTruthy();
    expect(screen.getByText("2 kg")).toBeTruthy();
    expect(screen.getByText("1 L")).toBeTruthy();
  });

  it("shows empty state actions when there are no items", async () => {
    (getPantryItems as jest.Mock).mockResolvedValueOnce([]);
    const screen = render(<PantryScreen />);

    await waitFor(() => expect(screen.getByText("Your pantry is empty")).toBeTruthy());
    expect(screen.getByText("Scan receipt")).toBeTruthy();
    expect(screen.getByText("Describe items")).toBeTruthy();
  });

  it("commits quantity edits", async () => {
    const screen = render(<PantryScreen />);

    await waitFor(() => expect(screen.getByText("broccoli")).toBeTruthy());
    fireEvent.press(screen.getByText("2 kg"));
    fireEvent.changeText(screen.getByDisplayValue("2"), "3");
    fireEvent(screen.getByDisplayValue("3"), "blur");

    await waitFor(() => expect(updatePantryQuantity).toHaveBeenCalledWith(1, 3));
  });

  it("deletes pantry items through the card action", async () => {
    const screen = render(<PantryScreen />);

    await waitFor(() => expect(screen.getByText("broccoli")).toBeTruthy());
    fireEvent.press(screen.getByLabelText("Remove broccoli"));

    await waitFor(() => expect(deletePantryItem).toHaveBeenCalledWith(1));
  });
});
```

- [ ] **Step 2: Run the failing Pantry screen test**

Run:

```bash
cd mobile
npm test -- tests/pantry/pantry-screen.test.tsx --runInBand
```

Expected: FAIL because current Pantry UI does not render Replit-style cards/actions and still uses alert confirmation for deletion.

- [ ] **Step 3: Replace Pantry screen with Replit-style card UI over real queries**

Replace `mobile/app/(tabs)/pantry/index.tsx` with:

```tsx
// mobile/app/(tabs)/pantry/index.tsx

import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import {
  FlatList,
  LayoutAnimation,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { PantrySkeleton } from "@/components/skeletons/PantrySkeleton";
import { AppScreen } from "@/components/ui/AppScreen";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconButton } from "@/components/ui/IconButton";
import { deletePantryItem, getPantryItems, updatePantryQuantity } from "@/db/pantry";
import { hapticImpact } from "@/platform/haptics";
import {
  formatPantryQuantity,
  getExpiryBadge,
  getPantryCategoryMeta,
  groupPantryItems,
  type PantrySection,
} from "@/pantry/presentation";
import { theme } from "@/theme";
import type { PantryItem } from "@/types";

function expiryToneToBadgeTone(tone: "expired" | "soon" | "later"): "danger" | "warning" | "neutral" {
  if (tone === "expired") return "danger";
  if (tone === "soon") return "warning";
  return "neutral";
}

interface PantryItemCardProps {
  item: PantryItem;
  editingId: number | null;
  editQty: string;
  onStartEdit: (item: PantryItem) => void;
  onChangeEditQty: (quantity: string) => void;
  onCommitEdit: (item: PantryItem) => void;
  onDelete: (item: PantryItem) => void;
}

function PantryItemCard({
  item,
  editingId,
  editQty,
  onStartEdit,
  onChangeEditQty,
  onCommitEdit,
  onDelete,
}: PantryItemCardProps) {
  const meta = getPantryCategoryMeta(item.food_group);
  const expiryBadge = getExpiryBadge(item.expiry_date);
  const isEditing = editingId === item.id;

  return (
    <Card style={styles.itemCard} testID={`pantry.item.${item.id}`}>
      <View style={[styles.categoryDot, { backgroundColor: meta.color }]} />
      <View style={styles.itemContent}>
        <Text style={styles.itemName}>{item.canonical_name}</Text>
        {isEditing ? (
          <TextInput
            style={styles.editInput}
            value={editQty}
            onChangeText={onChangeEditQty}
            keyboardType="numeric"
            onBlur={() => onCommitEdit(item)}
            autoFocus
          />
        ) : (
          <Pressable onPress={() => onStartEdit(item)} accessibilityRole="button">
            <Text style={styles.itemQuantity}>{formatPantryQuantity(item)}</Text>
          </Pressable>
        )}
      </View>
      {expiryBadge ? (
        <Badge label={expiryBadge.label} tone={expiryToneToBadgeTone(expiryBadge.tone)} />
      ) : null}
      <IconButton
        icon="trash-outline"
        accessibilityLabel={`Remove ${item.canonical_name}`}
        color={theme.colors.textSecondary}
        backgroundColor="transparent"
        size={18}
        onPress={() => onDelete(item)}
      />
    </Card>
  );
}

interface PantrySectionViewProps {
  section: PantrySection;
  editingId: number | null;
  editQty: string;
  onStartEdit: (item: PantryItem) => void;
  onChangeEditQty: (quantity: string) => void;
  onCommitEdit: (item: PantryItem) => void;
  onDelete: (item: PantryItem) => void;
}

function PantrySectionView({
  section,
  editingId,
  editQty,
  onStartEdit,
  onChangeEditQty,
  onCommitEdit,
  onDelete,
}: PantrySectionViewProps) {
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name={section.meta.icon as keyof typeof Ionicons.glyphMap} size={16} color={section.meta.color} />
        <Text style={styles.groupHeader}>{section.title.toUpperCase()}</Text>
      </View>
      {section.items.map((item) => (
        <PantryItemCard
          key={item.id}
          item={item}
          editingId={editingId}
          editQty={editQty}
          onStartEdit={onStartEdit}
          onChangeEditQty={onChangeEditQty}
          onCommitEdit={onCommitEdit}
          onDelete={onDelete}
        />
      ))}
    </View>
  );
}

export default function PantryScreen() {
  const [items, setItems] = useState<PantryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editQty, setEditQty] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const result = await getPantryItems();
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setItems(result);
    setLoading(false);
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  async function commitEdit(item: PantryItem) {
    const qty = parseFloat(editQty);
    if (!Number.isNaN(qty) && qty > 0) {
      await updatePantryQuantity(item.id, qty);
    }
    setEditingId(null);
    await load();
  }

  async function deleteItem(item: PantryItem) {
    await hapticImpact("medium");
    await deletePantryItem(item.id);
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    await load();
  }

  const sections = groupPantryItems(items);

  if (loading) {
    return (
      <AppScreen title="Pantry" testID="pantry.screen">
        <PantrySkeleton />
      </AppScreen>
    );
  }

  if (items.length === 0) {
    return (
      <AppScreen
        title="Pantry"
        subtitle="Reduce waste, eat what you have"
        testID="pantry.screen"
        actions={
          <IconButton
            icon="add"
            accessibilityLabel="Add pantry item"
            color={theme.colors.primaryForeground}
            backgroundColor={theme.colors.primary}
            onPress={() => router.push("/(tabs)/pantry/add")}
          />
        }
      >
        <EmptyState
          testID="pantry.emptyState"
          icon="basket-outline"
          title="Your pantry is empty"
          message="Scan a receipt or describe what you have to get started."
          actions={[
            { label: "Scan receipt", onPress: () => router.push("/(tabs)/pantry/scan") },
            { label: "Describe items", onPress: () => router.push("/(tabs)/pantry/describe") },
          ]}
        />
      </AppScreen>
    );
  }

  return (
    <AppScreen
      title="Pantry"
      subtitle={`${items.length} ${items.length === 1 ? "item" : "items"}`}
      testID="pantry.screen"
      actions={
        <IconButton
          icon="add"
          accessibilityLabel="Add pantry item"
          color={theme.colors.primaryForeground}
          backgroundColor={theme.colors.primary}
          onPress={() => router.push("/(tabs)/pantry/add")}
        />
      }
    >
      <FlatList
        testID="pantry.list"
        data={sections}
        keyExtractor={(section) => section.key}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.listContent}
        renderItem={({ item }) => (
          <PantrySectionView
            section={item}
            editingId={editingId}
            editQty={editQty}
            onStartEdit={(pantryItem) => {
              setEditingId(pantryItem.id);
              setEditQty(String(pantryItem.quantity));
            }}
            onChangeEditQty={setEditQty}
            onCommitEdit={commitEdit}
            onDelete={deleteItem}
          />
        )}
      />
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  listContent: { paddingBottom: theme.spacing.xl },
  section: { marginBottom: theme.spacing.lg },
  sectionHeader: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.xs,
    marginBottom: theme.spacing.sm,
  },
  groupHeader: {
    ...theme.typography.sectionLabel,
    color: theme.colors.textSecondary,
  },
  itemCard: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.md,
    marginBottom: theme.spacing.sm,
    paddingVertical: theme.spacing.md,
  },
  categoryDot: {
    borderRadius: 5,
    height: 10,
    width: 10,
  },
  itemContent: { flex: 1 },
  itemName: {
    color: theme.colors.text,
    fontSize: theme.typography.headline.fontSize,
    fontWeight: theme.typography.headline.fontWeight,
    marginBottom: 2,
  },
  itemQuantity: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.subhead.fontSize,
  },
  editInput: {
    alignSelf: "flex-start",
    borderColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    color: theme.colors.text,
    fontSize: theme.typography.subhead.fontSize,
    minWidth: 72,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: theme.spacing.xs,
  },
});
```

- [ ] **Step 4: Run Pantry screen test**

Run:

```bash
cd mobile
npm test -- tests/pantry/pantry-screen.test.tsx --runInBand
```

Expected: PASS.

- [ ] **Step 5: Run related tests**

Run:

```bash
cd mobile
npm test -- tests/pantry/presentation.test.ts tests/components/ui-foundation.test.tsx tests/pantry/pantry-screen.test.tsx --runInBand
```

Expected: PASS.

- [ ] **Step 6: Commit Pantry port**

```bash
git add 'mobile/app/(tabs)/pantry/index.tsx' mobile/tests/pantry/pantry-screen.test.tsx
git commit -m "feat(mobile): port pantry to replit visual style"
```

---

### Task 8: Run verification and adjust only highest-level smoke/e2e if needed

**Files:**
- Modify if needed: `mobile/e2e/smoke.yaml`
- Modify if needed: `mobile/e2e/helpers/navigate-tab.yaml`

- [ ] **Step 1: Run focused mobile tests**

Run:

```bash
make test-mobile
```

Expected: PASS.

- [ ] **Step 2: Run mobile lint/checks**

Run:

```bash
make lint-mobile
```

Expected: PASS.

- [ ] **Step 3: Run TypeScript directly if lint fails before tsc output is visible**

Run only if Step 2 fails without clear TypeScript details:

```bash
cd mobile
npx tsc --noEmit
```

Expected: PASS or a concrete type error to fix in the files from Tasks 2-7.

- [ ] **Step 4: Run highest-level smoke/e2e only**

Run:

```bash
cd mobile
npm run e2e -- e2e/smoke.yaml
```

Expected: PASS. If this fails only because of changed labels or tab icon rendering, update the smoke path to verify launch and core tab navigation only. Do not update detailed screen-level e2e coverage in this migration phase.

- [ ] **Step 5: Commit verification fixes if any files changed**

If Step 4 required a smoke test adjustment, run:

```bash
git add mobile/e2e/smoke.yaml mobile/e2e/helpers/navigate-tab.yaml
git commit -m "test(mobile): keep smoke e2e aligned with pantry port"
```

If no files changed, do not commit.

---

### Task 9: Manual Android-first verification and final notes

**Files:**
- Modify: `docs/mobile-replit-reconciliation-audit.md`

- [ ] **Step 1: Start Android app through existing project helper**

Run:

```bash
make start-android
```

Expected: Expo starts on Android emulator. Keep the process running while manually checking Pantry.

- [ ] **Step 2: Verify Pantry manually on Android**

Check these behaviors in the emulator:

- Pantry tab opens.
- Header shows `Pantry` and item count when data exists.
- Empty state still offers scan receipt and describe items when data is empty.
- Pantry items render as cards grouped by category.
- Quantity text enters edit mode and saves a positive numeric value.
- Trash action removes the item.
- Add action opens the existing add route.
- Layout is not blocked by the bottom tab bar.

- [ ] **Step 3: Record verification notes**

Append this section to `docs/mobile-replit-reconciliation-audit.md`, updating the date and results with the actual run outcome:

```markdown
## Pantry proof verification

- Android manual check date: 2026-05-02
- Android result: PASS
- Highest-level smoke/e2e result: PASS
- Unit/integration result: PASS
- Lint/typecheck result: PASS
- Follow-up items:
  - Evaluate Meals saved/suggested UX after Pantry visual direction is accepted.
  - Revisit pnpm/workspace after a second screen or shared JS package need emerges.
  - Evaluate blur/native tabs/glass effects in a separate platform-polish spike.
```

- [ ] **Step 4: Commit verification notes**

```bash
git add docs/mobile-replit-reconciliation-audit.md
git commit -m "docs: record pantry proof verification"
```

---

## Self-review checklist

- Spec coverage:
  - Screen/build-chain/dependency audit: Task 1.
  - Build-chain decision without preserving npm by inertia: Task 1.
  - Haptics dependency and safe fallback: Task 2.
  - Shared theme/foundation: Tasks 3 and 5.
  - Pantry proof over real DB queries: Tasks 4 and 7.
  - Highest-level e2e only, lower-level tests preferred: Tasks 7 and 8.
  - Android-first verification: Task 9.
- Incomplete marker scan: no `TBD`, `TODO`, `FIXME`, vague future work, or missing-detail steps are present.
- Type consistency:
  - `PantryItem.expiry_date`, `food_group`, `canonical_name`, `quantity`, and `unit` match `mobile/src/types/index.ts`.
  - `theme.colors.muted`, `theme.colors.mutedForeground`, `theme.colors.primaryForeground`, `theme.categoryColors`, and `theme.expiryColors` are defined before use.
  - `hapticImpact` is defined before `IconButton` and Pantry use it.
  - `groupPantryItems`, `getExpiryBadge`, `formatPantryQuantity`, and `getPantryCategoryMeta` are defined before Pantry uses them.
