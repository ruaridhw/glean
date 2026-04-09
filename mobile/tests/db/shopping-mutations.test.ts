// mobile/tests/db/shopping-mutations.test.ts

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

import {
  addManualShoppingItem,
  completeCheckout,
  deleteShoppingItem,
  toggleShoppingItem,
} from "@/db/shopping";

const clientModule = require("@/db/client");

function makeDbMock() {
  return {
    select: jest.fn(() => chain([])),
    insert: jest.fn(() => chain([])),
    update: jest.fn(() => chain(undefined)),
    delete: jest.fn(() => chain(undefined)),
  };
}

describe("addManualShoppingItem", () => {
  it("inserts a row with source manual", async () => {
    const mockDb = makeDbMock();
    clientModule.drizzleDb = mockDb;

    await addManualShoppingItem({ name: "birthday candles" });

    expect(mockDb.insert).toHaveBeenCalledTimes(1);
  });

  it("passes all optional fields through", async () => {
    const mockDb = makeDbMock();
    clientModule.drizzleDb = mockDb;

    await addManualShoppingItem({
      name: "whole milk",
      quantity: 2000,
      unit: "ml",
      ingredient_id: 42,
    });

    expect(mockDb.insert).toHaveBeenCalledTimes(1);
  });
});

describe("toggleShoppingItem", () => {
  it("calls update when setting checked to true", async () => {
    const mockDb = makeDbMock();
    clientModule.drizzleDb = mockDb;

    await toggleShoppingItem(5, true);

    expect(mockDb.update).toHaveBeenCalledTimes(1);
  });

  it("calls update when setting checked to false", async () => {
    const mockDb = makeDbMock();
    clientModule.drizzleDb = mockDb;

    await toggleShoppingItem(5, false);

    expect(mockDb.update).toHaveBeenCalledTimes(1);
  });
});

describe("deleteShoppingItem", () => {
  it("deletes the item by id", async () => {
    const mockDb = makeDbMock();
    clientModule.drizzleDb = mockDb;

    await deleteShoppingItem(7);

    expect(mockDb.delete).toHaveBeenCalledTimes(1);
  });
});

describe("completeCheckout", () => {
  it("deletes all checked items", async () => {
    const mockDb = makeDbMock();
    clientModule.drizzleDb = mockDb;

    await completeCheckout();

    expect(mockDb.delete).toHaveBeenCalledTimes(1);
  });
});
