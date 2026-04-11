---
name: idea
description: >
  Use when the user says "idea", "new issue", "track this", "file an issue",
  "create a ticket", or wants to quickly capture a feature idea as a GitHub issue.
---

# Idea → GitHub Issue

Quickly turn a natural language idea into a well-structured GitHub issue.

## Process

1. **Get the idea** — use `$ARGUMENTS` if provided, otherwise ask the user.
2. **Expand** into issue structure (see below).
3. **Confirm** — present the draft and let the user adjust before creating. Use AskUserQuestion for labels/priority if ambiguous.
4. **Create** via `gh issue create`.
5. **Add to project board** and optionally set Priority field.
6. **Report** the issue URL.

## Issue structure

From the idea, generate:

- **Title** — short, imperative (under 70 chars)
- **Description** — what the feature is and why it matters to the user
- **Acceptance criteria** — user-facing outcomes only (what the user sees, feels, or can do). No component names, library choices, or architecture details.
- **Technical approach** *(subject to change)* — implementation specifics: libraries, component names, files to modify, architecture decisions. These may evolve during development. Use codebase knowledge to suggest concrete starting points.
- **Labels** — `enhancement` + `mobile` or `backend` (or both)
- **Priority** *(optional)* — P0 (now), P1 (next), or P2 (later). Skip if the user doesn't specify.

### Issue body template

```markdown
## Description
{what and why — user impact}

## Acceptance criteria
- [ ] {user-facing outcome}

### Technical approach (subject to change)
- [ ] {library, component, file, or architecture detail}

## Dependencies
{#issue numbers, or omit section}
```

## Quick reference

```bash
# Create issue (derive repo from git remote)
gh issue create --title "Title" --label "enhancement,mobile" --body "..."

# Add to project board (use gh project list to find project number and owner)
gh project item-add <PROJECT_NUMBER> --owner <OWNER> --url <issue_url>

# Set priority (look up field ID and option IDs via gh project field-list)
gh project item-edit --project-id "$PROJECT_ID" --id "$ITEM_ID" \
  --field-id "<PRIORITY_FIELD_ID>" \
  --single-select-option-id "<OPTION_ID>"
```

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Acceptance criteria names components/libraries | Rewrite as user-visible behaviour |
| Mixing "uses AsyncStorage" into acceptance | Move to Technical approach section |
| Skipping user confirmation | Always present draft before `gh issue create` |
