# Glean Polish & UX Roadmap — Design Spec

**Goal:** Polish the Glean app to a level where first-time users feel it's a real, complete product they'd keep using. Organised into Now/Next/Later for a GitHub Project board.

**Primary lens:** User retention — the first impression must feel polished.

**Design decisions:**
- Native `Alert.alert()` stays for destructive confirmations (delete, checkout). Toasts handle success/info feedback.
- `react-native-toast-message` for the toast system — drop-in, themeable, no native dependency.
- `react-native-reanimated` for animations — already compatible with Expo, pairs with gesture handler for Next swipe work.
- Local-only DB is a deliberate architectural choice. No multi-user/sync features planned.

---

## NOW — Ship-readiness polish (6 items)

### 1. Skeleton loading screens
Replace `ActivityIndicator` spinners with shimmer/skeleton placeholders on all list screens: Pantry, Meals (saved + discover tabs), Plan grid, Shopping list. Use a single reusable `Skeleton` component that accepts layout props (lines, circles, rectangles) to match each screen's content shape.

### 2. Error states with retry
When API calls fail (scan, search, suggestions), show a friendly error view with an icon, short message, and "Try again" button. Add a network-offline banner (persistent, dismisses on reconnect) using `@react-native-community/netinfo`. Errors for local DB operations can remain console-level — they indicate bugs, not user-facing issues.

### 3. Empty states with guidance
Each screen gets a dedicated empty state that guides toward the primary action:
- **Pantry:** "Your pantry is empty. Scan a receipt or describe what you have to get started." → CTA buttons for scan and describe.
- **Meals:** "No recipes yet. Discover recipes or import one from a URL." → CTA for search.
- **Plan:** "No meals planned this week. Add recipes to your plan or let AI suggest a week." → CTA for generate.
- **Shop:** "Your shopping list is empty. Plan some meals and we'll figure out what you need." → CTA linking to Plan tab.

Each empty state should include a simple illustration or icon to feel less barren.

### 4. Screen & list animations
- **List items:** `LayoutAnimation` or `reanimated` entering/exiting animations when items are added, removed, or checked off in Pantry, Shopping list.
- **Screen transitions:** Smooth push/pop transitions between screens (Expo Router defaults are fine, but ensure modal presentations animate correctly).
- **Recipe list → detail:** Shared element transition on the recipe image/title if feasible with Expo Router; otherwise a clean slide-up.
- **Check-off:** Satisfying strikethrough + fade animation when toggling shopping list items.

### 5. Toast system
Install `react-native-toast-message`. Configure a custom toast component themed with design system tokens (colours, fonts, radii from `@/theme`). Show toasts for:
- "Added to pantry" (after review/confirm)
- "Recipe saved" (after import/search save)
- "Meal planned" (after assigning recipe to slot)
- "Checkout complete" (after shopping checkout)
- "Item deleted" (after swipe-to-delete, with undo action if feasible)

Mount the `<Toast />` component in the root layout. Keep native Alerts for destructive confirmations (delete ingredient, clear plan, etc.).

### 6. Scan progress experience
Replace the ActivityIndicator during receipt scan with a multi-step progress screen:
- Pulsing receipt/camera icon at the top
- Step indicators: "Uploading image" → "Reading receipt" → "Extracting items"
- Steps advance based on actual API progress if possible, or timed estimates if not (upload ~1s, OCR ~2-3s, extraction ~1s)
- On completion, auto-navigate to the review screen

This makes the 2-5 second wait feel intentional rather than broken.

---

## NEXT — Quality & depth (9 items)

### 7. Onboarding flow
3-screen swipeable walkthrough on first launch:
1. **Scan** — "Snap a photo of your receipt and we'll stock your pantry"
2. **Plan** — "Plan your week's meals with AI suggestions"
3. **Shop** — "We'll build your shopping list from what you're missing"

After the walkthrough, a **"Describe your pantry"** interactive step:
- Text input field with microphone button for speech-to-text (`expo-speech` or native dictation)
- Prompt: "What do you have at home? Just describe it naturally — 'eggs, milk, some chicken in the freezer, half a bag of rice'"
- Submits to the existing `/receipts/describe` endpoint to parse and bootstrap the pantry
- "Skip" option for users who want to start from scratch

Shown once, gated by AsyncStorage flag.

