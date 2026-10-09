Type: grilling
Status: resolved
Blocked by: 01

## Question

Given the research in ticket 01 (`.scratch/flutter-port/research/state-routing-persistence.md`), decide and lock: the Flutter routing library, the state-management approach, and the local-persistence library. This is the foundational stack decision the rest of the spec builds on — grill the user rather than picking unilaterally, since these are genuine value trade-offs (e.g. compile-time safety vs boilerplate, learning curve) not purely technical facts.

## Answer

Locked, following ticket 01's research lean:

- **Routing**: `go_router` — official, `StatefulShellRoute.indexedStack` maps cleanly onto the current per-tab navigation stacks.
- **State management**: Riverpod — the only option with cache/invalidate primitives analogous to TanStack Query, accepting that a thin custom query-caching layer on top is needed (no mature off-the-shelf equivalent).
  - **Corrected by [ticket 20](20-decide-data-layer-architecture.md)**: that custom query-caching layer is mostly unnecessary. There is no server-side user state, so only `/recipes/search` wants query-style caching (`FutureProvider.family` + `autoDispose` covers it); local reads use drift `.watch()` streams instead. Riverpod stays the pick — the extra layer doesn't.
- **Local persistence**: `drift` — best-maintained, SQL-like typed queries closest to the current Drizzle experience. `isar` ruled out (maintenance stalled), `objectbox`/`sqflite` passed over (bigger paradigm shift / no ORM, respectively).
