import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import { getRecipeById, getRecipeIngredients } from "@/db/recipes";
import { getPantryIngredientIds } from "@/meals/pantry-match";
import RecipeDetailScreen from "../../app/(tabs)/meals/[id]";

jest.mock("@expo/vector-icons", () => {
  const React = require("react");
  const { Text } = require("react-native");
  return { Ionicons: ({ name }: { name: string }) => React.createElement(Text, null, name) };
});

jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: ({ children }: { children: React.ReactNode }) => children,
  useSafeAreaInsets: () => ({ top: 0, right: 0, bottom: 0, left: 0 }),
}));

jest.mock("expo-router", () => ({
  router: { back: jest.fn(), push: jest.fn() },
  useLocalSearchParams: () => ({ id: "7" }),
}));

jest.mock("@/db/recipes", () => ({
  getRecipeById: jest.fn(),
  getRecipeIngredients: jest.fn(),
}));

jest.mock("@/meals/pantry-match", () => ({
  getPantryIngredientIds: jest.fn(),
}));

jest.mock("@/platform/haptics", () => ({
  hapticImpact: jest.fn().mockResolvedValue(undefined),
}));

describe("RecipeDetailScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getPantryIngredientIds as jest.Mock).mockResolvedValue(new Set([2]));
    (getRecipeById as jest.Mock).mockResolvedValue({
      id: 7,
      title: "Tomato Pasta",
      cuisine: "Italian",
      difficulty: "easy",
      active_time_mins: 15,
      total_time_mins: 30,
      not_suitable_for: [],
      yield_count: 4,
      nutrition: null,
      instructions: [{ step_number: 1, phase: "cook", text: "Boil pasta" }],
      last_cooked_at: null,
      dietary_flags: ["Vegetarian"],
    });
    (getRecipeIngredients as jest.Mock).mockResolvedValue([
      {
        id: 1,
        recipe_id: 7,
        ingredient_id: 2,
        quantity: 2,
        unit: "whole",
        preparation: "chopped",
        is_optional: false,
        substitutions: [],
        ingredient: { id: 2, canonical_name: "tomato", is_staple: false },
      },
    ]);
  });

  it("renders Replit-style detail sections from real recipe data", async () => {
    const screen = render(<RecipeDetailScreen />);

    await waitFor(() => expect(screen.getByText("Tomato Pasta")).toBeTruthy());
    expect(screen.getByText("30 min")).toBeTruthy();
    expect(screen.getByText("Serves")).toBeTruthy();
    expect(screen.getByText("Ingredients")).toBeTruthy();
    expect(screen.getByText("2 whole tomato, chopped")).toBeTruthy();
    expect(screen.getByText("in pantry")).toBeTruthy();
    expect(screen.getByText("Instructions")).toBeTruthy();
    expect(screen.getByText("Boil pasta")).toBeTruthy();
  });

  it("shows a 'to buy' chip for an ingredient absent from the pantry", async () => {
    (getPantryIngredientIds as jest.Mock).mockResolvedValue(new Set([99]));
    const screen = render(<RecipeDetailScreen />);

    await waitFor(() => expect(screen.getByText("Tomato Pasta")).toBeTruthy());
    expect(screen.getByText("to buy")).toBeTruthy();
    expect(screen.queryByText("in pantry")).toBeNull();
  });

  it("hides pantry chips when the pantry lookup rejects (graceful degrade)", async () => {
    (getPantryIngredientIds as jest.Mock).mockRejectedValue(new Error("db unavailable"));
    const screen = render(<RecipeDetailScreen />);

    await waitFor(() => expect(screen.getByText("Tomato Pasta")).toBeTruthy());
    expect(screen.queryByText("in pantry")).toBeNull();
    expect(screen.queryByText("to buy")).toBeNull();
  });

  it("keeps add-to-plan handoff", async () => {
    const screen = render(<RecipeDetailScreen />);

    await waitFor(() => expect(screen.getByText("Add to plan")).toBeTruthy());
    fireEvent.press(screen.getByText("Add to plan"));
    expect(router.push).toHaveBeenCalledWith({
      pathname: "/(tabs)/plan",
      params: { add_recipe_id: "7" },
    });
  });
});
