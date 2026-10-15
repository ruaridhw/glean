---
status: accepted
date: 2026-10-15
---

# The catalogue is backend-owned reference data; household data stays on the phone

Glean is local-first: the pantry, plan and shopping list live only on the phone, and the backend has been stateless. We're nonetheless making the **catalogue** (every catalogue item, its ingredient group, aliases and rules) shared reference data that the backend owns, in DynamoDB. Each device syncs a copy. Without one source of truth, an item's rules end up fixed by whichever unit or category the phone happens to see first: that's what stores spices as millilitres, and what makes planning abort on grams versus teaspoons. The 23-category taxonomy was also copied by hand between the app and the backend prompts.

## Considered options

- **Seed the catalogue on the phone only.** It keeps the backend stateless. But the backend's parse and normalisation prompts need the same data, so the copying would remain, and nothing an agent learns about a new item would reach the next device or reinstall.
- **S3 objects.** Rejected: the catalogue takes many small concurrent writes from normalisation, which suits DynamoDB.

## Consequences

- **Household overrides stay on the phone,** in their own table, layered over the synced catalogue by stable item id. A catalogue update never erases them. Renamed or merged items keep their old ids as aliases, so overrides follow them.
- **The catalogue includes household items** (toilet roll, shampoo), not just ingredients, because they go on the same shopping list and need a store section.
- **DynamoDB must stay inside the AWS free tier:** provisioned capacity, Standard table class, at most 25 RCU and 25 WCU summed across every table and index in the region, no global tables, point-in-time recovery off, and a budget alert on any charge.
