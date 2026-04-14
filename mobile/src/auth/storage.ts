// mobile/src/auth/storage.ts
import * as SecureStore from "expo-secure-store";

const KEYS = {
  accessToken: "glean_access_token",
  refreshToken: "glean_refresh_token",
  idToken: "glean_id_token",
  email: "glean_email",
  userSub: "glean_user_sub",
};

function ciToken(name: string): string | undefined {
  return process.env[`EXPO_PUBLIC_CI_${name}`];
}

export const authStorage = {
  async getAccessToken(): Promise<string | null> {
    const ci = ciToken("ACCESS_TOKEN");
    if (ci) return ci;
    return SecureStore.getItemAsync(KEYS.accessToken);
  },
  async getRefreshToken(): Promise<string | null> {
    const ci = ciToken("REFRESH_TOKEN");
    if (ci) return ci;
    return SecureStore.getItemAsync(KEYS.refreshToken);
  },
  async getEmail(): Promise<string | null> {
    return SecureStore.getItemAsync(KEYS.email);
  },
  async getUserSub(): Promise<string | null> {
    if (__DEV__) return "dev-user-sub";
    const ciIdToken = ciToken("ID_TOKEN");
    if (ciIdToken) {
      try {
        const payload = ciIdToken.split(".")[1]!;
        const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
        return (JSON.parse(json) as { sub: string }).sub;
      } catch {
        return null;
      }
    }
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
    if (__DEV__ || ciToken("ACCESS_TOKEN")) return true;
    const token = await SecureStore.getItemAsync(KEYS.accessToken);
    return token !== null && (token?.length ?? 0) > 0;
  },
};
