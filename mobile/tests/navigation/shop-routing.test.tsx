import { render } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import TabsLayout from "../../app/(tabs)/_layout";
import ShopLayout from "../../app/(tabs)/shop/_layout";

const initialMetrics = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 47, left: 0, right: 0, bottom: 34 },
};

const mockTabScreens: Array<{ name: string; options?: { title?: string; href?: string | null } }> =
  [];
const mockStackLayouts: Array<{ screenOptions?: { headerShown?: boolean } }> = [];

jest.mock("@expo/vector-icons", () => {
  const React = require("react");
  const { Text } = require("react-native");
  return { Ionicons: ({ name }: { name: string }) => React.createElement(Text, null, name) };
});

jest.mock("expo-router", () => {
  const React = require("react");

  const Tabs = ({ children }: { children: ReactNode }) =>
    React.createElement(React.Fragment, null, children);
  Tabs.Screen = (props: { name: string; options?: { title?: string; href?: string | null } }) => {
    mockTabScreens.push(props);
    return null;
  };

  const Stack = (props: { screenOptions?: { headerShown?: boolean } }) => {
    mockStackLayouts.push(props);
    return null;
  };

  return { Stack, Tabs };
});

describe("Shop routing", () => {
  beforeEach(() => {
    mockTabScreens.length = 0;
    mockStackLayouts.length = 0;
  });

  it("mounts Shop as a nested tab stack instead of flat hidden tab routes", () => {
    render(
      <SafeAreaProvider initialMetrics={initialMetrics}>
        <TabsLayout />
      </SafeAreaProvider>,
    );

    expect(mockTabScreens.map((screen) => screen.name)).toEqual([
      "pantry",
      "meals",
      "plan/index",
      "shop",
      "settings/index",
    ]);
    expect(mockTabScreens).not.toEqual(
      expect.arrayContaining([
        expect.objectContaining({ name: "shop/index" }),
        expect.objectContaining({ name: "shop/describe" }),
        expect.objectContaining({ name: "shop/review" }),
      ]),
    );
    expect(mockTabScreens.find((screen) => screen.name === "shop")?.options).toEqual(
      expect.objectContaining({
        tabBarButtonTestID: "tabs.shop",
        title: "Shop",
      }),
    );
  });

  it("uses a headerless stack for Shop describe and review screens", () => {
    render(<ShopLayout />);

    expect(mockStackLayouts).toEqual([
      expect.objectContaining({ screenOptions: { headerShown: false } }),
    ]);
  });
});
