# CLAUDE.md

This file provides guidance to Claude Code when working in the Glean mobile app.

## Preferred tools

- Use `rg` for fast text and file search
- Use `rtk` when reading large files, listing directories, or running noisy commands

## Commands

```bash
npm test                               # all tests (uses --experimental-vm-modules)
npm test -- --watch                    # watch mode
npm test -- tests/db/client.test.ts    # single file
npm run check                          # biome lint + tsc + knip (dead code)
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

Claude can drive the Android emulator via helper scripts in `mobile/scripts/`.
All scripts are auto-approved in `.claude/settings.json`.

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
├── sign-in.tsx              # Sign-in / sign-up screen
└── (tabs)/
    ├── _layout.tsx          # Tab bar (5 tabs + hidden sub-routes)
    ├── pantry/              # Pantry management (index, add, scan, describe, review, manual-entry)
    ├── meals/               # Recipe browsing (index, [id], search)
    ├── plan/                # Weekly meal plan (index)
    ├── shop/                # Shopping list (index)
    └── settings/            # User config + sign out (index)

src/
├── api/client.ts            # HTTP client with auth token injection + 401 refresh
├── auth/
│   ├── cognito.ts           # Cognito sign-in/up/refresh (lazy-init, dev bypass)
│   ├── storage.ts           # SecureStore token persistence (dev bypasses)
│   └── async-storage-shim.ts # In-memory shim for Cognito's AsyncStorage dep
├── db/
│   ├── client.ts            # expo-sqlite + Drizzle setup, migration runner
│   ├── schema.ts            # Drizzle table definitions (source of truth)
│   ├── seed.ts              # Seed data (ingredient categories)
│   ├── config.ts            # User config CRUD
│   ├── pantry.ts            # Pantry item queries
│   ├── recipes.ts           # Recipe + ingredient queries
│   ├── plan.ts              # Meal plan queries
│   └── shopping.ts          # Shopping list queries
├── screens/                 # Reusable screen components (SplashScreen)
├── components/              # Shared UI components
├── theme.ts                 # Design tokens (colors, spacing, typography)
└── types.ts                 # Shared TypeScript interfaces
```

### Key patterns

- **Dev auth bypass:** In `__DEV__` mode, `hasTokens()` returns true, `getUserSub()`
  returns `"dev-user-sub"`, and `signIn()` sets mock tokens without hitting Cognito.
- **SQL migrations:** Drizzle migrations in `drizzle/` are imported as inline strings
  via `babel-plugin-inline-import`. Metro needs `sourceExts: ["sql"]` and the babel
  plugin configured in `babel.config.js`.
- **AsyncStorage shim:** `amazon-cognito-identity-js` imports `@react-native-async-storage/async-storage`
  which can't be installed due to peer dep conflicts. Metro's `extraNodeModules` routes
  the import to an in-memory Map-based shim in `src/auth/async-storage-shim.ts`.
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
