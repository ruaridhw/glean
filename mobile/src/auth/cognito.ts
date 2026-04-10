// mobile/src/auth/cognito.ts
import {
  AuthenticationDetails,
  CognitoRefreshToken,
  CognitoUser,
  CognitoUserAttribute,
  CognitoUserPool,
  type CognitoUserSession,
} from "amazon-cognito-identity-js";
import { authStorage } from "./storage";

// Lazy-init: env vars aren't available at module-load time in local dev
// (no .env.local with Cognito IDs). Deferring creation avoids the
// "Both UserPoolId and ClientId are required" crash on import.
let _userPool: CognitoUserPool | null = null;

function getUserPool(): CognitoUserPool {
  if (!_userPool) {
    _userPool = new CognitoUserPool({
      // biome-ignore lint/style/noNonNullAssertion: required Expo public env vars
      UserPoolId: process.env.EXPO_PUBLIC_COGNITO_USER_POOL_ID!,
      // biome-ignore lint/style/noNonNullAssertion: required Expo public env vars
      ClientId: process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID!,
    });
  }
  return _userPool;
}

function getUser(email: string): CognitoUser {
  return new CognitoUser({ Username: email, Pool: getUserPool() });
}

export async function signIn(email: string, password: string): Promise<void> {
  if (__DEV__) {
    await authStorage.setTokens({
      access: "dev-access",
      refresh: "dev-refresh",
      id: "dev-id",
      email,
      userSub: "dev-user-sub",
    });
    return;
  }
  return new Promise((resolve, reject) => {
    getUser(email).authenticateUser(
      new AuthenticationDetails({ Username: email, Password: password }),
      {
        onSuccess: async (session: CognitoUserSession) => {
          const idPayload = session.getIdToken().decodePayload();
          await authStorage.setTokens({
            access: session.getAccessToken().getJwtToken(),
            refresh: session.getRefreshToken().getToken(),
            id: session.getIdToken().getJwtToken(),
            email,
            userSub: idPayload.sub as string,
          });
          resolve();
        },
        onFailure: reject,
      },
    );
  });
}

export async function signUp(email: string, password: string): Promise<void> {
  return new Promise((resolve, reject) => {
    getUserPool().signUp(
      email,
      password,
      [new CognitoUserAttribute({ Name: "email", Value: email })],
      [],
      (err) => (err ? reject(err) : resolve()),
    );
  });
}

export async function refreshTokens(): Promise<boolean> {
  const [rawRefreshToken, email] = await Promise.all([
    authStorage.getRefreshToken(),
    authStorage.getEmail(),
  ]);
  if (!rawRefreshToken || !email) return false;

  return new Promise((resolve) => {
    getUser(email).refreshSession(
      new CognitoRefreshToken({ RefreshToken: rawRefreshToken }),
      async (err, session: CognitoUserSession) => {
        if (err) {
          await authStorage.clearTokens();
          resolve(false);
        } else {
          const idPayload = session.getIdToken().decodePayload();
          await authStorage.setTokens({
            access: session.getAccessToken().getJwtToken(),
            refresh: session.getRefreshToken().getToken(),
            id: session.getIdToken().getJwtToken(),
            email,
            userSub: idPayload.sub as string,
          });
          resolve(true);
        }
      },
    );
  });
}

export async function signOut(): Promise<void> {
  await authStorage.clearTokens();
}
