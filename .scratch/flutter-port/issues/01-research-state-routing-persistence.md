Type: research
Status: resolved

## Question

Research the current (2026) Flutter ecosystem landscape for the three layers this app needs to replace, and write a sourced comparison — not a final pick, that's ticket 06's job:

- **Routing**: `go_router` vs `auto_route` vs raw Navigator 2.0/Router API. Compare nested tab+stack support (the current app has a tab layout with per-tab stacks: meals, pantry, plan, shop, settings), deep-linking, type-safe route params, and maintenance/adoption status.
- **State management**: Riverpod vs Bloc/Cubit vs Provider vs plain `InheritedWidget`+`ChangeNotifier`. The current app pairs local component state with TanStack Query for server-state caching/invalidation against a REST backend — look specifically for what each option's answer to "TanStack-Query-equivalent" caching is (e.g. Riverpod's `AsyncNotifier`/`riverpod_query`-style packages).
- **Local persistence**: `drift` vs `sqflite` vs `isar` vs `objectbox`. The current app uses Drizzle ORM over `expo-sqlite` as a real local data store (pantry items, meal plans, shopping lists — not just a cache), with schema migrations. No compatibility constraint with the old schema is needed (greenfield, no data migration planned). Compare schema-migration ergonomics, type-safety, and query API shape.

Write findings to `.scratch/flutter-port/research/state-routing-persistence.md`, citing official docs / pub.dev / repo activity for each claim.

## Answer

**Routing** — `go_router` is the Flutter-team-published, officially recommended option; its `StatefulShellRoute.indexedStack` gives independent per-tab navigator stacks that map almost directly onto Glean's tab layout (meals/pantry/plan/shop/settings), and it has far higher adoption than `auto_route` (3.52M vs 354k weekly downloads). `auto_route` offers comparably purpose-built tab abstractions (`AutoTabsRouter`) with stronger default codegen type-safety but smaller adoption and more open issues. Raw Navigator 2.0 would mean hand-building what both packages provide for free — not recommended.

**State management** — Riverpod is the only option with first-party primitives (`family`, `autoDispose`, `ref.invalidate`, `AsyncNotifier`) that map onto TanStack Query's cache/stale/invalidate model, though spread across composable modifiers rather than one unified query API (the closer TanStack-style analog, `fquery`, is small and largely unproven). Bloc/Cubit has the most stars and Flutter-Favorite status but no built-in query-cache concept. Provider is simplest but has no async-cache tooling at all — notably, Provider's own author built Riverpod specifically to fill that gap.

**Local persistence** — `drift` is the most actively maintained (recent releases, Flutter Favorite), with the strongest migration tooling and a SQL-like typed-query API closest to the current Drizzle experience. Isar's maintenance is stalled (last stable release ~3 years old, last commit over a year stale; `isar_community` is only a narrow bugfix fork, not a real forward path). ObjectBox remains actively maintained and fast but is NoSQL-shaped with more manual migrations. `sqflite` is a solid low-level SQLite binding with no ORM/type-safety of its own.

Full findings + citations: `.scratch/flutter-port/research/state-routing-persistence.md` on branch `worktree-agent-a3421c2f939480699` (worktree `/home/ruaridh/glean/.claude/worktrees/agent-a3421c2f939480699`, commit `b8770c8`) — not yet merged into `flutter-port`.
