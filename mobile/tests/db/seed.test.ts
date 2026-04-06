// mobile/tests/db/seed.test.ts
import { describe, expect, it, vi } from 'vitest';
import { seedDatabase } from '@/db/seed';

function makeMockDb(categoryCount: number) {
  const runAsync = vi.fn().mockResolvedValue(undefined);
  const getFirstAsync = vi.fn().mockResolvedValue({ count: categoryCount });
  const withTransactionAsync = vi.fn(async (fn: () => Promise<void>) => fn());
  return { runAsync, getFirstAsync, withTransactionAsync } as any;
}

describe('seedDatabase', () => {
  it('inserts 23 categories and 10 staples when table is empty', async () => {
    const db = makeMockDb(0);
    await seedDatabase(db);
    expect(db.withTransactionAsync).toHaveBeenCalledTimes(1);
    const categoryCalls = db.runAsync.mock.calls.filter((c: string[]) =>
      c[0]?.includes('ingredient_categories')
    );
    const stapleCalls = db.runAsync.mock.calls.filter((c: string[]) =>
      c[0]?.includes('ingredients')
    );
    expect(categoryCalls).toHaveLength(23);
    expect(stapleCalls).toHaveLength(10);
  });

  it('skips seeding when categories already exist', async () => {
    const db = makeMockDb(23);
    await seedDatabase(db);
    expect(db.withTransactionAsync).not.toHaveBeenCalled();
    expect(db.runAsync).not.toHaveBeenCalled();
  });
});
