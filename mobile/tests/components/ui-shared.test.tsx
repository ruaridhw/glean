import { fireEvent, render } from "@testing-library/react-native";
import { Text } from "react-native";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { StatsRow } from "@/components/ui/StatsRow";

jest.mock("@expo/vector-icons", () => {
  const React = require("react");
  const { Text } = require("react-native");
  return {
    Ionicons: ({ name }: { name: string }) => React.createElement(Text, null, name),
  };
});

jest.mock("@/platform/haptics", () => ({
  hapticImpact: jest.fn().mockResolvedValue(undefined),
}));

describe("shared UI primitives", () => {
  it("renders segmented control options and selects by value", () => {
    const onChange = jest.fn();
    const screen = render(
      <SegmentedControl
        value="saved"
        onChange={onChange}
        options={[
          { value: "saved", label: "Saved", icon: "bookmark" },
          { value: "planned", label: "Planned", icon: "calendar-outline" },
        ]}
      />,
    );

    expect(screen.getByText("Saved")).toBeTruthy();
    expect(screen.getByText("Planned")).toBeTruthy();
    fireEvent.press(screen.getByText("Planned"));
    expect(onChange).toHaveBeenCalledWith("planned");
  });

  it("renders section header with optional action", () => {
    const onPress = jest.fn();
    const screen = render(
      <SectionHeader
        title="Preferences"
        subtitle="Used for meal planning"
        actionLabel="Edit"
        onAction={onPress}
      />,
    );

    expect(screen.getByText("Preferences")).toBeTruthy();
    expect(screen.getByText("Used for meal planning")).toBeTruthy();
    fireEvent.press(screen.getByText("Edit"));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it("renders stats row values and labels", () => {
    const screen = render(
      <StatsRow
        stats={[
          { value: "4", label: "Pantry" },
          { value: "2", label: "Planned" },
        ]}
      />,
    );

    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText("Pantry")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText("Planned")).toBeTruthy();
  });

  it("allows custom stat content", () => {
    const screen = render(<StatsRow stats={[{ value: <Text>80%</Text>, label: "Progress" }]} />);
    expect(screen.getByText("80%")).toBeTruthy();
  });
});
