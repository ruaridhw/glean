import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import ShoppingReviewScreen from "../../../app/(tabs)/shop/review";

const mockReplace = jest.fn();

jest.mock("expo-router", () => ({
  router: { replace: (...args: unknown[]) => mockReplace(...args) },
  useLocalSearchParams: () => ({
    items: JSON.stringify([
      {
        name: "taco shells",
        quantity: 1,
        unit: "pack",
        unit_price: null,
        api_ingredient_id: "taco-shells",
        category: "bakery",
        confidence: 0.82,
      },
      {
        name: "whole milk",
        quantity: 1,
        unit: "bottle",
        unit_price: null,
        api_ingredient_id: null,
        category: "dairy",
        confidence: 0.91,
      },
    ]),
    clarifyingQuestions: JSON.stringify(["What lunchbox snacks do you want?"]),
  }),
}));

jest.mock("@expo/vector-icons", () => ({
  Ionicons: ({ name }: { name: string }) => {
    const { Text } = require("react-native");
    return <Text>{name}</Text>;
  },
}));

const mockAddAiShoppingItems = jest.fn();

jest.mock("@/db/shopping", () => ({
  addAiShoppingItems: (...args: unknown[]) => mockAddAiShoppingItems(...args),
}));

jest.mock("@/utils/toast", () => ({
  showSuccess: jest.fn(),
}));

describe("ShoppingReviewScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAddAiShoppingItems.mockResolvedValue(undefined);
  });

  it("saves accepted proposals to the local shopping list", async () => {
    const { getByText } = render(
      <SafeAreaProvider
        initialMetrics={{
          frame: { x: 0, y: 0, width: 390, height: 844 },
          insets: { top: 0, right: 0, bottom: 0, left: 0 },
        }}
      >
        <ShoppingReviewScreen />
      </SafeAreaProvider>,
    );

    fireEvent.press(getByText("Add 2 items"));

    await waitFor(() => {
      expect(mockAddAiShoppingItems).toHaveBeenCalledWith([
        {
          name: "taco shells",
          quantity: 1,
          unit: "pack",
          api_ingredient_id: "taco-shells",
          category: "bakery",
        },
        {
          name: "whole milk",
          quantity: 1,
          unit: "bottle",
          api_ingredient_id: null,
          category: "dairy",
        },
      ]);
    });
    expect(mockReplace).toHaveBeenCalledWith("/(tabs)/shop");
  });
});
