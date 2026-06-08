import { getAuthBypassUserSub, isAuthBypassEnabled, resolveAuthSession } from "@/auth/mode";

describe("auth mode", () => {
  const devGlobal = globalThis as typeof globalThis & { __DEV__: boolean };
  const originalDev = devGlobal.__DEV__;

  function setDevMode(enabled: boolean): void {
    Object.defineProperty(devGlobal, "__DEV__", { configurable: true, value: enabled });
  }

  afterEach(() => {
    setDevMode(originalDev);
    delete process.env.EXPO_PUBLIC_AUTH_BYPASS;
    delete process.env.EXPO_PUBLIC_AUTH_BYPASS_USER_SUB;
    delete process.env.EXPO_PUBLIC_APP_VARIANT;
  });

  it("uses the shared dev/e2e bypass identity in development", () => {
    setDevMode(true);

    expect(isAuthBypassEnabled()).toBe(true);
    expect(getAuthBypassUserSub()).toBe("dev-user-sub");
    expect(
      resolveAuthSession({
        accessToken: null,
        refreshToken: null,
        userSub: null,
      }),
    ).toEqual({
      authenticated: true,
      accessToken: null,
      refreshToken: null,
      userSub: "dev-user-sub",
      source: "bypass",
    });
  });

  it("allows the same bypass in CI production builds when explicitly enabled", () => {
    setDevMode(false);
    process.env.EXPO_PUBLIC_APP_VARIANT = "e2e";
    process.env.EXPO_PUBLIC_AUTH_BYPASS = "true";
    process.env.EXPO_PUBLIC_AUTH_BYPASS_USER_SUB = "ci-e2e-user-sub";

    expect(isAuthBypassEnabled()).toBe(true);
    expect(getAuthBypassUserSub()).toBe("ci-e2e-user-sub");
    expect(
      resolveAuthSession({
        accessToken: null,
        refreshToken: null,
        userSub: null,
      }),
    ).toEqual({
      authenticated: true,
      accessToken: null,
      refreshToken: null,
      userSub: "ci-e2e-user-sub",
      source: "bypass",
    });
  });

  it("does not allow production bypass with the public bypass flag alone", () => {
    setDevMode(false);
    process.env.EXPO_PUBLIC_AUTH_BYPASS = "true";
    process.env.EXPO_PUBLIC_AUTH_BYPASS_USER_SUB = "ci-e2e-user-sub";

    expect(isAuthBypassEnabled()).toBe(false);
    expect(
      resolveAuthSession({
        accessToken: null,
        refreshToken: null,
        userSub: null,
      }),
    ).toEqual({
      authenticated: false,
      accessToken: null,
      refreshToken: null,
      userSub: null,
      source: "tokens",
    });
  });

  it("does not authenticate production users without stored tokens or explicit bypass", () => {
    setDevMode(false);

    expect(isAuthBypassEnabled()).toBe(false);
    expect(
      resolveAuthSession({
        accessToken: null,
        refreshToken: null,
        userSub: null,
      }),
    ).toEqual({
      authenticated: false,
      accessToken: null,
      refreshToken: null,
      userSub: null,
      source: "tokens",
    });
  });
});
