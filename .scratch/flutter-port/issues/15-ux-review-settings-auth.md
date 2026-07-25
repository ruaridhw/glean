Type: grilling
Status: resolved

## Question

Review the current Settings and Sign-in/Auth flow's user-facing behavior — `mobile/app/(tabs)/settings/index.tsx`, `mobile/app/sign-in.tsx`, `mobile/app/auth/callback.tsx` — and decide, screen by screen, whether the current UX makes sense or should change for the Flutter port. Don't assume 1:1 parity is the goal; if something is confusing or awkward today, surface it and grill the user until there's a shared answer for what it should do instead. Record the resolved behavior for each screen (kept as-is / changed, and how).

## Answer (partial — decided so far)

### Auth-bypass build hygiene — DECIDED
Verified: `.github/workflows/mobile-ci.yml:92-116` bakes `EXPO_PUBLIC_AUTH_BYPASS=true`, `EXPO_PUBLIC_APP_VARIANT=e2e`, and `EXPO_PUBLIC_API_URL=${{ secrets.PROD_API_URL }}` into a `gradlew assembleRelease` APK, uploaded as an artifact. `EXPO_PUBLIC_*` values are compile-time inlined into the bundle.

**Not exploitable as first feared**: every LLM-backed backend router applies auth at the router level — `recipes`, `shopping`, `meal_plan`, `receipts` all carry `dependencies=[Depends(verify_cognito_token)]`. That APK opens straight into the UI but cannot call any production AI endpoint (all 401). No data-breach or cost-abuse vector; only local-SQLite features work in it.

**Residual risks worth designing out**: the protection rests *entirely* on the backend (a future endpoint added without the router-level dependency would immediately be reachable by such a build), and nothing structurally prevents those vars being set on the EAS `production` profile.

**Decided**: in Flutter, the bypass lives behind a **separate entrypoint/flavour** (`main_e2e.dart`) so the bypass path **cannot compile into a production binary at all** — refining [ticket 07](07-decide-auth.md)'s `--dart-define` decision. Add a startup assertion that the bypass is unreachable when the API base URL is production.

### Bugs — must not reproduce
- **`saveUserConfig` failure is silently swallowed** (`settings/index.tsx:122-134`) — no try/catch, so a DB write failure shows the user *nothing*: no "Saved", no error.
- `auth/callback` is only registered while signed out (`_layout.tsx:52`), but `refresh()` flips `isAuthenticated` *before* `router.replace(...)` (`callback.tsx:82-83`) — the screen is unmounted from under its own navigation call.
- `promptAsync()`'s return value is dropped (`sign-in.tsx:40`); the flow depends entirely on the redirect arriving as a deep link. On iOS `ASWebAuthenticationSession` returns the redirect to `promptAsync` rather than emitting a `Linking` URL — **worth verifying on device**, since if it doesn't emit, iOS sign-in dead-ends silently.
- `handleSignOut` double-navigates (`settings/index.tsx:158-161`).
- `refreshTokens` writes a possibly-undefined access token unchecked (`google.ts:74-79`); a malformed 200 stores garbage while `hasTokens()` stays true.
- Slider `onValueChange` writes state every drag frame with no `onSlidingComplete` (`:234`, `:252`, `:274`) — continuous re-renders, likely jank.
- DB-init failure is caught and **ignored** (`_layout.tsx:82-86`) — the app proceeds into tabs with a possibly unusable DB.
- `getUserConfig` throws "Not authenticated" but Settings renders "Check your connection and try again" (`:191-192`) — misattributed cause.

### Still open
- **Is local data user-scoped or device-scoped?** Only `user_config` is keyed by user sub (`schema.ts:108-109`); `pantry_items`, `recipes`, `meal_plan_entries`, `shopping_list_items` have **no user column**. Signing in as a different account inherits the previous user's groceries while settings reset — a privacy issue.
- Does sign-out wipe the local DB, and is the user warned?
- Offline-first vs auth-gated: all data is local, yet the whole app sits behind a token check. Should a signed-out/expired user still read their pantry?
- What happens on token expiry mid-session? Today nothing signs out or routes to sign-in.
- Onboarding: there is **none**. A new user lands on an empty Pantry and never learns the pantry→meals→plan→shop loop or that Settings drives plan quality.
- Settings copy: nothing says these values steer meal-plan generation; the time field has no "minutes" unit and never states its 1–480 bound until violated.
- Save model: explicit "Save settings" vs auto-save. Today the StatsRow updates live so state *looks* saved, nothing marks the form dirty, and switching tabs discards edits silently.
- Terms/Privacy are plain text, not links (`sign-in.tsx:70-72`) — needed before store submission?
- Landing tab: always Pantry, or contextual?

### Data scoping and onboarding — DECIDED
See [cross-cutting decisions](_cross-cutting.md):
- **Local data is scoped to the user** — all user-data tables gain a user column, so account switching is correct and sign-out need not wipe the DB.
- **A short, skippable first-run setup** captures dinners/week, servings and dietary flags, then points at receipt-scan. Settings copy must also explain that these values steer meal-plan generation.

### Settings save model — DECIDED
**Auto-save**: drop the "Save settings" button and persist each control on change (debounced; on slider release, which also fixes the every-drag-frame re-render jank at `settings/index.tsx:234,252,274`). This removes the dirty-state trap entirely — today the StatsRow updates live so state *looks* saved, nothing marks the form dirty, and switching tabs discards edits silently. Also removes the title-only `Alert.alert("Saved")` that was inconsistent with the app's toast system.

### Session expiry — DECIDED
On token expiry, **keep local pantry/plan/shopping readable** and show a "signed out" banner that gates only the AI-backed features. All user data is local SQLite, so hard-booting the user out of readable data for a network-only concern is the wrong trade. Today nothing signs out or routes anywhere on expiry — `refreshTokens()` failure only throws `ApiError(401, "Session expired")` at the call site (`api/client.ts:29-32`).

This pairs with the user-scoped-data decision: since tables are keyed by user, a signed-out session still knows whose data to show.

### Recorded recommendations (not separately contested)
- **Terms of Service and Privacy Policy must become real tappable links** before store submission — they are plain text today (`sign-in.tsx:70-72`).
- **Landing tab stays Pantry** — predictable beats contextual, and the first-run setup now points new users at receipt-scan anyway.
- **Google-only sign-in stands** for the port; adding email/Apple later would reshape the single-button screen, but there's no reason to pre-build for it.
- **Surface DB-init failure** instead of ignoring it (`_layout.tsx:82-86` currently proceeds into the app with a possibly unusable database).
- Fix the misattributed Settings load error ("Check your connection" shown when `getUserConfig` threw "Not authenticated").

## Resolution
Resolved. No deferred items for this flow.
