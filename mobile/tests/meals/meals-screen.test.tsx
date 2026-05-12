import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import MealsScreen from "../../app/(tabs)/meals";
import { getSavedRecipes } from "@/db/recipes";

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

jest.mock("@/db/recipes", () => ({
  getSavedRecipes: jest.fn(),
}));

jest.mock("@/platform/haptics", () => ({
  hapticImpact: jest.fn().mockResolvedValue(undefined),
}));

describe("MealsScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getSavedRecipes as jest.Mock).mockResolvedValue([
      {
        id: 7,
        title: "Tomato Pasta",
        cuisine: "Italian",
        difficulty: "easy",
        active_time_mins: 15,
        total_time_mins: 30,
        not_suitable_for: [],
        yield_count: 4,
        nutrition: null,
        instructions: [],
        last_cooked_at: null,
        is_ai_generated: false,
        dietary_flags: ["Vegetarian"],
      },
    ]);
  });

  it("renders Replit-style saved recipe cards over real recipes", async () => {
    const screen = render(<MealsScreen />);

    await waitFor(() => expect(screen.getByText("Tomato Pasta")).toBeTruthy());
    expect(screen.getByText("Meals")).toBeTruthy();
    expect(screen.getByText("Saved (1)")).toBeTruthy();
    expect(screen.getByText("Search")).toBeTruthy();
    expect(screen.getByText("30 min")).toBeTruthy();
    expect(screen.getByText("4 servings")).toBeTruthy();
    expect(screen.getByText("Italian")).toBeTruthy();
  });

  it("navigates to recipe detail from a card", async () => {
    const screen = render(<MealsScreen />);

    await waitFor(() => expect(screen.getByText("Tomato Pasta")).toBeTruthy());
    fireEvent.press(screen.getByText("Tomato Pasta"));
    expect(router.push).toHaveBeenCalledWith("/(tabs)/meals/7");
  });

  it("shows empty state actions for search and import", async () => {
    (getSavedRecipes as jest.Mock).mockResolvedValueOnce([]);
    const screen = render(<MealsScreen />);

    await waitFor(() => expect(screen.getByText("No saved recipes")).toBeTruthy());
    expect(screen.getByText("Search recipes")).toBeTruthy();
    expect(screen.getByText("Import from URL")).toBeTruthy();
  });
});
