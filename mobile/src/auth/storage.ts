// mobile/src/auth/storage.ts
import * as SecureStore from "expo-secure-store";

const KEYS = {
  accessToken: "glean_access_token",
  refreshToken: "glean_refresh_token",
  idToken: "glean_id_token",
  email: "glean_email",
};

export const authStorage = {
  async getAccessToken(): Promise<string | null> {
    return SecureStore.getItemAsync(KEYS.accessToken);
  },
  async getRefreshToken(): Promise<string | null> {
    return SecureStore.getItemAsync(KEYS.refreshToken);
  },
  async getEmail(): Promise<string | null> {
    return SecureStore.getItemAsync(KEYS.email);
  },
  async setTokens(params: {
    access: string;
    refresh: string;
    id: string;
    email: string;
  }): Promise<void> {
    await SecureStore.setItemAsync(KEYS.accessToken, params.access);
    await SecureStore.setItemAsync(KEYS.refreshToken, params.refresh);
    await SecureStore.setItemAsync(KEYS.idToken, params.id);
    await SecureStore.setItemAsync(KEYS.email, params.email);
  },
  async clearTokens(): Promise<void> {
    await Promise.all(
      Object.values(KEYS).map((k) => SecureStore.deleteItemAsync(k).catch(() => {})),
    );
  },
  async hasTokens(): Promise<boolean> {
    const token = await SecureStore.getItemAsync(KEYS.accessToken);
    return token !== null && token.length > 0;
  },
};
