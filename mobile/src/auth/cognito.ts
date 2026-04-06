// mobile/src/auth/cognito.ts
import {
  CognitoUser,
  CognitoUserPool,
  AuthenticationDetails,
  CognitoUserSession,
  CognitoRefreshToken,
  CognitoUserAttribute,
} from 'amazon-cognito-identity-js';
import { authStorage } from './storage';

const userPool = new CognitoUserPool({
  UserPoolId: process.env.EXPO_PUBLIC_COGNITO_USER_POOL_ID!,
  ClientId: process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID!,
});

function getUser(email: string): CognitoUser {
  return new CognitoUser({ Username: email, Pool: userPool });
}

export async function signIn(email: string, password: string): Promise<void> {
  return new Promise((resolve, reject) => {
    getUser(email).authenticateUser(
      new AuthenticationDetails({ Username: email, Password: password }),
      {
        onSuccess: async (session: CognitoUserSession) => {
          await authStorage.setTokens({
            access: session.getAccessToken().getJwtToken(),
            refresh: session.getRefreshToken().getToken(),
            id: session.getIdToken().getJwtToken(),
            email,
          });
          resolve();
        },
        onFailure: reject,
      }
    );
  });
}

export async function signUp(email: string, password: string): Promise<void> {
  return new Promise((resolve, reject) => {
    userPool.signUp(
      email,
      password,
      [new CognitoUserAttribute({ Name: 'email', Value: email })],
      [],
      (err) => (err ? reject(err) : resolve())
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
          await authStorage.setTokens({
            access: session.getAccessToken().getJwtToken(),
            refresh: session.getRefreshToken().getToken(),
            id: session.getIdToken().getJwtToken(),
            email,
          });
          resolve(true);
        }
      }
    );
  });
}

export async function signOut(): Promise<void> {
  await authStorage.clearTokens();
}
