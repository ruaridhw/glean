# AGENTS.md

This file provides guidance to agents when working in the Glean mobile app.
See `../AGENTS.md` for repo-wide Makefile targets and preferred tools.
`CLAUDE.md` is a compatibility symlink to this file.

## Commands

Prefer `make test-mobile` / `make lint-mobile` from the repo root. Use the commands
below for targeted runs within this directory:

```bash
npm test -- --watch                    # watch mode
npm test -- tests/db/client.test.ts    # single file
npx drizzle-kit generate              # regenerate migrations from schema.ts
```

## Android Emulator

`ANDROID_HOME` is not in the default shell PATH. All `adb` and `emulator` commands
need the SDK paths prepended. Use the helpers below.

### Environment setup

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"
```

### Common commands

```bash
# Kill Metro + clear app data
mobile/scripts/emu-kill

# Start Expo on Android emulator (SDK paths + fresh Metro cache)
mobile/scripts/emu-start

# Clear Expo Go app data only (resets SQLite DB and migrations)
mobile/scripts/emu-clear

# List running emulators
$HOME/Library/Android/sdk/platform-tools/adb devices
```

### Controlling the emulator non-interactively

Codex on macOS can drive the Android emulator via helper scripts in
`mobile/scripts/`. Other agents/platforms should adapt these commands to their
environment.

```bash
# Tap by visible text (uses uiautomator to find element bounds)
mobile/scripts/emu-tap "Discover"
mobile/scripts/emu-tap "Import from URL"

# Tap by coordinates (x, y)
mobile/scripts/emu-tap 540 1200

# Tap + wait + screenshot in one call (supports text or coordinates)
mobile/scripts/emu-tap-and-look "Discover"
mobile/scripts/emu-tap-and-look 540 1200

# Type text (spaces auto-escaped to %s)
mobile/scripts/emu-type hello world

# Press keys
mobile/scripts/emu-input keyevent KEYCODE_BACK
mobile/scripts/emu-input keyevent KEYCODE_ENTER

# Swipe (x1, y1, x2, y2, duration_ms)
mobile/scripts/emu-input swipe 540 1500 540 500 300

# Screenshot → then Read(mobile/.cache/emu-screenshot.png) to view
mobile/scripts/emu-screenshot

# Clear Expo Go app data (resets SQLite DB)
mobile/scripts/emu-clear
```

For commands not covered by a script, use the full adb path:

```bash
ADB="$HOME/Library/Android/sdk/platform-tools/adb"

# Read recent logcat (Expo/React Native output)
$ADB logcat -d -t 50 '*:E'           # last 50 error lines
$ADB logcat -d -t 100 ReactNativeJS:* '*:S'  # last 100 JS console lines

# Get screen dimensions
$ADB shell wm size

# Check if an app is running
$ADB shell pidof host.exp.exponent
```

### Workflow: visual debugging

1. `mobile/scripts/emu-screenshot` then `Read(mobile/.cache/emu-screenshot.png)` to see the screen
2. `mobile/scripts/emu-tap "Button Text"` or `emu-type ...` to interact
3. `mobile/scripts/emu-tap-and-look "Button Text"` to tap + screenshot in one step
4. Use logcat if something looks wrong

Prefer tapping by text over coordinates — it's resilient to layout changes and screen sizes.

## Architecture

Expo Router file-based routing with tabs layout. All app state lives on-device
in SQLite (Drizzle ORM + expo-sqlite). The backend is stateless — see `../backend/CLAUDE.md`.

### Module layout

```
app/
├── _layout.tsx              # Root layout: DB init, auth check, Stack navigator
├── index.tsx                # Redirect to /(tabs)
├── sign-in.tsx              # Sign-in / sign-up screen
└── (tabs)/
    ├── _layout.tsx          # Tab bar (5 tabs + hidden sub-routes)
    ├── pantry/              # Pantry management (index, add, scan, scan-progress, describe, review, manual-entry)
    ├── meals/               # Recipe browsing (index, [id], search, import)
    ├── plan/                # Weekly meal plan (index)
    ├── shop/                # Shopping list (index)
    └── settings/            # User config + sign out (index)

