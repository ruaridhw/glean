// mobile/tests/db/client.test.ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';

vi.mock('expo-sqlite', () => ({
  openDatabaseSync: vi.fn(() => ({
    execAsync: vi.fn().mockResolvedValue(undefined),
  })),
}));

vi.mock('drizzle-orm/expo-sqlite', () => ({
  drizzle: vi.fn(() => ({})),
}));

const mockMigrate = vi.fn().mockResolvedValue(undefined);
vi.mock('drizzle-orm/expo-sqlite/migrator', () => ({
  migrate: mockMigrate,
}));

vi.mock('../../drizzle/migrations', () => ({ default: {} }));

describe('getDb', () => {
  beforeEach(() => {
    vi.resetModules();
    mockMigrate.mockClear();
  });

  it('calls migrate on first invocation', async () => {
    const { getDb } = await import('@/db/client');
    await getDb();
    expect(mockMigrate).toHaveBeenCalledTimes(1);
  });

  it('does not call migrate on subsequent invocations', async () => {
    const { getDb } = await import('@/db/client');
    await getDb();
    await getDb();
    expect(mockMigrate).toHaveBeenCalledTimes(1);
  });

  it('returns the raw expo-sqlite database', async () => {
    // The client module calls openDatabaseSync at the top level and stores the
    // result as `expo`. getDb() returns that same object. We verify it is the
    // expo-sqlite instance by confirming execAsync is present and was called.
    const { getDb } = await import('@/db/client');
    const db = await getDb();
    expect(db).toHaveProperty('execAsync');
    expect((db as { execAsync: Mock }).execAsync).toHaveBeenCalledWith('PRAGMA foreign_keys = ON;');
  });
});
