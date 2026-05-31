import { render, waitFor } from "@testing-library/react-native";
import type { ReactNode } from "react";

import RootLayout from "../../app/_layout";

const mockStackScreens: string[] = [];

jest.mock("expo-router", () => {
  const React = require("react");

  const Stack = ({ children }: { children: ReactNode }) =>
    React.createElement(React.Fragment, null, children);
  Stack.Screen = ({ name }: { name: string }) => {
    mockStackScreens.push(name);
    return null;
  };

  return {
    router: { replace: jest.fn() },
    Stack,
  };
});

jest.mock("@/auth/storage", () => ({
  authStorage: { hasTokens: jest.fn().mockResolvedValue(true) },
}));

jest.mock("@/db/client", () => ({
  getDb: jest.fn().mockResolvedValue({}),
}));

jest.mock("@/db/seed", () => ({
  seedDatabase: jest.fn().mockResolvedValue(undefined),
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
  const { Text } = require("react-native");
  return () => React.createElement(Text, null, "Loading");
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
    jest.clearAllMocks();
  });

  it("wraps the app stack in a gesture handler root view", async () => {
    const screen = render(<RootLayout />);

    await waitFor(() => expect(mockStackScreens).toContain("(tabs)"));

    expect(screen.getByTestId("gesture-handler-root").props.style).toEqual({ flex: 1 });
  });
});
