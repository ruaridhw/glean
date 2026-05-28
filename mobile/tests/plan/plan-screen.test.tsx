import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import { useSuggestMeals } from "@/api/hooks";
import { getUserConfig } from "@/db/config";
import { getPantryItems } from "@/db/pantry";
import {
  addMealPlanEntry,
  deleteMealPlanEntry,
  getMealPlanEntries,
  markMealAsCooked,
} from "@/db/plan";
import { getSavedRecipes } from "@/db/recipes";
import { addShoppingGapsForRecipe } from "@/db/shopping";
import PlanScreen from "../../app/(tabs)/plan";

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
    useLocalSearchParams: () => ({}),
  };
});

jest.mock("@/api/hooks", () => ({ useSuggestMeals: jest.fn() }));
jest.mock("@/db/config", () => ({ getUserConfig: jest.fn() }));
jest.mock("@/db/pantry", () => ({ getPantryItems: jest.fn() }));
jest.mock("@/db/plan", () => ({
  addMealPlanEntry: jest.fn().mockResolvedValue(3),
  deleteMealPlanEntry: jest.fn().mockResolvedValue(undefined),
  getMealPlanCount: jest.fn().mockResolvedValue(1),
  getMealPlanEntries: jest.fn(),
  markMealAsCooked: jest.fn().mockResolvedValue(undefined),
}));
jest.mock("@/db/recipes", () => ({ getSavedRecipes: jest.fn() }));
jest.mock("@/db/shopping", () => ({
  addShoppingGapsForRecipe: jest.fn().mockResolvedValue(undefined),
}));
jest.mock("@/suggestions/compress", () => ({ compressPantry: jest.fn().mockReturnValue([]) }));
jest.mock("@/utils/toast", () => ({ showError: jest.fn(), showSuccess: jest.fn() }));
jest.mock("@/platform/haptics", () => ({ hapticImpact: jest.fn().mockResolvedValue(undefined) }));

describe("PlanScreen", () => {
  const mutate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mutate.mockImplementation((_payload, callbacks) => {
      callbacks.onSuccess({ suggestions: [{ recipe_id: 10 }] });
    });
    (useSuggestMeals as jest.Mock).mockReturnValue({ mutate, reset: jest.fn(), isPending: false });
    (getMealPlanEntries as jest.Mock).mockResolvedValue([
      {
        id: 1,
        recipe_id: 7,
        planned_date: "2026-05-12",
        cooked_at: null,
        servings: 1,
        recipe_title: "Tomato Pasta",
      },
    ]);
    (getUserConfig as jest.Mock).mockResolvedValue({
      id: "user",
      purchase_tolerance: 0.5,
      preferred_servings: 2,
      meals_per_week: 3,
      dietary_flags: [],
      max_active_time_mins: null,
    });
    (getPantryItems as jest.Mock).mockResolvedValue([]);
    (getSavedRecipes as jest.Mock).mockResolvedValue([
      {
        id: 10,
        title: "Miso Soup",
        not_suitable_for: [],
        instructions: [],
        is_ai_generated: false,
      },
    ]);
  });

  it("renders progress and dinner slots", async () => {
    const screen = render(<PlanScreen />);

    await waitFor(() => expect(screen.getByText("Tomato Pasta")).toBeTruthy());
    expect(screen.getByText("This Week")).toBeTruthy();
    expect(screen.getByText("1 of 3 dinners")).toBeTruthy();
    expect(screen.getAllByText("Add dinner")).toHaveLength(2);
  }, 15_000);

  it("marks an entry cooked and deletes entries", async () => {
    const screen = render(<PlanScreen />);

    await waitFor(() => expect(screen.getByText("Tomato Pasta")).toBeTruthy());
    fireEvent.press(screen.getByText("Cooked"));
    await waitFor(() => expect(markMealAsCooked).toHaveBeenCalledWith(1));

    fireEvent.press(screen.getByLabelText("Remove Tomato Pasta"));
    await waitFor(() => expect(deleteMealPlanEntry).toHaveBeenCalledWith(1));
  });

  it("generates a week using existing suggestion and shopping gap flow", async () => {
    const screen = render(<PlanScreen />);

    await waitFor(() => expect(screen.getByText("Generate plan")).toBeTruthy());
    fireEvent.press(screen.getByText("Generate plan"));

    await waitFor(() => expect(mutate).toHaveBeenCalled());
    expect(addMealPlanEntry).toHaveBeenCalledWith(10);
    expect(addShoppingGapsForRecipe).toHaveBeenCalledWith(10);
  });

  it("navigates empty slots to recipe search", async () => {
    const screen = render(<PlanScreen />);

    await waitFor(() => expect(screen.getAllByText("Add dinner")[0]).toBeTruthy());
    fireEvent.press(screen.getAllByText("Add dinner")[0]!);
    expect(router.push).toHaveBeenCalledWith("/(tabs)/meals/search");
  });
});
