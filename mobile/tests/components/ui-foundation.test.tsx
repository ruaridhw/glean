import { fireEvent, render } from "@testing-library/react-native";
import { KeyboardAvoidingView, ScrollView, Text, View } from "react-native";

jest.mock("@expo/vector-icons", () => {
  const React = require("react");
  const { Text: MockText } = require("react-native");
  return {
    Ionicons: ({ name }: { name: string }) => React.createElement(MockText, null, name),
  };
});

import { AppScreen } from "@/components/ui/AppScreen";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { IconButton } from "@/components/ui/IconButton";

jest.mock("@/platform/haptics", () => ({
  hapticImpact: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: ({ children }: { children: React.ReactNode }) => children,
  useSafeAreaInsets: () => ({ top: 0, right: 0, bottom: 0, left: 0 }),
}));

describe("UI foundation", () => {
  it("renders a screen title and subtitle", () => {
    const screen = render(
      <AppScreen title="Pantry" subtitle="4 items">
        <Text>Body</Text>
      </AppScreen>,
    );

    expect(screen.getByText("Pantry")).toBeTruthy();
    expect(screen.getByText("4 items")).toBeTruthy();
    expect(screen.getByText("Body")).toBeTruthy();
  });

  it("can wrap scrollable screens in keyboard handling", () => {
    const screen = render(
      <AppScreen title="Settings" scroll keyboardAvoiding>
        <Text>Form body</Text>
      </AppScreen>,
    );

    expect(screen.UNSAFE_getByType(KeyboardAvoidingView)).toBeTruthy();
    expect(screen.UNSAFE_getByType(ScrollView).props.keyboardDismissMode).toBe("on-drag");
    expect(screen.UNSAFE_getByType(ScrollView).props.keyboardShouldPersistTaps).toBe("handled");
  });

  it("can remove reserved bottom padding for screens with pinned bottom actions", () => {
    const screen = render(
      <AppScreen title="Shop" contentPaddingBottom={0}>
        <Text>Body</Text>
      </AppScreen>,
    );

    const body = screen
      .UNSAFE_getAllByType(View)
      .find((view) =>
        Array.isArray(view.props.style)
          ? view.props.style.some(
              (style: unknown) =>
                typeof style === "object" && style !== null && "paddingBottom" in style,
            )
          : false,
      );

    expect(body?.props.style).toContainEqual({ paddingBottom: 0 });
  });

  it("renders cards and badges", () => {
    const screen = render(
      <Card testID="card">
        <Badge label="2d left" tone="warning" testID="badge" />
      </Card>,
    );

    expect(screen.getByTestId("card")).toBeTruthy();
    expect(screen.getByTestId("badge")).toBeTruthy();
    expect(screen.getByText("2d left")).toBeTruthy();
  });

  it("fires icon button presses", () => {
    const onPress = jest.fn();
    const screen = render(
      <IconButton icon="add" accessibilityLabel="Add item" onPress={onPress} />,
    );

    fireEvent.press(screen.getByLabelText("Add item"));
    expect(onPress).toHaveBeenCalledTimes(1);
  });
});
