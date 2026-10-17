---
status: accepted
date: 2026-10-15
---

# Classification decisions are made by a pinned decision model, not by regex or free-text LLM calls

Wherever the backend needs a *decision* — is this recipe nut-free, does this raw name match this catalogue item — it asks a **pinned decision model** (TypeSafe Jev, currently `typesafe/jev-1.14` via OpenRouter) through one thin, vendor-neutral **DecisionClient** (#135/#141). The dietary keyword regexes that predated it were **removed entirely** once the decision model was shown to cover every case (#159/#161); the owner prefers tuning the decision model over maintaining hand-written rules.

Three disciplines surround the client, all agreed up front: the **model version is pinned** so behaviour only changes deliberately; **every decision is cached in backend storage**, keyed by what was asked, so repeat questions are free and consistent; and **every decision is logged** to LangSmith, which already traces all LLM calls. Naming of new items is **synchronous in the same request** (a cheap model such as flash-lite), not a background job — the earlier self-invoking-Lambda design was dropped as circular, and an "unresolved" marker is never persisted.

## Considered options

- **Keep the regexes as a fast path.** Rejected: two mechanisms drift apart, and the regexes were already wrong on real recipes (curry pastes, hyphenated forms). One mechanism, tuned, is simpler to reason about and to eval.
- **An async naming pipeline with pending markers.** Rejected: the Lambda only serves web requests, self-invocation was circular, and the pending/expiry machinery was complexity without a user benefit.
- **Keeping the decision cache inside a generic "normalisation service".** Rejected: the cache belongs to backend storage, so the service stays reusable and stateless.

## Consequences

- **Tuning is evidence-based.** Decision thresholds are set from runs over the whole 632-recipe corpus against labelled ground truth, not from spot checks, and a judge study (#124/#170) measures the decision model against the LLM judges.
- **Any feature that needs a judgement call is a candidate for the decision model** — category pre-fill, ingredient-to-pantry matching, unit words, dish-versus-list — rather than new heuristics.
- **Prompt or criteria changes invalidate cached decisions** for that question; caches key on the criteria, not just the subject.
