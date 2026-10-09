Type: grilling
Status: open

## Question

Deferred from [ticket 14](14-ux-review-plan.md). Two related improvements to meal-plan generation, held out of the initial port:

1. **Surface the generation rationale.** The backend already returns `reason` and `missing_ingredients` per suggestion (`api/types.ts:101-102`) and the client throws both away (`plan/index.tsx:257-261`). Surfacing them makes the AI legible and warns the user what a plan will cost them at the shop. Decide how they're presented without making rows too dense (and note it may want streaming, since showing rationale increases perceived latency).
2. **Pre-flight guard.** Generation currently proceeds happily with `pantry: []` and `recipe_history: []` — with no saved recipes the model has nothing legitimate to return, yet the Generate button looks identical. Decide whether to block or warn when there are no saved recipes, the pantry is empty, or the device is offline.

Also in scope, and the cheapest piece: **`api/client.ts` sets no timeout at all on the LLM round-trip**, and generation feedback is only the button label changing to "Generating" (`plan/index.tsx:289-298`) — no spinner, and the button stays tappable. A client timeout plus a real progress indicator is basic robustness that could reasonably land earlier than the rest of this ticket.
