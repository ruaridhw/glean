---
status: accepted
date: 2026-10-15
---

# Every LLM response is structured output

Every backend LLM call uses **structured output** (`with_structured_output` or the provider equivalent) against a typed schema — no exceptions for "simple" calls, and no parsing free text out of chat responses (#65/#142). The rule was set by annotation when the shopping parser gained structured output: it applies to *all* LLM responses, not just the parse endpoints.

## Considered options

- **Structured output only where parsing was painful.** Rejected: free-text answers keep creeping back (an integration test was still reading "pong" out of a raw chat call), and every free-text reader is a prompt-injection and drift surface.
- **Free text plus defensive parsing.** Rejected: it's the failure mode this decision removes.

## Consequences

- **A shared shopping-unit vocabulary** constrains parser output to units the app can actually reason about, which is what makes the parse cache (ADR 0010's decision caching, #66/#160) safe to share across items.
- **Integration tests** call the structured path like everything else.
- **Evals score typed fields**, not prose, which keeps the receipt and dietary eval suites deterministic to write.
