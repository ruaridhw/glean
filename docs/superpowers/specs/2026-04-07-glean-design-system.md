# Glean Design System

## Overview

**Direction:** iOS-native structure with a warm cream palette — clean grouped lists, crisp white cards, and a single teal accent colour. Approachable but precise. Light mode only.

**Philosophy:** Defer to iOS conventions wherever possible (grouped lists, system typography, native tab bar feel). The only personality comes from the warm cream background and the teal/terracotta accent pair — everything else stays out of the way so the food content (emoji, quantities, expiry urgency) reads clearly.

---

## Colour Tokens

| Token | Hex | Usage |
|-------|-----|-------|
| `color.background` | `#fdfaf6` | App background (all screens) |
| `color.surface` | `#f0e8de` | Search bars, section backgrounds, tab bar tint |
| `color.card` | `#ffffff` | List group cards, modal sheets |
| `color.border` | `#ede3d8` | Dividers, card borders, tab bar top line |
| `color.primary` | `#2a9d8f` | Teal — active tab, primary buttons, links, badges |
| `color.primaryLight` | `#e8f5f3` | Teal-tinted icon backgrounds |
| `color.warning` | `#e07c3c` | Terracotta — expiry badges, destructive-adjacent actions |
| `color.warningLight` | `#fde8d0` | Terracotta-tinted icon/badge backgrounds |
| `color.success` | `#1a6b4a` | In-stock / good-condition indicators |
| `color.successLight` | `#d4f0e8` | Success badge backgrounds |
| `color.text` | `#2c1a0e` | Primary text — headings, list item names |
| `color.textSecondary` | `#9c7a5e` | Secondary text — quantities, captions, placeholders |
| `color.textDisabled` | `#c8b8a8` | Disabled states, chevrons, inactive tab labels |

---

## Typography

System font stack: `-apple-system` / `SF Pro` on iOS. In React Native, omitting `fontFamily` in a StyleSheet uses the platform default (SF Pro on iOS) automatically — no font loading required.

| Role | Size | Weight | Color | Notes |
|------|------|--------|-------|-------|
| Large Title | 34px | 800 | `color.text` | Screen title in nav bar (e.g. "Pantry") |
| Title 2 | 22px | 700 | `color.text` | Section headings, sheet titles |
| Headline | 17px | 600 | `color.text` | List item primary text |
| Body | 17px | 400 | `color.text` | Body copy, descriptions |
| Subhead | 15px | 400 | `color.textSecondary` | List item secondary text (quantities, dates) |
| Caption | 12px | 400 | `color.textSecondary` | Timestamps, metadata |
| Section Label | 11px | 700 | `color.textSecondary` | Grouped list section headers — uppercase, +0.07em letter-spacing |

---

## Spacing

Base unit: `4px`. All spacing values are multiples.

| Token | Value | Usage |
|-------|-------|-------|
| `space.xs` | 4px | Inline gap between icon and badge |
| `space.sm` | 8px | Inner padding tight elements |
| `space.md` | 12px | Default horizontal padding within list items |
| `space.lg` | 16px | Screen edge margin, section label padding |
| `space.xl` | 24px | Between sections |
| `space.xxl` | 32px | Top-of-screen breathing room |

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `radius.sm` | 8px | Icon backgrounds, small badges |
| `radius.md` | 12px | List group cards, input fields |
| `radius.lg` | 16px | Bottom sheets, modal cards |
| `radius.pill` | 999px | Status badges, filter chips |

---

## Shadows / Elevation

Light, warm-tinted shadows. Never cold grey.

| Level | Style | Usage |
|-------|-------|-------|
| `shadow.card` | `0 1px 6px rgba(44,26,14,0.07)` | List group cards |
| `shadow.sheet` | `0 -2px 20px rgba(44,26,14,0.10)` | Bottom sheets, modals |
| `shadow.fab` | `0 4px 16px rgba(42,157,143,0.30)` | FAB button (teal glow) |

---

## Components

### Grouped List (core pattern)

iOS-style grouped sections. Each group is a white card (`color.card`) with `radius.md`, `shadow.card`, and `16px` horizontal margin. Items separated by a `0.5px color.border` divider. Section headers use the Section Label type style above the card.

```
Section Label (uppercase, muted)
┌─────────────────────────────┐  ← white card, radius 12, shadow
│ [icon]  Name        qty  ›  │  ← 11px padding vertical
│ [icon]  Name        qty  ›  │
└─────────────────────────────┘
```

