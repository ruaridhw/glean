# AI Workflow Production Smoke

Use this runbook after backend evals pass and a production build is installed on the device.

## Preflight

- Confirm the installed app is pointed at the production API.
- Confirm the signed-in app profile is the real profile being smoke-tested.
- Open LangSmith project `glean`.
- Identify the production Lambda function name from the `glean-api-prod` CloudFormation stack output or Lambda console.
- Start the AWS log watcher from `backend/`:

```bash
uv run python scripts/ai_workflow_smoke_watch.py \
  --function-name <prod-lambda-function-name> \
  --region eu-west-2
```

Add `--run-aws` after the app actions to fail the command when CloudWatch contains error-like events in the smoke window.

## App Actions

Run these from the installed app in order and record the timestamp for each action.

| Flow | App action | Expected LangSmith feature tag | App-visible pass condition |
| --- | --- | --- | --- |
| Receipt scan | Scan a real grocery receipt into pantry review | `receipt-scan` | Parsed items appear with quantities, units, and confidence suitable for review |
| Pantry purchase description | Describe a recent grocery purchase | `pantry-purchase-description` | Parsed pantry items appear for review |
| Meal plan generation | Generate a meal plan from the Plan tab | `meal-plan-generation` | Candidate meals are added or shown without exceeding the requested meal slots |
| Shopping-list description | Describe items to add to the shopping list | `shopping-list-description` | Shopping proposals appear with practical quantities and units |
| Recipe search | Search for `carbonara` or another known recipe term | None expected | Search results are returned and recipe detail opens |
| Recipe URL import | Import a known structured recipe URL | No LLM trace expected when structured data is present | Recipe detail is populated with title, ingredients, and instructions |
| Recipe URL fallback | Import a URL that lacks structured recipe data, if available | `recipe-import` | Recipe detail is populated by the LLM fallback |

## Evidence To Capture

- LangSmith project `glean` shows one trace for each expected feature tag in the action window.
- AWS CloudWatch for the production Lambda has no `ERROR`, `Exception`, or `Traceback` events in the smoke window.
- The app shows successful results for each flow.
- For recipe URL import, note whether the path was structured/no-LLM or fallback/LLM.

## Cleanup

Because this smoke pass uses the real profile, clean up the test data before finishing:

- Remove pantry items created by receipt scan and purchase description.
- Remove generated meal plan entries.
- Remove shopping-list items created by the shopping description.
- Remove imported test recipes that should not remain saved.

## Optional Live Backend Commands

These run backend HTTP/provider smoke tests without the installed app. They are useful before the manual app pass:

```bash
uv run pytest tests/integration/test_ai_workflow_live_smoke.py -v --no-cov
```

Set optional inputs for full coverage:

```bash
export GLEAN_VISION_RECEIPT_IMAGE=/absolute/path/to/receipt.jpg
export GLEAN_LIVE_RECIPE_URL=https://example.com/known-recipe-page
uv run pytest tests/integration/test_ai_workflow_live_smoke.py -v --no-cov
```