### 8. Haptic feedback
`expo-haptics` for tactile feedback:
- `ImpactFeedbackStyle.Light` on shopping list check-off toggle
- `ImpactFeedbackStyle.Medium` on camera shutter press
- `NotificationFeedbackType.Success` on checkout complete
- `NotificationFeedbackType.Warning` on delete confirmation

### 9. Pull-to-refresh
`RefreshControl` on Pantry list, Meals list, Shopping list. Triggers a re-query from the local SQLite database (and any pending API sync if applicable). Themed spinner colour from design tokens.

### 10. Keyboard handling
- `KeyboardAvoidingView` wrapping all input screens (manual entry, describe, search, settings)
- Dismiss keyboard on scroll via `keyboardDismissMode="on-drag"` on ScrollViews/FlatLists
- Auto-focus the primary text input on screen mount where appropriate (search, manual entry, describe)

### 11. Swipe gestures
`react-native-gesture-handler` + `reanimated` (builds on Now animation work):
- Swipe-left-to-delete on pantry items and shopping list items
- Red "Delete" background revealed on swipe
- Integrates with haptic feedback (#8) and toast undo (#5)

### 12. Search improvements
- Debounced input (300ms) to avoid excessive API calls
- Recent searches stored in AsyncStorage, shown as chips below the search bar
- "No results" empty state with suggestions ("Try a different spelling" or "Import from URL instead")

### 13. Quantity stepper
Replace the raw `TextInput` for pantry quantity editing with a +/- stepper component:
- Tap +/- to increment/decrement by the item's base unit
- Long-press for fast increment
- Still allows direct text input on tap of the number
- Respects unit type (whole numbers for "items", decimals for kg/ml)

### 14. Expiry warnings
Visual badges on pantry list items:
- **Amber** — expires within 3 days
- **Red** — expired
- Sort option to surface expiring items first
- Threshold configurable in Settings (default 3 days)

### 15. Expiry reminders (local notifications)
`expo-notifications` scheduled locally:
- When a pantry item has an expiry date, schedule a local notification N days before (configurable in Settings, default 1 day)
- Notification text: "{item} expires tomorrow" / "{item} expires in 3 days"
- Tapping notification opens the Pantry tab
- Reschedule/cancel when item is consumed or deleted

---

## LATER — Depth & platform (7 items)

### 16. Accessibility audit
- `accessibilityLabel` on all `Pressable`/`TouchableOpacity` elements
- `accessibilityRole` on buttons, links, headers
- Contrast ratio verification against theme tokens (WCAG AA minimum)
- VoiceOver / TalkBack testing pass
- Ensure all custom components (stepper, swipe actions) are screen-reader navigable

### 17. Image caching
Switch recipe images to `expo-image` (or `Image` with `cachePolicy`). Built-in disk cache means images render instantly on revisit and work offline.

### 18. Offline resilience
- `@tanstack/react-query` `onlineMutationManager` to queue mutations (scan, suggestions) when offline
- Visual indicator when offline (grey banner from #2, plus disabled state on API-dependent buttons)
- Auto-sync queued mutations on reconnect

### 19. Dark mode
- Extend `@/theme` with a `dark` palette alongside the existing light tokens
- `useColorScheme()` to respect system preference
- User override toggle in Settings (Light / Dark / System), persisted in AsyncStorage
- All screens already import from `@/theme`, so the migration is mostly token swaps

### 20. Widget / quick actions
- iOS home screen widget via `expo-widgets` showing today's planned meals
- 3D Touch / long-press quick actions: "Scan receipt", "Open shopping list"

### 21. Push notifications (general)
- Meal prep reminders ("Start cooking in 30 minutes" based on recipe prep time + planned meal time)
- Weekly plan reminder ("Plan your meals for the week" on Sunday morning)
- Requires a notification preferences screen in Settings

### 22. App Store polish
- App Store screenshots generated from real app state
- Store description and keywords
- App icon variants (light/dark if dark mode is done)
- Animated splash screen replacing the static one

### 23. Real-time scan progress
Replace timed frontend estimates with actual backend progress reporting. Architecture: split `/receipts/scan` into async job submission (`POST /receipts/scan` returns `{job_id}`) + status polling (`GET /receipts/scan/{job_id}`). Requires: DynamoDB table for job state with TTL auto-cleanup, SAM template additions (DynamoDB resource + IAM), Lambda function updated to write status transitions (uploading → ocr → extracting → done).
