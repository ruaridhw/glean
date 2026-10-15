Type: grilling
Status: open

## Question

Deferred from [ticket 11](11-ux-review-pantry.md). Once expiry dates are inferred automatically, add a path for the user to **set or correct** an expiry date — inferred shelf life will sometimes be wrong, and today there is no edit path at all (`addPantryItem` in `db/pantry.ts:75-95` doesn't even accept an expiry).

Needs: where the edit lives (the Review screen during intake, an edit sheet on the pantry row, or both), whether it's optional per item, and how a user-set date is distinguished from an inferred one in the UI.
