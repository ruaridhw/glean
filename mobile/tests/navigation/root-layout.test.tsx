import { render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import type { ReactNode } from "react";
import { authStorage } from "@/auth/storage";
import { getDb } from "@/db/client";
import { seedDatabase } from "@/db/seed";
import RootLayout from "../../app/_layout";

const mockStackScreens: string[] = [];
const protectedGuards: boolean[] = [];

jest.mock("expo-router", () => {
  const React = require("react");
  const { View } = require("react-native");
  const Stack = Object.assign(
    ({ children }: { children: ReactNode }) => {
      return React.createElement(View, { testID: "root-stack" }, children);
    },
    {
      Screen: ({ name }: { name: string }) => {
        mockStackScreens.push(name);
        return React.createElement(View, { testID: `stack-screen-${name}` });
      },
      Protected: ({ children, guard }: { children: ReactNode; guard: boolean }) => {
        protectedGuards.push(guard);
        return guard ? React.createElement(View, { testID: "protected-stack" }, children) : null;
      },
    },
  );

  return { router: { replace: jest.fn() }, Stack };
});

jest.mock("@/auth/storage", () => ({
  authStorage: { getUserSub: jest.fn(), hasTokens: jest.fn() },
}));

jest.mock("@/db/client", () => ({
  getDb: jest.fn(),
}));

jest.mock("@/db/seed", () => ({
  seedDatabase: jest.fn(),
}));

jest.mock("@/components/ui/OfflineBanner", () => ({
  OfflineBanner: () => null,
}));

jest.mock("@/components/ui/Toast", () => ({
  Toast: () => null,
  toastConfig: {},
}));

jest.mock("@/screens/SplashScreen", () => {
  const React = require("react");
  const { View } = require("react-native");
  return () => React.createElement(View, { testID: "splash-screen" });
});

jest.mock("react-native-gesture-handler", () => {
  const React = require("react");
  const { View } = require("react-native");

  return {
    GestureHandlerRootView: ({ children, style }: { children: ReactNode; style?: object }) =>
      React.createElement(View, { style, testID: "gesture-handler-root" }, children),
  };
});

describe("RootLayout", () => {
  beforeEach(() => {
    mockStackScreens.length = 0;
    protectedGuards.length = 0;
    jest.clearAllMocks();
    (getDb as jest.Mock).mockResolvedValue({});
    (seedDatabase as jest.Mock).mockResolvedValue(undefined);
    (authStorage.hasTokens as jest.Mock).mockResolvedValue(false);
    (authStorage.getUserSub as jest.Mock).mockResolvedValue(null);
  });

  it("wraps the app stack in a gesture handler root view", async () => {
    (authStorage.hasTokens as jest.Mock).mockResolvedValue(true);
    (authStorage.getUserSub as jest.Mock).mockResolvedValue("user-sub-123");
    const screen = render(<RootLayout />);

    await waitFor(() => expect(mockStackScreens).toContain("(tabs)"));

    expect(screen.getByTestId("gesture-handler-root").props.style).toEqual({ flex: 1 });
  });

  it("gates unauthenticated users to the sign-in route", async () => {
    const screen = render(<RootLayout />);

    expect(screen.getByTestId("splash-screen")).toBeTruthy();

    await waitFor(() => expect(screen.getByTestId("root-stack")).toBeTruthy());

    expect(protectedGuards).toEqual([true, false]);
    expect(mockStackScreens).toContain("sign-in");
    expect(mockStackScreens).toContain("auth/callback");
    expect(mockStackScreens).not.toContain("index");
    expect(mockStackScreens).not.toContain("(tabs)");
    expect(router.replace).not.toHaveBeenCalled();
    expect(getDb).toHaveBeenCalledTimes(1);
    expect(seedDatabase).toHaveBeenCalledTimes(1);
    expect(authStorage.hasTokens).toHaveBeenCalledTimes(1);
  });

  it("opens the protected app stack for authenticated users", async () => {
    (authStorage.hasTokens as jest.Mock).mockResolvedValue(true);
    (authStorage.getUserSub as jest.Mock).mockResolvedValue("user-sub-123");

    render(<RootLayout />);

    await waitFor(() => expect(mockStackScreens).toContain("(tabs)"));

    expect(protectedGuards).toEqual([false, true]);
    expect(mockStackScreens).toContain("index");
    expect(mockStackScreens).toContain("(tabs)");
    expect(mockStackScreens).not.toContain("sign-in");
  });
});
