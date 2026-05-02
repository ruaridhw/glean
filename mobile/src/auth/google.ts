// mobile/src/auth/google.ts
import { exchangeCodeAsync, type TokenResponse } from "expo-auth-session";
import { authStorage } from "./storage";

const COGNITO_DOMAIN = process.env.EXPO_PUBLIC_COGNITO_DOMAIN ?? "";
const CLIENT_ID = process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID ?? "";
const REDIRECT_URI = "glean://auth/callback";

const TOKEN_ENDPOINT = `https://${COGNITO_DOMAIN}/oauth2/token`;

export const AUTHORIZE_URL = `https://${COGNITO_DOMAIN}/oauth2/authorize`;

function decodeIdTokenPayload(idToken: string): { sub: string; email: string } {
  const payload = idToken.split(".")[1];
  if (!payload) throw new Error("Invalid ID token");
  // Use Buffer in Node/test environments; atob works in React Native's Hermes engine
  const json =
    typeof Buffer !== "undefined"
      ? Buffer.from(payload.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf-8")
      : atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
  return JSON.parse(json);
}

export async function handleAuthCode(code: string, codeVerifier: string): Promise<void> {
  const tokenResponse: TokenResponse = await exchangeCodeAsync(
    {
      code,
      clientId: CLIENT_ID,
      redirectUri: REDIRECT_URI,
      extraParams: { code_verifier: codeVerifier },
    },
    { tokenEndpoint: TOKEN_ENDPOINT },
  );

  const { idToken, refreshToken } = tokenResponse;
  if (!idToken || !refreshToken) throw new Error("Token response missing required tokens");

  const { sub, email } = decodeIdTokenPayload(idToken);

  await authStorage.setTokens({
    access: tokenResponse.accessToken,
    refresh: refreshToken,
    id: idToken,
    email,
    userSub: sub,
  });
}

export async function refreshTokens(): Promise<boolean> {
  const refreshToken = await authStorage.getRefreshToken();
  if (!refreshToken) return false;

  try {
    const body = new URLSearchParams({
      grant_type: "refresh_token",
      client_id: CLIENT_ID,
      refresh_token: refreshToken,
    });

    const response = await fetch(TOKEN_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });

    if (!response.ok) {
      await authStorage.clearTokens();
      return false;
    }

    const data = await response.json();
    const { sub, email } = decodeIdTokenPayload(data.id_token);

    await authStorage.setTokens({
      access: data.access_token,
      refresh: refreshToken, // Cognito doesn't return a new refresh token
      id: data.id_token,
      email,
      userSub: sub,
    });

    return true;
  } catch {
    await authStorage.clearTokens();
    return false;
  }
}

export async function signOut(): Promise<void> {
  await authStorage.clearTokens();
}
