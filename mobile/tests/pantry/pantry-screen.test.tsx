import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import { deletePantryItem, getPantryItems, updatePantryQuantity } from "@/db/pantry";
import PantryScreen from "../../app/(tabs)/pantry";

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

jest.mock("@/db/pantry", () => ({
  getPantryItems: jest.fn(),
  updatePantryQuantity: jest.fn().mockResolvedValue(undefined),
  deletePantryItem: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/platform/haptics", () => ({
  hapticImpact: jest.fn().mockResolvedValue(undefined),
}));

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

describe("PantryScreen", () => {
  jest.setTimeout(15_000);

  beforeEach(() => {
    jest.clearAllMocks();
    (getPantryItems as jest.Mock).mockResolvedValue([
      {
        id: 1,
        ingredient_id: 10,
        quantity: 2,
        unit: "kg",
        unit_price: null,
        expiry_date: "2026-05-04",
        last_used_at: null,
        updated_at: "2026-05-02T00:00:00Z",
        canonical_name: "broccoli",
        is_staple: false,
        food_group: "vegetables",
      },
      {
        id: 2,
        ingredient_id: 11,
        quantity: 1,
        unit: "L",
        unit_price: null,
        expiry_date: null,
        last_used_at: null,
        updated_at: "2026-05-02T00:00:00Z",
        canonical_name: "milk",
        is_staple: false,
        food_group: "dairy",
      },
    ]);
  });

  it("renders grouped pantry cards with real data", async () => {
    const screen = render(<PantryScreen />);

    await waitFor(() => expect(screen.getByText("broccoli")).toBeTruthy());
    expect(screen.getByText("Pantry")).toBeTruthy();
    expect(screen.getByText("2 items")).toBeTruthy();
    expect(screen.getByText("Veg & Fruit")).toBeTruthy();
    expect(screen.getByText("Dairy")).toBeTruthy();
    expect(screen.getByText("2 kg")).toBeTruthy();
    expect(screen.getByText("1 L")).toBeTruthy();
  });

  it("opens the add pantry flow when the pantry has items", async () => {
    const screen = render(<PantryScreen />);

    await waitFor(() => expect(screen.getByText("broccoli")).toBeTruthy());
    fireEvent.press(screen.getByLabelText("Add pantry item"));

    expect(router.push).toHaveBeenCalledWith("/(tabs)/pantry/add");
  });

  it("opens the add pantry flow from the empty state header", async () => {
    (getPantryItems as jest.Mock).mockResolvedValueOnce([]);
    const screen = render(<PantryScreen />);

    await waitFor(() => expect(screen.getByText("Your pantry is empty")).toBeTruthy());
    expect(screen.getByText("Scan receipt")).toBeTruthy();
    expect(screen.getByText("Describe items")).toBeTruthy();

    fireEvent.press(screen.getByLabelText("Add pantry item"));

    expect(router.push).toHaveBeenCalledWith("/(tabs)/pantry/add");
  });

  it("commits quantity edits", async () => {
    const screen = render(<PantryScreen />);

    await waitFor(() => expect(screen.getByText("broccoli")).toBeTruthy());
    fireEvent.press(screen.getByText("2 kg"));
    fireEvent.changeText(screen.getByDisplayValue("2"), "3");
    fireEvent(screen.getByDisplayValue("3"), "blur");

    await waitFor(() => expect(updatePantryQuantity).toHaveBeenCalledWith(1, 3));
  });

  it("deletes pantry items through the card action", async () => {
    const screen = render(<PantryScreen />);

    await waitFor(() => expect(screen.getByText("broccoli")).toBeTruthy());
    fireEvent.press(screen.getByLabelText("Remove broccoli"));

    await waitFor(() => expect(deletePantryItem).toHaveBeenCalledWith(1));
  });

  it("filters rows to a single category when its chip is pressed", async () => {
    (getPantryItems as jest.Mock).mockResolvedValue([
      {
        id: 1,
        ingredient_id: 10,
        quantity: 2,
        unit: "kg",
        unit_price: null,
        expiry_date: null,
        last_used_at: null,
        updated_at: "2026-05-02T00:00:00Z",
        canonical_name: "broccoli",
        is_staple: false,
        food_group: "vegetables",
      },
      {
        id: 3,
        ingredient_id: 12,
        quantity: 3,
        unit: "whole",
        unit_price: null,
        expiry_date: null,
        last_used_at: null,
        updated_at: "2026-05-02T00:00:00Z",
        canonical_name: "carrots",
        is_staple: false,
        food_group: "vegetables",
      },
      {
        id: 2,
        ingredient_id: 11,
        quantity: 1,
        unit: "L",
        unit_price: null,
        expiry_date: null,
        last_used_at: null,
        updated_at: "2026-05-02T00:00:00Z",
        canonical_name: "milk",
        is_staple: false,
        food_group: "dairy",
      },
    ]);

    const screen = render(<PantryScreen />);

    await waitFor(() => expect(screen.getByText("broccoli")).toBeTruthy());
    // Chips use short category names + per-category counts, plus the "All · N" chip.
    expect(screen.getByText("All · 3")).toBeTruthy();
    expect(screen.getByText("Veg 2")).toBeTruthy();
    expect(screen.getByText("Dairy 1")).toBeTruthy();
    // Everything visible before filtering.
    expect(screen.getByText("milk")).toBeTruthy();

    fireEvent.press(screen.getByText("Veg 2"));

    await waitFor(() => expect(screen.queryByText("milk")).toBeNull());
    expect(screen.getByText("broccoli")).toBeTruthy();
    expect(screen.getByText("carrots")).toBeTruthy();
  });

  it("deletes pantry items from a qualifying left swipe", async () => {
    const screen = render(<PantryScreen />);

    await waitFor(() => expect(screen.getByText("broccoli")).toBeTruthy());
    const row = screen.getByTestId("pantry-row-1");

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

    await waitFor(() => expect(deletePantryItem).toHaveBeenCalledWith(1));
  });
});
