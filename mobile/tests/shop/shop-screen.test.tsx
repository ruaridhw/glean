import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
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
  return { Ionicons: ({ name }: { name: string }) => React.createElement(Text, null, name) };
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

  it("adds, toggles, and deletes shopping items", async () => {
    const screen = render(<ShopScreen />);

    await waitFor(() => expect(screen.getByText("tomatoes")).toBeTruthy());
    fireEvent.changeText(screen.getByPlaceholderText("Add item..."), "bread");
    fireEvent.press(screen.getByText("Add"));
    await waitFor(() => expect(addManualShoppingItem).toHaveBeenCalledWith({ name: "bread" }));

    fireEvent.press(screen.getByLabelText("Check tomatoes"));
    await waitFor(() => expect(toggleShoppingItem).toHaveBeenCalledWith(1, true));

    fireEvent.press(screen.getByLabelText("Remove tomatoes"));
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