src/
├── api/
│   ├── client.ts            # HTTP client with auth token injection + 401 refresh
│   ├── hooks.ts             # TanStack Query hooks (useRecipeSearch, useScanReceipt, etc.)
│   └── types.ts             # API response types mirroring backend Pydantic schemas
├── auth/
│   ├── google.ts            # Google auth via expo-auth-session + Cognito Hosted UI
│   └── storage.ts           # SecureStore token persistence (__DEV__ + CI bypasses)
├── db/
│   ├── client.ts            # expo-sqlite + Drizzle setup, migration runner
│   ├── schema.ts            # Drizzle table definitions (source of truth)
│   ├── seed.ts              # Seed data (ingredient categories)
│   ├── config.ts            # User config CRUD
│   ├── ingredients.ts       # Ingredient lookup and upsert queries
│   ├── pantry.ts            # Pantry item queries
│   ├── recipes.ts           # Recipe + ingredient queries
│   ├── plan.ts              # Meal plan queries
│   └── shopping.ts          # Shopping list queries
├── normalization/
│   ├── units.ts             # Unit conversion table (volume, weight, countable)
│   └── index.ts             # normalizeUnit() and related helpers
├── suggestions/
│   └── compress.ts          # Pantry data compression for AI suggestion payloads (urgency scoring)
├── screens/                 # Reusable screen components (SplashScreen)
├── components/
│   ├── skeletons/           # Per-tab loading skeletons (Pantry, Meals, Plan, Shopping)
│   ├── ui/                  # Shared UI primitives (EmptyState, ErrorState, OfflineBanner, Toast)
│   └── PulsingDots.tsx      # Animated loading indicator
├── utils/
│   └── toast.ts             # Toast helper
├── theme/
│   └── index.ts             # Design tokens (colors, spacing, typography)
└── types/
    └── index.ts             # Shared TypeScript interfaces
```

### Key patterns

- **Dev auth bypass:** In `__DEV__` mode, `hasTokens()` returns true and `getUserSub()`
  returns `"dev-user-sub"`. No Cognito calls are made locally.
- **CI auth bypass:** When `EXPO_PUBLIC_CI_ACCESS_TOKEN` is set (CI builds only), tokens
  are read from build-time env vars instead of SecureStore. The user sub is decoded
  from the CI ID token. Production builds never have these env vars.
- **Google auth flow:** `expo-auth-session` opens Cognito's Hosted UI with PKCE. After
  the Google sign-in redirect, the auth code is exchanged for Cognito JWTs via
  `handleAuthCode()`. Token refresh uses Cognito's `/oauth2/token` endpoint directly.
- **SQL migrations:** Drizzle migrations in `drizzle/` are imported as inline strings
  via `babel-plugin-inline-import`. Metro needs `sourceExts: ["sql"]` and the babel
  plugin configured in `babel.config.js`.
- **Expo SDK 54:** Pinned to SDK 54 with `legacy-peer-deps=true` in `.npmrc` to avoid
  peer dep conflicts with react-dom/react-native-web that expo-router pulls in.

### Database schema

Source of truth is `src/db/schema.ts`. Migrations are generated with `npx drizzle-kit generate`.
After changing the schema, regenerate and commit the new migration + updated `drizzle/migrations.js`.

### Testing

```bash
npm test                                # all tests
npm test -- --testPathPattern=db        # tests matching "db"
npm test -- -t "getDb"                  # tests matching name "getDb"
```

Tests use `jest-expo` preset. Mocks for native modules (expo-sqlite, expo-secure-store)
are in `jest.setup.js` or inline `jest.mock()` calls.
