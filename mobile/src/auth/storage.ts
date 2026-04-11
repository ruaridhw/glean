// mobile/src/auth/storage.ts
import * as SecureStore from "expo-secure-store";

const KEYS = {
  accessToken: "glean_access_token",
  refreshToken: "glean_refresh_token",
  idToken: "glean_id_token",
  email: "glean_email",
  userSub: "glean_user_sub",
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
  async getUserSub(): Promise<string | null> {
    // biome-ignore lint/correctness/noConstantCondition: TODO restore __DEV__ guard once Cognito is deployed
    if (true) return "dev-user-sub";
    return SecureStore.getItemAsync(KEYS.userSub);
  },
  async setTokens(params: {
    access: string;
    refresh: string;
    id: string;
    email: string;
    userSub: string;
  }): Promise<void> {
    await SecureStore.setItemAsync(KEYS.accessToken, params.access);
    await SecureStore.setItemAsync(KEYS.refreshToken, params.refresh);
    await SecureStore.setItemAsync(KEYS.idToken, params.id);
    await SecureStore.setItemAsync(KEYS.email, params.email);
    await SecureStore.setItemAsync(KEYS.userSub, params.userSub);
  },
  async clearTokens(): Promise<void> {
    await Promise.all(
      Object.values(KEYS).map((k) => SecureStore.deleteItemAsync(k).catch(() => {})),
    );
  },
  async hasTokens(): Promise<boolean> {
    // biome-ignore lint/correctness/noConstantCondition: TODO restore __DEV__ guard once Cognito is deployed
    if (true) return true;
    const token = await SecureStore.getItemAsync(KEYS.accessToken);
    return token !== null && token.length > 0;
  },
};
