Type: grilling
Status: resolved

## Question

Surfaced while resolving [ticket 08](08-decide-component-architecture.md): the current app runs **two parallel, inconsistent state patterns**.

- **Local SQLite state** — 11 route files import `@/db/*` and call it imperatively. Four screens (`pantry/index.tsx`, `meals/index.tsx`, `plan/index.tsx`, `shop/index.tsx`) run a manual dance: `useFocusEffect` → `load()` → `setLoading(true)` → `setItems(...)` → and an explicit `await load()` after *every* mutation to refresh. No caching, no declarative invalidation.
- **Server state** — 5 screens use TanStack Query hooks from `@/api/hooks` (`useGenerateMealPlan`, `useDescribeReceipt`, `useParseShoppingDescription`, …), which do have caching and invalidation.

So the same app has declarative cached server state alongside hand-rolled imperative local state, with screens reaching directly into the DB layer.

Decide the Flutter data-layer architecture: whether local `drift` reads and remote API reads unify behind one provider/repository abstraction, whether screens may call the data layer directly or must go through providers, and how invalidation-after-mutation works (replacing the manual `load()` calls).

## Answer

### Enabling fact: there is no server-side user state

Backend routes are exhaustively: `GET /recipes/search`, `GET /recipes/{id}`, `POST /recipes/import-url`, `POST /meal-plan`, `POST /receipts/scan`, `POST /receipts/describe`, `POST /shopping/parse-description`, `GET /health`, and a dev-only `POST /dev/export-db`. No user pantry, plan, or shopping-list endpoints exist.

So: **local SQLite is the sole source of truth for user data; the backend is a stateless processing service plus a read-only recipe corpus.** There is nothing to sync and no offline-first reconciliation problem. Any repository-with-cache-reconciliation layer would be solving a problem this app does not have.

### Decision: two clearly-separated roles, no unifying repository

1. **Local `drift` reads → Riverpod `StreamProvider` over drift's `.watch()`.** The source of truth for every screen. Because drift streams re-emit whenever the underlying table changes, mutations require **no invalidation call at all** and there is no on-focus reload. The current `useFocusEffect` → `load()` → `setLoading` → refetch-after-every-mutation dance (in `pantry/index.tsx`, `meals/index.tsx`, `plan/index.tsx`, `shop/index.tsx`) **deletes itself rather than being ported** — mutations just write.
2. **Remote API → command providers** (`AsyncNotifier`/`FutureProvider`) returning *ephemeral proposals* that the user reviews on the review screens and then commits into drift. This matches what those endpoints actually are: transformations, not resources.

**Hard rule:** screens never import drift or the API client directly — always through providers. This is the fix for the present smell (11 route files reach into `@/db/*` imperatively).

### Correction to [ticket 06](06-decide-stack.md)

Ticket 06 recorded that a "thin custom query-caching layer" over Riverpod would be needed to replace TanStack Query. Given the above, it mostly **isn't**: only `/recipes/search` wants query-style caching (debounced search), which `FutureProvider.family` + `autoDispose` covers natively. Everything else is a one-shot command where caching isn't the point. TanStack Query was carrying loading/error-state ergonomics more than caching — that role belongs to Riverpod's `AsyncValue`.

### Input for [ticket 16](16-test-migration-strategy.md)

Tests asserting the manual reload/refetch behavior (loading-state toggles, on-focus refetch) test a mechanism that ceases to exist and should be **dropped**, not ported. Tests asserting *observable* outcomes (after deleting an item, it disappears from the list) remain valid and become widget tests over a `StreamProvider` with an in-memory drift database.
