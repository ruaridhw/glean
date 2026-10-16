# ruff: noqa: E501
"""Golden judge messages, captured once from the judges as they were before the prompt builders were extracted.

Source: `backend/tests/integration/evals/judges/rubrics.py` at the merge-base commit cf98f6f (the parent branch,
evals/01-receipt-photo-evals), run against a capturing chat model. Each case is the complete list of
(message type, content) the judge sent. They are data: nothing here is computed from the current prompt builders.
"""

LONG_HTML = "<html><body><p>Step 1: stir the pot gently for 1 minutes.</p><p>Step 2: stir the pot gently for 2 minutes.</p><p>Step 3: stir the pot gently for 3 minutes.</p><p>Step 4: stir the pot gently for 4 minutes.</p><p>Step 5: stir the pot gently for 5 minutes.</p><p>Step 6: stir the pot gently for 6 minutes.</p><p>Step 7: stir the pot gently for 7 minutes.</p><p>Step 8: stir the pot gently for 8 minutes.</p><p>Step 9: stir the pot gently for 9 minutes.</p><p>Step 10: stir the pot gently for 10 minutes.</p><p>Step 11: stir the pot gently for 11 minutes.</p><p>Step 12: stir the pot gently for 12 minutes.</p><p>Step 13: stir the pot gently for 13 minutes.</p><p>Step 14: stir the pot gently for 14 minutes.</p><p>Step 15: stir the pot gently for 15 minutes.</p><p>Step 16: stir the pot gently for 16 minutes.</p><p>Step 17: stir the pot gently for 17 minutes.</p><p>Step 18: stir the pot gently for 18 minutes.</p><p>Step 19: stir the pot gently for 19 minutes.</p><p>Step 20: stir the pot gently for 20 minutes.</p><p>Step 21: stir the pot gently for 21 minutes.</p><p>Step 22: stir the pot gently for 22 minutes.</p><p>Step 23: stir the pot gently for 23 minutes.</p><p>Step 24: stir the pot gently for 24 minutes.</p><p>Step 25: stir the pot gently for 25 minutes.</p><p>Step 26: stir the pot gently for 26 minutes.</p><p>Step 27: stir the pot gently for 27 minutes.</p><p>Step 28: stir the pot gently for 28 minutes.</p><p>Step 29: stir the pot gently for 29 minutes.</p><p>Step 30: stir the pot gently for 30 minutes.</p><p>Step 31: stir the pot gently for 31 minutes.</p><p>Step 32: stir the pot gently for 32 minutes.</p><p>Step 33: stir the pot gently for 33 minutes.</p><p>Step 34: stir the pot gently for 34 minutes.</p><p>Step 35: stir the pot gently for 35 minutes.</p><p>Step 36: stir the pot gently for 36 minutes.</p><p>Step 37: stir the pot gently for 37 minutes.</p><p>Step 38: stir the pot gently for 38 minutes.</p><p>Step 39: stir the pot gently for 39 minutes.</p><p>Step 40: stir the pot gently for 40 minutes.</p><p>Step 41: stir the pot gently for 41 minutes.</p><p>Step 42: stir the pot gently for 42 minutes.</p><p>Step 43: stir the pot gently for 43 minutes.</p><p>Step 44: stir the pot gently for 44 minutes.</p><p>Step 45: stir the pot gently for 45 minutes.</p><p>Step 46: stir the pot gently for 46 minutes.</p><p>Step 47: stir the pot gently for 47 minutes.</p><p>Step 48: stir the pot gently for 48 minutes.</p><p>Step 49: stir the pot gently for 49 minutes.</p><p>Step 50: stir the pot gently for 50 minutes.</p><p>Step 51: stir the pot gently for 51 minutes.</p><p>Step 52: stir the pot gently for 52 minutes.</p><p>Step 53: stir the pot gently for 53 minutes.</p><p>Step 54: stir the pot gently for 54 minutes.</p><p>Step 55: stir the pot gently for 55 minutes.</p><p>Step 56: stir the pot gently for 56 minutes.</p><p>Step 57: stir the pot gently for 57 minutes.</p><p>Step 58: stir the pot gently for 58 minutes.</p><p>Step 59: stir the pot gently for 59 minutes.</p></body></html>"
GOLDEN = {
    "receipt scan": [
        (
            "SystemMessage",
            "You are evaluating a grocery receipt normalisation system.\n"
            "Given a raw receipt line item name and the system's normalised output, rate the quality "
            "1-5:\n"
            "\n"
            "5 = Perfect canonical name, correct unit conversion, accurate price calculation\n"
            "4 = Minor issue (slightly verbose name, small rounding difference)\n"
            "3 = Acceptable but imprecise (name has extra words, unit roughly correct)\n"
            "2 = Significant error (wrong unit type, major quantity error)\n"
            "1 = Wrong (completely misidentified item)\n"
            "\n"
            "Return structured data with a single score field from 1 to 5.",
        ),
        (
            "HumanMessage",
            'Raw receipt item: "WHL MILK 2L"\nNormalised to: "whole milk", quantity=2000ml, unit_price=0.000675/ml',
        ),
    ],
    "receipt scan without a price": [
        (
            "SystemMessage",
            "You are evaluating a grocery receipt normalisation system.\n"
            "Given a raw receipt line item name and the system's normalised output, "
            "rate the quality 1-5:\n"
            "\n"
            "5 = Perfect canonical name, correct unit conversion, accurate price "
            "calculation\n"
            "4 = Minor issue (slightly verbose name, small rounding difference)\n"
            "3 = Acceptable but imprecise (name has extra words, unit roughly "
            "correct)\n"
            "2 = Significant error (wrong unit type, major quantity error)\n"
            "1 = Wrong (completely misidentified item)\n"
            "\n"
            "Return structured data with a single score field from 1 to 5.",
        ),
        (
            "HumanMessage",
            'Raw receipt item: "BNLS CHKN BRST 500G"\n'
            'Normalised to: "chicken breast", quantity=500g, unit_price=None/g',
        ),
    ],
    "meal plan": [
        (
            "SystemMessage",
            "You are evaluating a meal-plan generation system.\n"
            "Given a user's pantry state, dietary flags, and the generated meal-plan recipe, rate the "
            "quality 1-5:\n"
            "\n"
            "5 = Excellent — uses expiring/urgent pantry items, reason is specific and references actual "
            "pantry data\n"
            "4 = Good — reasonable recipe, reason references pantry items by name\n"
            '3 = Acceptable — valid recipe but reason is generic (e.g. "good for dinner")\n'
            "2 = Poor — ignores pantry priorities or reason is vague/irrelevant\n"
            "1 = Bad — violates dietary flags or completely irrelevant to pantry state\n"
            "\n"
            "Return structured data with a single score field from 1 to 5.",
        ),
        (
            "HumanMessage",
            "Pantry state:\n"
            "- rice: 800g (urgency: 10.0)\n"
            "- spinach: 100g (urgency: 80.0)\n"
            "\n"
            "Dietary flags: ['vegan', 'nut-free']\n"
            "\n"
            'Meal-plan recipe: "Spinach rice"\n'
            'Reason: "Uses the spinach that expires first"',
        ),
    ],
    "recipe import": [
        (
            "SystemMessage",
            "You are evaluating a recipe extraction system.\n"
            "Given source HTML and the system's extracted recipe JSON, rate the extraction quality "
            "1-5:\n"
            "\n"
            "5 = Perfect — all fields accurately captured from the HTML\n"
            "4 = Minor omission (missing optional field like cuisine or difficulty)\n"
            "3 = Mostly correct but missing some ingredients or instruction steps\n"
            "2 = Significant errors (wrong title, missing most ingredients)\n"
            "1 = Completely wrong extraction\n"
            "\n"
            "Return structured data with a single score field from 1 to 5.",
        ),
        (
            "HumanMessage",
            "Source HTML (first 2000 chars):\n"
            "<h1>Crème brûlée</h1>\n"
            "\n"
            "Extracted recipe:\n"
            "{\n"
            '  "title": "Cr\\u00e8me br\\u00fbl\\u00e9e",\n'
            '  "ingredients": [\n'
            '    "cream",\n'
            '    "sugar"\n'
            "  ],\n"
            '  "total_time": null\n'
            "}",
        ),
    ],
    "recipe import with long html": [
        (
            "SystemMessage",
            "You are evaluating a recipe extraction system.\n"
            "Given source HTML and the system's extracted recipe JSON, rate the "
            "extraction quality 1-5:\n"
            "\n"
            "5 = Perfect — all fields accurately captured from the HTML\n"
            "4 = Minor omission (missing optional field like cuisine or difficulty)\n"
            "3 = Mostly correct but missing some ingredients or instruction steps\n"
            "2 = Significant errors (wrong title, missing most ingredients)\n"
            "1 = Completely wrong extraction\n"
            "\n"
            "Return structured data with a single score field from 1 to 5.",
        ),
        (
            "HumanMessage",
            "Source HTML (first 2000 chars):\n"
            "<html><body><p>Step 1: stir the pot gently for 1 minutes.</p><p>Step 2: "
            "stir the pot gently for 2 minutes.</p><p>Step 3: stir the pot gently for "
            "3 minutes.</p><p>Step 4: stir the pot gently for 4 minutes.</p><p>Step "
            "5: stir the pot gently for 5 minutes.</p><p>Step 6: stir the pot gently "
            "for 6 minutes.</p><p>Step 7: stir the pot gently for 7 "
            "minutes.</p><p>Step 8: stir the pot gently for 8 minutes.</p><p>Step 9: "
            "stir the pot gently for 9 minutes.</p><p>Step 10: stir the pot gently "
            "for 10 minutes.</p><p>Step 11: stir the pot gently for 11 "
            "minutes.</p><p>Step 12: stir the pot gently for 12 minutes.</p><p>Step "
            "13: stir the pot gently for 13 minutes.</p><p>Step 14: stir the pot "
            "gently for 14 minutes.</p><p>Step 15: stir the pot gently for 15 "
            "minutes.</p><p>Step 16: stir the pot gently for 16 minutes.</p><p>Step "
            "17: stir the pot gently for 17 minutes.</p><p>Step 18: stir the pot "
            "gently for 18 minutes.</p><p>Step 19: stir the pot gently for 19 "
            "minutes.</p><p>Step 20: stir the pot gently for 20 minutes.</p><p>Step "
            "21: stir the pot gently for 21 minutes.</p><p>Step 22: stir the pot "
            "gently for 22 minutes.</p><p>Step 23: stir the pot gently for 23 "
            "minutes.</p><p>Step 24: stir the pot gently for 24 minutes.</p><p>Step "
            "25: stir the pot gently for 25 minutes.</p><p>Step 26: stir the pot "
            "gently for 26 minutes.</p><p>Step 27: stir the pot gently for 27 "
            "minutes.</p><p>Step 28: stir the pot gently for 28 minutes.</p><p>Step "
            "29: stir the pot gently for 29 minutes.</p><p>Step 30: stir the pot "
            "gently for 30 minutes.</p><p>Step 31: stir the pot gently for 31 "
            "minutes.</p><p>Step 32: stir the pot gently for 32 minutes.</p><p>Step "
            "33: stir the pot gently for 33 minutes.</p><p>Step 34: stir the pot "
            "gently for 34 minutes.</p><p>Step 35: stir the pot gently for 35 "
            "minutes.</p><p>Step 36: stir the pot gently for 36 minutes.</p><p>Step "
            "37: stir the pot gently for 37 minutes.</p><p>Step 38: stir the pot "
            "gently for 38 minutes.</p><p>Step 39: stir the pot gently for 39 "
            "minutes.</p><p>Step 40: stir \n"
            "\n"
            "Extracted recipe:\n"
            "{\n"
            '  "title": "Stew"\n'
            "}",
        ),
    ],
    "pantry description": [
        (
            "SystemMessage",
            "You are evaluating a grocery purchase description parser.\n"
            "Given a user's free-text grocery purchase and the system's parsed pantry items, "
            "rate the quality 1-5:\n"
            "\n"
            "5 = Excellent - all concrete purchased items are captured with sensible names, "
            "quantities, and units\n"
            "4 = Good - captures the important items with only minor quantity or naming issues\n"
            "3 = Acceptable - most items are present but at least one quantity or name is "
            "imprecise\n"
            "2 = Poor - misses important items or uses unsuitable units\n"
            "1 = Bad - mostly wrong or not useful for updating a pantry\n"
            "\n"
            "Return structured data with a single score field from 1 to 5.",
        ),
        (
            "HumanMessage",
            "Purchase description:\n"
            "2 eggs and some milk\n"
            "\n"
            "Parsed pantry items:\n"
            "[\n"
            "  {\n"
            '    "name": "eggs",\n'
            '    "quantity": 2.0,\n'
            '    "unit": "units"\n'
            "  },\n"
            "  {\n"
            '    "name": "milk",\n'
            '    "quantity": null\n'
            "  }\n"
            "]",
        ),
    ],
    "shopping-list description": [
        (
            "SystemMessage",
            "You are evaluating a grocery shopping list parser.\n"
            "Given a user's free-text shopping list and the system's structured shopping "
            "proposal, rate the quality 1-5:\n"
            "\n"
            "5 = Excellent - all requested items are captured with practical shopping "
            "names, quantities, units, and categories\n"
            "4 = Good - captures the important items with minor naming, category, or "
            "quantity issues\n"
            "3 = Acceptable - most items are present but vague or incomplete\n"
            "2 = Poor - misses important items or invents items not implied by the "
            "request\n"
            "1 = Bad - mostly wrong or not useful for building a shopping list\n"
            "\n"
            "Return structured data with a single score field from 1 to 5.",
        ),
        (
            "HumanMessage",
            "Shopping list description:\n"
            "taco shells, limes\n"
            "\n"
            "Parsed shopping proposal:\n"
            "{\n"
            '  "items": [\n'
            "    {\n"
            '      "name": "taco shells"\n'
            "    }\n"
            "  ],\n"
            '  "clarifying_questions": []\n'
            "}",
        ),
    ],
}
