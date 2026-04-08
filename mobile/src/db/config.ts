// mobile/src/db/config.ts
import { eq } from "drizzle-orm";
import { authStorage } from "@/auth/storage";
import type { UserConfig } from "@/types";
import { drizzleDb } from "./client";
import { userConfig } from "./schema";

const DEFAULT_CONFIG: Omit<UserConfig, "id"> = {
  purchase_tolerance: 0.5,
  preferred_servings: 2,
  meals_per_week: 5,
  dietary_flags: [],
  max_active_time_mins: null,
};

export async function getUserConfig(): Promise<UserConfig> {
  const sub = await authStorage.getUserSub();
  if (!sub) throw new Error("Not authenticated");

  const [row] = await drizzleDb.select().from(userConfig).where(eq(userConfig.id, sub));

  if (!row) return { id: sub, ...DEFAULT_CONFIG };

  return {
    id: row.id,
    purchase_tolerance: row.purchase_tolerance,
    preferred_servings: row.preferred_servings,
    meals_per_week: row.meals_per_week,
    dietary_flags: JSON.parse(row.dietary_flags) as string[],
    max_active_time_mins: row.max_active_time_mins ?? null,
  };
}

export async function saveUserConfig(config: UserConfig): Promise<void> {
  await drizzleDb
    .insert(userConfig)
    .values({
      id: config.id,
      purchase_tolerance: config.purchase_tolerance,
      preferred_servings: config.preferred_servings,
      meals_per_week: config.meals_per_week,
      dietary_flags: JSON.stringify(config.dietary_flags),
      max_active_time_mins: config.max_active_time_mins ?? null,
    })
    .onConflictDoUpdate({
      target: userConfig.id,
      set: {
        purchase_tolerance: config.purchase_tolerance,
        preferred_servings: config.preferred_servings,
        meals_per_week: config.meals_per_week,
        dietary_flags: JSON.stringify(config.dietary_flags),
        max_active_time_mins: config.max_active_time_mins ?? null,
      },
    });
}
