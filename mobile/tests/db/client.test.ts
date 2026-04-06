// mobile/tests/db/client.test.ts

jest.mock('expo-sqlite', () => ({
  openDatabaseSync: jest.fn(() => ({
    execAsync: jest.fn().mockResolvedValue(undefined),
  })),
}));

jest.mock('drizzle-orm/expo-sqlite', () => ({
  drizzle: jest.fn(() => ({})),
}));

const mockMigrate = jest.fn().mockResolvedValue(undefined);
jest.mock('drizzle-orm/expo-sqlite/migrator', () => ({
  migrate: mockMigrate,
}));

jest.mock('../../drizzle/migrations', () => ({ default: {} }), { virtual: true });

describe('getDb', () => {
  beforeEach(() => {
    jest.resetModules();
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
    const { getDb } = await import('@/db/client');
    const db = await getDb();
    expect(db).toHaveProperty('execAsync');
    expect((db as jest.Mock & { execAsync: jest.Mock }).execAsync).toHaveBeenCalledWith(
      'PRAGMA foreign_keys = ON;',
    );
  });
});
