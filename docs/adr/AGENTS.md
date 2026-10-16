# ADR practices

How we write and maintain Architecture Decision Records in this folder.

## What an ADR is here

- **A living record of the *current* decision,** not an append-only log. When a
  decision evolves, update the ADR in place so it always describes what holds
  today; git history preserves what it used to say. If a decision is replaced
  wholesale by an unrelated one, mark the old record `status: superseded` in
  its frontmatter and point at the replacement.
- **One decision per record.** Small and focused beats comprehensive; most
  ADRs here are 1–2 KB.
- **Decisions, not features.** A bug fix, a UI tweak or a shipped feature isn't
  an ADR. A choice between durable alternatives — where the "why" and the
  rejected options would otherwise be lost — is.

## Format

- Frontmatter: `status` (`accepted`/`superseded`) and `date` — the date **the
  decision was made**, which may predate the file.
- Title: a full-sentence statement of the decision ("The pantry tracks most
  cupboard goods by presence, not quantity"), not a label.
- Body: the decision and its motivation in plain English. Then, where useful,
  **## Considered options** (each rejected alternative *with its reason*) and
  **## Consequences** (bullets with a bold lead-in).
- Cite the evidence: PRs, issues, Inbox answers, annotated plans. An ADR mined
  from history should say where the decision lives.

## Workflow

- **An ADR rides the last PR of the stack it relates to.** If everything it
  documents is already merged, it goes in a standalone docs PR off `main`.
- **Numbers are the next free 4-digit sequence, unique across in-flight
  branches.** Check open PRs touching this folder before picking one.

## Content rules

- **No internal machine or homelab names** in committed content — refer to
  "the home server", "the Mac", etc.
- **No recipe-source brand names.** Say "the source's app" or "the retailer",
  never the brand.
- Plain-English names for domain concepts; define jargon where it's first used.
