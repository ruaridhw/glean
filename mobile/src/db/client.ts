// mobile/src/db/client.ts

import { drizzle } from "drizzle-orm/expo-sqlite";
import { migrate } from "drizzle-orm/expo-sqlite/migrator";
import { openDatabaseSync } from "expo-sqlite";
import migrations from "../../drizzle/migrations";

const expo = openDatabaseSync("glean.db", { enableChangeListener: true });
export const drizzleDb = drizzle(expo);

let _ready = false;

export async function getDb() {
  if (!_ready) {
    await expo.execAsync("PRAGMA foreign_keys = ON;");
    await migrate(drizzleDb, migrations);
    _ready = true;
  }
  return expo;
}
