import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import ImportScreen from "../../app/(tabs)/meals/import";
import SearchScreen from "../../app/(tabs)/meals/search";
import { apiClient } from "@/api/client";
import { useRecipeSearch } from "@/api/hooks";
import { getRecipeByExternalId, saveRecipe } from "@/db/recipes";

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
  router: { push: jest.fn() },
}));

jest.mock("@/api/hooks", () => ({
  useRecipeSearch: jest.fn(),
}));

jest.mock("@/api/client", () => ({
  apiClient: { get: jest.fn(), post: jest.fn() },
}));

jest.mock("@/db/recipes", () => ({
  getRecipeByExternalId: jest.fn(),
  saveRecipe: jest.fn(),
}));

jest.mock("@/utils/toast", () => ({
  showSuccess: jest.fn(),
}));

describe("Meals search and import screens", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useRecipeSearch as jest.Mock).mockReturnValue({
      data: {
        results: [
          {
            external_id: "ext-1",
            title: "Miso Soup",
            cuisine: "Japanese",
            difficulty: "easy",
            total_time_mins: 20,
          },
        ],
      },
      isLoading: false,
      isError: false,
      refetch: jest.fn(),
    });
    (getRecipeByExternalId as jest.Mock).mockResolvedValue(null);
    (apiClient.get as jest.Mock).mockResolvedValue({
      title: "Miso Soup",
      ingredients: [],
      instructions: [],
    });
    (apiClient.post as jest.Mock).mockResolvedValue({
      title: "Imported Soup",
      ingredients: [],
      instructions: [],
    });
    (saveRecipe as jest.Mock).mockResolvedValue(12);
  });

  it("renders search results as cards and saves selected recipe", async () => {
    const screen = render(<SearchScreen />);

    expect(screen.getByText("Discover Recipes")).toBeTruthy();
    expect(screen.getByText("Miso Soup")).toBeTruthy();
    expect(screen.getByText("Japanese")).toBeTruthy();
    fireEvent.press(screen.getByText("Miso Soup"));

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith("/recipes/ext-1"));
    expect(saveRecipe).toHaveBeenCalledWith(expect.objectContaining({ title: "Miso Soup" }));
    expect(router.push).toHaveBeenCalledWith("/(tabs)/meals/12");
  });

  it("imports a recipe URL through the real import endpoint", async () => {
    const screen = render(<ImportScreen />);

    expect(screen.getByText("Import from URL")).toBeTruthy();
    fireEvent.changeText(screen.getByPlaceholderText("https://..."), "https://example.com/recipe");
    fireEvent.press(screen.getByText("Import"));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/recipes/import-url", {
        url: "https://example.com/recipe",
      }),
    );
    expect(saveRecipe).toHaveBeenCalledWith(expect.objectContaining({ title: "Imported Soup" }));
    expect(router.push).toHaveBeenCalledWith("/(tabs)/meals/12");
  });
});