### List Item Anatomy

- **Icon:** 32×32, `radius.sm`, background from food category colour (`color.primaryLight` for veg, `color.warningLight` for expiring, `#fef5df` for citrus/grain)
- **Primary text:** Headline weight
- **Secondary text:** Subhead weight, `color.textSecondary`
- **Badge:** Pill shape, right-aligned. Three states: warning (terracotta), success (green), neutral (none)
- **Chevron:** `›` in `color.textDisabled`, signals navigability

### Badges

```
Expiring:  background #fde8d0  text #c25000  e.g. "2d"  "Soon"
Good:      background #d4f0e8  text #1a6b4a  e.g. "OK"
```

### Buttons

| Variant | Background | Text | Border | Usage |
|---------|-----------|------|--------|-------|
| Primary | `color.primary` | `#fff` | none | Main CTA (Add Item, Confirm) |
| Secondary | `color.card` | `color.primary` | `1.5px color.primary` | Secondary actions |
| Destructive | `color.card` | `color.warning` | `1.5px color.warning` | Remove, delete |
| Ghost | transparent | `color.primary` | none | Inline text actions |

All buttons: `radius.md`, `14px` font, 600 weight, `12px` vertical padding.

### FAB (Floating Action Button)

Round, 56×56, `color.primary` background, white `+` icon, `shadow.fab`. Positioned `24px` from bottom-right, sits above tab bar.

### Search Bar

Full-width within screen, `color.surface` background, `radius.md`, `8px` vertical padding, `12px` horizontal. Magnifying glass icon in `color.textDisabled`. Placeholder text in `color.textDisabled`.

### Tab Bar

5 tabs: Pantry · Meals · Plan · Shop · Settings. Background `rgba(#fdfaf6, 0.95)` with backdrop blur. Top border `0.5px color.border`. Active tab: icon + label in `color.primary` + 4×4 dot indicator below label. Inactive: icon + label in `color.textDisabled`.

### Section Label

```
EXPIRING SOON
```
11px, 700 weight, uppercase, `+0.07em` letter-spacing, `color.textSecondary`. `16px` left, `6px` bottom margin before the card group.

---

## Screen Anatomy

```
┌──────────────────────────────┐
│  Status Bar                  │  background: color.background
│  Large Title    [Edit] [+]   │  nav bar actions: color.primary
│  N items · M expiring        │  subtitle: textSecondary
│  ┌──────────────────────┐    │
│  │ ⌕  Search…           │    │  color.surface
│  └──────────────────────┘    │
│  SECTION LABEL               │
│  ┌──────────────────────┐    │  color.card + shadow.card
│  │ item  ·  item  ·  …  │    │
│  └──────────────────────┘    │
│  SECTION LABEL               │
│  ┌──────────────────────┐    │
│  │ …                    │    │
│  └──────────────────────┘    │
│                         [+]  │  FAB
│──────────────────────────────│
│  Tab Bar                     │  color.background/95 + blur
└──────────────────────────────┘
```

---

## Icons

- **Food / ingredient icons:** Emoji (🥦 🥛 🍋 🥕). Displayed inside coloured icon backgrounds. No custom food icon set needed.
- **UI icons:** Expo's `@expo/vector-icons` — `Ionicons` set. Key icons: `add`, `search`, `chevron-forward`, `camera`, `checkmark`, `trash`.
- **Tab bar:** Emoji icons consistent with food/kitchen theme (🥬 🍽 📅 🛒 ⚙️).

---

## Motion

Follow iOS defaults. No custom animations in v1.

- **List transitions:** `LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut)` when items added/removed
- **Sheet presentation:** Standard iOS modal slide-up
- **Loading states:** `ActivityIndicator` in `color.primary`

---

## React Native Implementation Notes

Deliver as `mobile/src/theme/index.ts` — a single exported `theme` object:

```typescript
export const theme = {
  colors: { ... },   // all tokens above
  spacing: { ... },  // xs/sm/md/lg/xl/xxl
  radius: { ... },   // sm/md/lg/pill
  shadow: { ... },   // card/sheet/fab
  typography: { ... }, // fontSize + fontWeight per role
} as const;
```

All screens and components import from `@/theme` — no inline hex values in component files.
