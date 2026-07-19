// mobile/src/auth/storage.ts
import * as SecureStore from "expo-secure-store";
import { isAuthBypassEnabled, resolveAuthSession } from "./mode";

const KEYS = {
  accessToken: "glean_access_token",
  refreshToken: "glean_refresh_token",
  idToken: "glean_id_token",
  email: "glean_email",
  userSub: "glean_user_sub",
  pendingAuthCodeVerifier: "glean_pending_auth_code_verifier",
  pendingAuthState: "glean_pending_auth_state",
};

// Single entry point for "what is the current auth session?". resolveAuthSession is the
// authoritative source of the session shape; the bypass short-circuit here just avoids
// touching SecureStore when it isn't needed.
async function loadSession() {
  if (isAuthBypassEnabled()) {
    return resolveAuthSession({ accessToken: null, refreshToken: null, userSub: null });
  }
  const [accessToken, refreshToken, userSub] = await Promise.all([
    SecureStore.getItemAsync(KEYS.accessToken),
    SecureStore.getItemAsync(KEYS.refreshToken),
    SecureStore.getItemAsync(KEYS.userSub),
  ]);
  return resolveAuthSession({ accessToken, refreshToken, userSub });
}

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
    return (await loadSession()).userSub;
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
      [KEYS.accessToken, KEYS.refreshToken, KEYS.idToken, KEYS.email, KEYS.userSub].map((k) =>
        SecureStore.deleteItemAsync(k).catch(() => {}),
      ),
    );
  },
  async setPendingAuthRequest(params: { codeVerifier: string; state?: string }): Promise<void> {
    await SecureStore.setItemAsync(KEYS.pendingAuthCodeVerifier, params.codeVerifier);
    if (params.state) {
      await SecureStore.setItemAsync(KEYS.pendingAuthState, params.state);
    } else {
      await SecureStore.deleteItemAsync(KEYS.pendingAuthState).catch(() => {});
    }
  },
  async getPendingAuthCodeVerifier(state?: string): Promise<string | null> {
    const codeVerifier = await SecureStore.getItemAsync(KEYS.pendingAuthCodeVerifier);
    if (!codeVerifier) return null;

    const expectedState = await SecureStore.getItemAsync(KEYS.pendingAuthState);
    if (expectedState && expectedState !== state) return null;
    if (!expectedState && state) return null;

    return codeVerifier;
  },
  async clearPendingAuthRequest(): Promise<void> {
    await Promise.all(
      [KEYS.pendingAuthCodeVerifier, KEYS.pendingAuthState].map((k) =>
        SecureStore.deleteItemAsync(k).catch(() => {}),
      ),
    );
  },
  async hasTokens(): Promise<boolean> {
    return (await loadSession()).authenticated;
  },
};
