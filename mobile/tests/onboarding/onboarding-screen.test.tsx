import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import { useDescribeReceipt } from "@/api/hooks";
import { completeOnboarding } from "@/onboarding/storage";
import OnboardingScreen from "../../app/onboarding";

jest.mock("@expo/vector-icons", () => {
  const React = require("react");
  const { Text } = require("react-native");
  return {
    Ionicons: ({ name, ...props }: { name: string }) => React.createElement(Text, props, name),
  };
});

jest.mock("expo-router", () => ({
  router: {
    push: jest.fn(),
    replace: jest.fn(),
  },
}));

jest.mock("@/api/hooks", () => ({
  useDescribeReceipt: jest.fn(),
}));

jest.mock("@/onboarding/storage", () => ({
  completeOnboarding: jest.fn(),
}));

const mutate = jest.fn();

describe("OnboardingScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (completeOnboarding as jest.Mock).mockResolvedValue(undefined);
    (useDescribeReceipt as jest.Mock).mockReturnValue({
      isError: false,
      isPending: false,
      mutate,
      reset: jest.fn(),
    });
  });

  it("walks through the three onboarding cards before pantry setup", () => {
    const screen = render(<OnboardingScreen />);

    expect(screen.getByText("Stock your pantry from a receipt")).toBeTruthy();
    expect(screen.getByTestId("onboarding.dot.0").props.accessibilityState.selected).toBe(true);

    fireEvent.press(screen.getByText("Next"));
    expect(screen.getByText("Plan meals around what you have")).toBeTruthy();
    expect(screen.getByTestId("onboarding.dot.1").props.accessibilityState.selected).toBe(true);

    fireEvent.press(screen.getByText("Next"));
    expect(screen.getByText("Shop only for the gaps")).toBeTruthy();
    expect(screen.getByTestId("onboarding.dot.2").props.accessibilityState.selected).toBe(true);

    fireEvent.press(screen.getByText("Get started"));
    expect(screen.getByText("What do you have at home?")).toBeTruthy();
  });

  it("does not submit an empty pantry description", () => {
    const screen = render(<OnboardingScreen />);

    fireEvent.press(screen.getByText("Next"));
    fireEvent.press(screen.getByText("Next"));
    fireEvent.press(screen.getByText("Get started"));
    fireEvent.press(screen.getByText("Review items"));

    expect(mutate).not.toHaveBeenCalled();
  });

  it("parses typed pantry text and routes to review without completing onboarding first", async () => {
    mutate.mockImplementationOnce(
      (_text: string, options: { onSuccess: (result: unknown) => void }) => {
        options.onSuccess({
          items: [{ name: "eggs", quantity: 6, unit: "units", unit_price: null, confidence: 0.95 }],
        });
      },
    );

    const screen = render(<OnboardingScreen />);

    fireEvent.press(screen.getByText("Next"));
    fireEvent.press(screen.getByText("Next"));
    fireEvent.press(screen.getByText("Get started"));
    fireEvent.changeText(
      screen.getByPlaceholderText("eggs, milk, some chicken in the freezer"),
      "eggs and milk",
    );
    fireEvent.press(screen.getByText("Review items"));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith({
        pathname: "/(tabs)/pantry/review",
        params: {
          items: JSON.stringify([
            { name: "eggs", quantity: 6, unit: "units", unit_price: null, confidence: 0.95 },
          ]),
          onboarding: "true",
        },
      }),
    );
    expect(completeOnboarding).not.toHaveBeenCalled();
  });

  it("can skip pantry setup and enter the app", async () => {
    const screen = render(<OnboardingScreen />);

    fireEvent.press(screen.getByText("Next"));
    fireEvent.press(screen.getByText("Next"));
    fireEvent.press(screen.getByText("Get started"));
    fireEvent.press(screen.getByText("Skip for now"));

    await waitFor(() => expect(completeOnboarding).toHaveBeenCalledTimes(1));
    expect(router.replace).toHaveBeenCalledWith("/(tabs)/pantry");
  });
});
