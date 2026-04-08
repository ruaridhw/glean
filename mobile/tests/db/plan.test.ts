// mobile/tests/db/plan.test.ts

// Chainable drizzle query builder mock: every method returns a new thenable
// that resolves to the queued value when await-ed.
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

function makeDbMock(selectQueue: unknown[], updateSpy?: jest.Mock) {
  let si = 0;
  const update = updateSpy ?? jest.fn(() => chain(undefined));
  return {
    select: jest.fn(() => chain(selectQueue[si++] ?? [])),
    insert: jest.fn((table: unknown) => {
      void table;
      return chain([{ id: 7 }]);
    }),
    update,
    delete: jest.fn(() => chain(undefined)),
    __updateMock: update,
  };
}

jest.mock("@/db/client", () => ({ drizzleDb: {} }));
jest.mock("@/normalization/units", () => ({
  normalizeUnit: jest.fn(() => null), // no conversion
}));

import { addMealPlanEntry, getMealPlanCount, markMealAsCooked } from "@/db/plan";

const clientModule = require("@/db/client");

describe("getMealPlanCount", () => {
  it("returns the row count", async () => {
    clientModule.drizzleDb = makeDbMock([[{ count: 5 }]]);
    const result = await getMealPlanCount();
    expect(result).toBe(5);
  });

  it("returns 0 when table is empty", async () => {
    clientModule.drizzleDb = makeDbMock([[{ count: 0 }]]);
    const result = await getMealPlanCount();
    expect(result).toBe(0);
  });
});

describe("addMealPlanEntry", () => {
  it("inserts a row and returns the new id", async () => {
    const mockDb = makeDbMock([]);
    clientModule.drizzleDb = mockDb;

    const id = await addMealPlanEntry(3, 2);
    expect(id).toBe(7);
    expect(mockDb.insert).toHaveBeenCalledTimes(1);
  });
});

describe("markMealAsCooked", () => {
  it("throws when entry not found", async () => {
    clientModule.drizzleDb = makeDbMock([
      [], // entry lookup → empty
    ]);
    await expect(markMealAsCooked(999)).rejects.toThrow("not found");
  });

  it("decrements pantry, stamps last_used_at and cooked_at", async () => {
    const updateMock = jest.fn(() => chain(undefined));
    clientModule.drizzleDb = {
      ...makeDbMock(
        [
          [{ recipe_id: 2, servings: 1 }], // entry
          [{ ingredient_id: 10, quantity: 200, unit: "g" }], // recipeIngs
          [{ canonical_unit: "g", canonical_name: "chicken breast" }], // ingredient
          [{ unit: "g" }], // pantryRow
        ],
        updateMock,
      ),
    };

    await markMealAsCooked(5);

    // update called 3 times: pantry, recipe, entry
    expect(updateMock).toHaveBeenCalledTimes(3);
  });

  it("handles recipe with no pantry row for ingredient gracefully", async () => {
    const updateMock = jest.fn(() => chain(undefined));
    clientModule.drizzleDb = {
      ...makeDbMock(
        [
          [{ recipe_id: 2, servings: 1 }],
          [{ ingredient_id: 10, quantity: 200, unit: "g" }],
          [{ canonical_unit: "g", canonical_name: "chicken breast" }],
          [], // no pantry row
        ],
        updateMock,
      ),
    };

    await markMealAsCooked(5);

    // Still stamps recipe and entry even when no pantry row
    expect(updateMock).toHaveBeenCalledTimes(3);
  });
});
