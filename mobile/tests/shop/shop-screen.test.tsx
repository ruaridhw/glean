import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import {
  addManualShoppingItem,
  deleteShoppingItem,
  getShoppingListItems,
  toggleShoppingItem,
} from "@/db/shopping";
import ShopScreen from "../../app/(tabs)/shop";

jest.mock("@expo/vector-icons", () => {
  const React = require("react");
  const { Text } = require("react-native");
  return {
    Ionicons: ({ name, ...props }: { name: string }) => React.createElement(Text, props, name),
  };
});

jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: ({ children }: { children: React.ReactNode }) => children,
  useSafeAreaInsets: () => ({ top: 0, right: 0, bottom: 0, left: 0 }),
}));

jest.mock("expo-router", () => {
  const React = require("react");
  return {
    router: { push: jest.fn() },
    useFocusEffect: (callback: () => void) => React.useEffect(callback, [callback]),
  };
});

jest.mock("@/db/shopping", () => ({
  addManualShoppingItem: jest.fn().mockResolvedValue(undefined),
  deleteShoppingItem: jest.fn().mockResolvedValue(undefined),
  getShoppingListItems: jest.fn(),
  toggleShoppingItem: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/platform/haptics", () => ({ hapticImpact: jest.fn().mockResolvedValue(undefined) }));
jest.mock("@/utils/toast", () => ({ showSuccess: jest.fn() }));

function createTouchHistory({
  currentPageX,
  currentPageY = 20,
  currentTimeStamp,
  previousPageX,
  previousPageY = 20,
  previousTimeStamp,
}: {
  currentPageX: number;
  currentPageY?: number;
  currentTimeStamp: number;
  previousPageX: number;
  previousPageY?: number;
  previousTimeStamp: number;
}) {
  return {
    indexOfSingleActiveTouch: 0,
    mostRecentTimeStamp: currentTimeStamp,
    numberActiveTouches: 1,
    touchBank: [
      {
        currentPageX,
        currentPageY,
        currentTimeStamp,
        previousPageX,
        previousPageY,
        previousTimeStamp,
        touchActive: true,
      },
    ],
  };
}

describe("ShopScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getShoppingListItems as jest.Mock).mockResolvedValue([
      {
        id: 1,
        ingredient_id: null,
        name: "tomatoes",
        quantity: 2,
        unit: "kg",
        source: "meal_plan",
        is_checked: false,
      },
      {
        id: 2,
        ingredient_id: null,
        name: "milk",
        quantity: 1,
        unit: "L",
        source: "manual",
        is_checked: true,
      },
    ]);
  });

  it("renders grouped shopping sections, counts, source badge and checkout bar", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes · 2 kg")).toBeTruthy());
    expect(screen.getByText("Shopping")).toBeTruthy();
    expect(screen.getByText("1 to buy")).toBeTruthy();
    expect(screen.getByText("1 checked")).toBeTruthy();
    expect(screen.getByText("To buy")).toBeTruthy();
    expect(screen.getByText("In your cart")).toBeTruthy();
    expect(screen.getByText("Plan")).toBeTruthy();
    expect(screen.getByText("milk · 1 L")).toBeTruthy();
    expect(screen.getByTestId("shop.pinnedCheckoutActions")).toBeTruthy();
    expect(screen.getByText("1 item in cart")).toBeTruthy();
  }, 15_000);

  it("adds a manual item and toggles an item checked", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes · 2 kg")).toBeTruthy());
    fireEvent.changeText(screen.getByPlaceholderText("Add item…"), "bread");
    fireEvent.press(screen.getByTestId("shop.addButton"));
    await waitFor(() => expect(addManualShoppingItem).toHaveBeenCalledWith({ name: "bread" }));

    fireEvent.press(screen.getByLabelText("Check tomatoes"));
    await waitFor(() => expect(toggleShoppingItem).toHaveBeenCalledWith(1, true));
  });

  it("toggles a shopping item when tapping the row content", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes · 2 kg")).toBeTruthy());
    fireEvent.press(screen.getByText("tomatoes · 2 kg"));

    await waitFor(() => expect(toggleShoppingItem).toHaveBeenCalledWith(1, true));
  });

  it("removes a checked cart item from its remove control", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("milk · 1 L")).toBeTruthy());
    fireEvent.press(screen.getByLabelText("Remove milk"));

    await waitFor(() => expect(deleteShoppingItem).toHaveBeenCalledWith(2));
  });

  it("deletes a shopping item from a qualifying left swipe", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes · 2 kg")).toBeTruthy());
    const row = screen.getByTestId("shopping-row-1");

    await act(async () => {
      row.props.onResponderGrant({
        nativeEvent: {},
        touchHistory: createTouchHistory({
          currentPageX: 200,
          currentTimeStamp: 1,
          previousPageX: 200,
          previousTimeStamp: 1,
        }),
      });
      row.props.onResponderMove({
        nativeEvent: {},
        touchHistory: createTouchHistory({
          currentPageX: 128,
          currentTimeStamp: 64,
          previousPageX: 200,
          previousTimeStamp: 1,
        }),
      });
      row.props.onResponderRelease({
        nativeEvent: {},
        touchHistory: createTouchHistory({
          currentPageX: 128,
          currentTimeStamp: 64,
          previousPageX: 200,
          previousTimeStamp: 1,
        }),
      });
    });

    await waitFor(() => expect(deleteShoppingItem).toHaveBeenCalledWith(1));
  });

  it("hands off to the receipt scan flow from the checkout bar", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("Scan receipt")).toBeTruthy());
    fireEvent.press(screen.getByText("Scan receipt"));
    expect(router.push).toHaveBeenCalledWith("/(tabs)/pantry/scan?returnTo=shop");
  });

  it("opens the nested describe screen from the header action", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes · 2 kg")).toBeTruthy());
    fireEvent.press(screen.getByLabelText("Describe list"));

    expect(router.push).toHaveBeenCalledWith("/(tabs)/shop/describe");
  });
});
