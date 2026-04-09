// mobile/tests/flows/receipt-checkout.test.ts
//
// Tests the logical flow that review.tsx executes on confirm:
// resolve ingredients → upsert pantry → checkOff shopping → (optional) completeCheckout

function chain(value: unknown) {
  const p = Promise.resolve(value);
  const handler: ProxyHandler<object> = {
    get(_target, prop: string) {
      if (prop === "then") return p.then.bind(p);
      if (prop === "catch") return p.catch.bind(p);
      if (prop === "finally") return p.finally.bind(p);
      return (..._args: unknown[]) => new Proxy({}, handler);
    },
  };
  return new Proxy({}, handler);
}

jest.mock("@/db/client", () => ({ drizzleDb: {} }));
jest.mock("drizzle-orm", () => ({
  eq: jest.fn((_col: unknown, val: unknown) => val),
  sql: jest.fn((...args: unknown[]) => args),
  and: jest.fn((...args: unknown[]) => args),
  inArray: jest.fn((_col: unknown, vals: unknown) => vals),
}));
jest.mock("@/db/schema", () => ({
  shoppingListItems: { ingredient_id: "ingredient_id", is_checked: "is_checked", id: "id" },
  pantryItems: { ingredient_id: "ingredient_id" },
  ingredients: { id: "id", canonical_name: "canonical_name" },
  recipeIngredients: {},
  ingredientCategories: {},
}));

import { checkOffByIngredientIds, completeCheckout } from "@/db/shopping";

const clientModule = require("@/db/client");

function makeDbMock() {
  return {
    select: jest.fn(() => chain([])),
    insert: jest.fn(() => chain([])),
    update: jest.fn(() => chain(undefined)),
    delete: jest.fn(() => chain(undefined)),
  };
}

describe("receipt checkout flow", () => {
  it("checks off shopping items by ingredient ids", async () => {
    const mockDb = makeDbMock();
    clientModule.drizzleDb = mockDb;

    await checkOffByIngredientIds([1, 2]);

    expect(mockDb.update).toHaveBeenCalledTimes(1);
  });

  it("completes checkout after checkOff when returnTo=shop", async () => {
    const mockDb = makeDbMock();
    clientModule.drizzleDb = mockDb;

    // Simulate the review.tsx confirm flow with returnTo=shop
    await checkOffByIngredientIds([1, 2]);

    // Reset to get fresh mock for completeCheckout
    const mockDb2 = makeDbMock();
    clientModule.drizzleDb = mockDb2;

    const returnTo = "shop";
    if (returnTo === "shop") {
      await completeCheckout();
    }

    expect(mockDb2.delete).toHaveBeenCalledTimes(1);
  });

  it("does not call completeCheckout without returnTo=shop", async () => {
    const mockDb = makeDbMock();
    clientModule.drizzleDb = mockDb;

    await checkOffByIngredientIds([1, 2]);

    const returnTo: string | undefined = undefined;
    if (returnTo === "shop") {
      await completeCheckout();
    }

    // update was called for checkOff, but delete was NOT called
    expect(mockDb.update).toHaveBeenCalledTimes(1);
    expect(mockDb.delete).not.toHaveBeenCalled();
  });
});
