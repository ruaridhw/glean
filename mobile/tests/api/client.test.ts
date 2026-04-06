// mobile/tests/api/client.test.ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';

vi.mock('@/auth/storage', () => ({
  authStorage: {
    getAccessToken: vi.fn(),
  },
}));

vi.mock('@/auth/cognito', () => ({
  refreshTokens: vi.fn(),
}));

import { authStorage } from '@/auth/storage';
import { refreshTokens } from '@/auth/cognito';
import { apiClient, ApiError } from '@/api/client';

const mockGetAccessToken = authStorage.getAccessToken as Mock;
const mockRefreshTokens = refreshTokens as Mock;

describe('apiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    mockGetAccessToken.mockResolvedValue('valid-token');
  });

  describe('get', () => {
    it('sends Bearer token in Authorization header', async () => {
      (global.fetch as Mock).mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({ data: 'ok' }),
      });

      await apiClient.get('/health');

      const [, init] = (global.fetch as Mock).mock.calls[0];
      expect((init.headers as Record<string, string>)['Authorization']).toBe('Bearer valid-token');
    });

    it('throws ApiError on non-2xx response', async () => {
      (global.fetch as Mock).mockResolvedValue({
        ok: false,
        status: 500,
        json: vi.fn().mockResolvedValue({ detail: 'Server error' }),
      });

      await expect(apiClient.get('/health')).rejects.toBeInstanceOf(ApiError);
    });
  });

  describe('401 refresh and retry', () => {
    it('refreshes tokens and retries on 401', async () => {
      (global.fetch as Mock)
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: vi.fn().mockResolvedValue({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValue({ data: 'ok' }),
        });

      mockRefreshTokens.mockResolvedValue(true);
      mockGetAccessToken
        .mockResolvedValueOnce('old-token')
        .mockResolvedValueOnce('new-token');

      const result = await apiClient.get('/protected');
      expect(mockRefreshTokens).toHaveBeenCalledTimes(1);
      expect(global.fetch).toHaveBeenCalledTimes(2);
      expect(result).toEqual({ data: 'ok' });
    });

    it('throws ApiError with 401 when refresh fails', async () => {
      (global.fetch as Mock).mockResolvedValue({
        ok: false,
        status: 401,
        json: vi.fn().mockResolvedValue({ detail: 'Unauthorized' }),
      });

      mockRefreshTokens.mockResolvedValue(false);

      const error = await apiClient.get('/protected').catch((e) => e);
      expect(error).toBeInstanceOf(ApiError);
      expect(error.status).toBe(401);
    });
  });
});
