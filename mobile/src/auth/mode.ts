type AuthSessionSource = "bypass" | "tokens";

type StoredAuthValues = {
  accessToken: string | null;
  refreshToken: string | null;
  userSub: string | null;
};

type AuthSession = StoredAuthValues & {
  authenticated: boolean;
  source: AuthSessionSource;
};

const AUTH_BYPASS_USER_SUB = "dev-user-sub";

export function isAuthBypassEnabled(): boolean {
  return (
    __DEV__ ||
    (process.env.EXPO_PUBLIC_AUTH_BYPASS === "true" &&
      process.env.EXPO_PUBLIC_APP_VARIANT === "e2e")
  );
}

export function getAuthBypassUserSub(): string {
  return process.env.EXPO_PUBLIC_AUTH_BYPASS_USER_SUB?.trim() || AUTH_BYPASS_USER_SUB;
}

export function resolveAuthSession(values: StoredAuthValues): AuthSession {
  if (isAuthBypassEnabled()) {
    return {
      authenticated: true,
      accessToken: null,
      refreshToken: null,
      userSub: getAuthBypassUserSub(),
      source: "bypass",
    };
  }

  const authenticated = Boolean(values.accessToken && values.accessToken.length > 0);

  return {
    authenticated,
    accessToken: values.accessToken,
    refreshToken: values.refreshToken,
    userSub: values.userSub,
    source: "tokens",
  };
}
