import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import { StyleSheet } from "react-native";
import {
  addManualShoppingItem,
  completeCheckout,
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
  completeCheckout: jest.fn().mockResolvedValue(undefined),
  deleteShoppingItem: jest.fn().mockResolvedValue(undefined),
  getShoppingListItems: jest.fn(),
  toggleShoppingItem: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/platform/haptics", () => ({ hapticImpact: jest.fn().mockResolvedValue(undefined) }));
jest.mock("@/utils/toast", () => ({ showSuccess: jest.fn() }));

type RenderedTree = string | null | { children?: RenderedTree[] | null } | RenderedTree[];

function collectRenderedText(node: RenderedTree): string[] {
  if (node === null) return [];
  if (typeof node === "string") return [node];
  if (Array.isArray(node)) return node.flatMap(collectRenderedText);
  return node.children?.flatMap(collectRenderedText) ?? [];
}

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

  it("renders grouped shopping cards and checkout action", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes")).toBeTruthy());
    expect(screen.getByText("Shopping")).toBeTruthy();
    expect(screen.getByText("1 remaining · 1 checked")).toBeTruthy();
    expect(screen.getByText("Remaining")).toBeTruthy();
    expect(screen.getByText("Checked")).toBeTruthy();
    expect(screen.getByText("2 kg")).toBeTruthy();
    expect(screen.getByText("From plan")).toBeTruthy();
    expect(screen.getByText("Completed checkout")).toBeTruthy();
  }, 15_000);

  it("renders checked rows first, remaining rows second, and checkout pinned below the list", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes")).toBeTruthy());
    const textOrder = collectRenderedText(screen.toJSON());

    expect(textOrder.indexOf("Add")).toBeGreaterThanOrEqual(0);
    expect(textOrder.indexOf("Checked")).toBeGreaterThan(textOrder.indexOf("Add"));
    expect(textOrder.indexOf("milk")).toBeGreaterThan(textOrder.indexOf("Checked"));
    expect(textOrder.indexOf("Remaining")).toBeGreaterThan(textOrder.indexOf("milk"));
    expect(textOrder.indexOf("tomatoes")).toBeGreaterThan(textOrder.indexOf("Remaining"));
    expect(StyleSheet.flatten(screen.getByTestId("shop.shoppingList").props.style)).toEqual(
      expect.objectContaining({ flex: 1 }),
    );
    expect(screen.getByTestId("shop.pinnedCheckoutActions")).toBeTruthy();
  });

  it("adds and toggles shopping items", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes")).toBeTruthy());
    fireEvent.changeText(screen.getByPlaceholderText("Add item..."), "bread");
    fireEvent.press(screen.getByText("Add"));
    await waitFor(() => expect(addManualShoppingItem).toHaveBeenCalledWith({ name: "bread" }));

    fireEvent.press(screen.getByLabelText("Check tomatoes"));
    await waitFor(() => expect(toggleShoppingItem).toHaveBeenCalledWith(1, true));
  });

  it("toggles a shopping item when tapping the row content", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes")).toBeTruthy());
    fireEvent.press(screen.getByText("tomatoes"));

    await waitFor(() => expect(toggleShoppingItem).toHaveBeenCalledWith(1, true));
  });

  it("deletes a shopping item from the trash action", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes")).toBeTruthy());
    fireEvent.press(screen.getByLabelText("Remove tomatoes"));

    await waitFor(() => expect(deleteShoppingItem).toHaveBeenCalledWith(1));
  });

  it("deletes a shopping item from a qualifying left swipe", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes")).toBeTruthy());
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

  it("highlights the delete affordance while swiping an item left", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes")).toBeTruthy());
    const row = screen.getByTestId("shopping-row-1");

    act(() => {
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
          currentPageX: 168,
          currentTimeStamp: 32,
          previousPageX: 200,
          previousTimeStamp: 1,
        }),
      });
    });

    expect(screen.getByTestId("shopping-row-delete-action-1").props.style).toContainEqual(
      expect.objectContaining({ backgroundColor: "#FEE2E2" }),
    );
    expect(screen.getByTestId("shopping-row-delete-icon-1").props.color).toBe("#EF4444");
  });

  it("deletes a shopping item from a fast left flick", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes")).toBeTruthy());
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
          currentPageX: 172,
          currentTimeStamp: 12,
          previousPageX: 200,
          previousTimeStamp: 1,
        }),
      });
      row.props.onResponderRelease({
        nativeEvent: {},
        touchHistory: createTouchHistory({
          currentPageX: 172,
          currentTimeStamp: 12,
          previousPageX: 200,
          previousTimeStamp: 1,
        }),
      });
    });

    await waitFor(() => expect(deleteShoppingItem).toHaveBeenCalledWith(1));
  });

  it("keeps checkout and receipt-scan handoff available", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("Completed checkout")).toBeTruthy());
    fireEvent.press(screen.getByText("Scan receipt"));
    expect(router.push).toHaveBeenCalledWith("/(tabs)/pantry/scan?returnTo=shop");

    fireEvent.press(screen.getByText("Clear checked"));
    await waitFor(() => expect(completeCheckout).toHaveBeenCalled());
  });

  it("opens the nested describe screen from the Shop list", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes")).toBeTruthy());
    fireEvent.press(screen.getByText("Describe"));

    expect(router.push).toHaveBeenCalledWith("/(tabs)/shop/describe");
  });
});
