// mobile/tests/db/shopping.test.ts

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

import { addShoppingGapsForRecipe } from "@/db/shopping";

const clientModule = require("@/db/client");

function makeDbMock(selectQueue: unknown[]) {
  let si = 0;
  return {
    select: jest.fn(() => chain(selectQueue[si++] ?? [])),
    insert: jest.fn(() => chain([])),
    update: jest.fn(() => chain(undefined)),
    delete: jest.fn(() => chain(undefined)),
  };
}

describe("addShoppingGapsForRecipe", () => {
  it("adds a shortfall item when pantry has less than needed", async () => {
    const mockDb = makeDbMock([
      // recipe ingredients (400g needed for 1 serving)
      [{ ingredient_id: 1, canonical_name: "chicken breast", quantity: 400, unit: "g" }],
      // pantry has 200g
      [{ quantity: 200 }],
      // not already on shopping list
      [],
    ]);
    clientModule.drizzleDb = mockDb;

    await addShoppingGapsForRecipe(1, 1);

    expect(mockDb.insert).toHaveBeenCalledTimes(1);
  });

  it("skips insert when pantry already has enough", async () => {
    const mockDb = makeDbMock([
      [{ ingredient_id: 1, canonical_name: "salt", quantity: 50, unit: "g" }],
      [{ quantity: 500 }], // pantry has 500g, needs 50g
    ]);
    clientModule.drizzleDb = mockDb;

    await addShoppingGapsForRecipe(1, 1);

    expect(mockDb.insert).not.toHaveBeenCalled();
  });

  it("skips insert when item is already on the shopping list", async () => {
    const mockDb = makeDbMock([
      [{ ingredient_id: 2, canonical_name: "pasta", quantity: 200, unit: "g" }],
      [], // pantry empty
      [{ id: 3 }], // already on shopping list
    ]);
    clientModule.drizzleDb = mockDb;

    await addShoppingGapsForRecipe(1, 1);

    expect(mockDb.insert).not.toHaveBeenCalled();
  });

  it("inserts correct shortfall quantity across multiple servings", async () => {
    const mockDb = makeDbMock([
      // 100g per serving
      [{ ingredient_id: 5, canonical_name: "rice", quantity: 100, unit: "g" }],
      [{ quantity: 50 }], // only 50g in pantry
      [], // not on list
    ]);
    clientModule.drizzleDb = mockDb;

    await addShoppingGapsForRecipe(1, 3); // 3 servings → 300g needed, 50g in pantry → 250g shortfall

    expect(mockDb.insert).toHaveBeenCalledTimes(1);
  });
});
