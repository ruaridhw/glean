import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router, useLocalSearchParams } from "expo-router";
import { getIngredientById, resolveOrCreateIngredient } from "@/db/ingredients";
import { upsertPantryItem } from "@/db/pantry";
import { checkOffByIngredientIds } from "@/db/shopping";
import { completeOnboarding } from "@/onboarding/storage";
import ReviewScreen from "../../app/(tabs)/pantry/review";

jest.mock("expo-router", () => ({
  router: { replace: jest.fn() },
  useLocalSearchParams: jest.fn(),
}));

jest.mock("@/db/ingredients", () => ({
  getIngredientById: jest.fn(),
  resolveOrCreateIngredient: jest.fn(),
}));

jest.mock("@/db/pantry", () => ({
  upsertPantryItem: jest.fn(),
}));

jest.mock("@/db/shopping", () => ({
  checkOffByIngredientIds: jest.fn(),
  completeCheckout: jest.fn(),
}));

jest.mock("@/onboarding/storage", () => ({
  completeOnboarding: jest.fn(),
}));

jest.mock("@/utils/toast", () => ({
  showSuccess: jest.fn(),
}));

describe("ReviewScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useLocalSearchParams as jest.Mock).mockReturnValue({
      items: JSON.stringify([
        { name: "eggs", quantity: 6, unit: "units", unit_price: null, confidence: 0.95 },
      ]),
      onboarding: "true",
    });
    (resolveOrCreateIngredient as jest.Mock).mockResolvedValue(42);
    (getIngredientById as jest.Mock).mockResolvedValue({
      id: 42,
      canonical_name: "eggs",
      canonical_unit: "units",
    });
    (upsertPantryItem as jest.Mock).mockResolvedValue(undefined);
    (checkOffByIngredientIds as jest.Mock).mockResolvedValue(undefined);
    (completeOnboarding as jest.Mock).mockResolvedValue(undefined);
  });

  it("marks onboarding complete after confirming onboarding review items", async () => {
    const screen = render(<ReviewScreen />);

    fireEvent.press(screen.getByText("Confirm 1 item"));

    await waitFor(() => expect(upsertPantryItem).toHaveBeenCalledTimes(1));
    expect(completeOnboarding).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith("/(tabs)/pantry");
  });
});
