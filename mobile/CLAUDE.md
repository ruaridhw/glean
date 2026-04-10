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
# Start Expo on Android emulator (with SDK paths and fresh Metro cache)
ANDROID_HOME=$HOME/Library/Android/sdk \
  PATH=$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH \
  npx expo start --android --clear

# Clear Expo Go app data (resets SQLite DB and migrations)
$HOME/Library/Android/sdk/platform-tools/adb shell pm clear host.exp.exponent

# List running emulators
$HOME/Library/Android/sdk/platform-tools/adb devices
```

### Controlling the emulator non-interactively

Claude can drive the Android emulator via `adb` without user intervention.
Always use the full adb path: `$HOME/Library/Android/sdk/platform-tools/adb`.

```bash
ADB="$HOME/Library/Android/sdk/platform-tools/adb"

# Screenshot → view in Claude (multimodal)
$ADB exec-out screencap -p > /tmp/emu-screenshot.png
# Then use Read tool on /tmp/emu-screenshot.png to see the screen

# Tap at coordinates (x, y)
$ADB shell input tap 540 1200

# Type text (spaces must be %s)
$ADB shell input text "hello%sworld"

# Press keys
$ADB shell input keyevent KEYCODE_BACK
$ADB shell input keyevent KEYCODE_HOME
$ADB shell input keyevent KEYCODE_ENTER

# Swipe (x1, y1, x2, y2, duration_ms)
$ADB shell input swipe 540 1500 540 500 300

# Read recent logcat (Expo/React Native output)
$ADB logcat -d -t 50 '*:E'           # last 50 error lines
$ADB logcat -d -t 100 ReactNativeJS:* '*:S'  # last 100 JS console lines

# Get screen dimensions
$ADB shell wm size

# Check if an app is running
$ADB shell pidof host.exp.exponent
```

### Workflow: visual debugging

1. Take a screenshot with `adb exec-out screencap -p > /tmp/emu-screenshot.png`
2. Read it with the Read tool to see the current screen state
3. Tap/type/swipe to interact
4. Screenshot again to verify the result
5. Use logcat if something looks wrong

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
