// mobile/tests/db/client.test.ts

import { migrate } from "drizzle-orm/expo-sqlite/migrator";
import { openDatabaseSync } from "expo-sqlite";

jest.mock("expo-sqlite", () => ({
  openDatabaseSync: jest.fn(() => ({
    execAsync: jest.fn().mockResolvedValue(undefined),
  })),
}));

jest.mock("drizzle-orm/expo-sqlite", () => ({
  drizzle: jest.fn(() => ({})),
}));

jest.mock("drizzle-orm/expo-sqlite/migrator", () => ({
  migrate: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("../../drizzle/migrations", () => ({ default: {} }), { virtual: true });

import { getDb } from "@/db/client";

describe("getDb", () => {
  it("calls migrate on first invocation", async () => {
    await getDb();
    expect(migrate).toHaveBeenCalledTimes(1);
  });

  it("does not call migrate on subsequent invocations", async () => {
    await getDb();
    expect(migrate).toHaveBeenCalledTimes(1);
  });

  it("returns the raw expo-sqlite database", async () => {
    const db = await getDb();
    const mockDb = (openDatabaseSync as jest.Mock).mock.results[0]!.value;
    expect(db).toBe(mockDb);
    expect(mockDb.execAsync).toHaveBeenCalledWith("PRAGMA foreign_keys = ON;");
  });
});
