import { apiClient } from "@/api/client";
import { addMealPlanEntry } from "@/db/plan";
import { getRecipeByExternalId, saveRecipe } from "@/db/recipes";
import { addShoppingGapsForRecipe } from "@/db/shopping";
import { planSuggestions } from "@/meal-plan/apply";

jest.mock("@/api/client", () => ({ apiClient: { get: jest.fn() } }));
jest.mock("@/db/recipes", () => ({ getRecipeByExternalId: jest.fn(), saveRecipe: jest.fn() }));
jest.mock("@/db/plan", () => ({ addMealPlanEntry: jest.fn().mockResolvedValue(1) }));
jest.mock("@/db/shopping", () => ({
  addShoppingGapsForRecipe: jest.fn().mockResolvedValue(undefined),
}));

const suggestion = (fields: { recipe_id?: number | null; external_id?: string | null }) => ({
  recipe_id: null,
  external_id: null,
  title: "Recipe",
  reason: "Uses the pantry.",
  missing_ingredients: [],
  ...fields,
});

describe("planSuggestions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("fetches, saves and plans a corpus recipe that is not saved yet", async () => {
    (getRecipeByExternalId as jest.Mock).mockResolvedValue(null);
    (apiClient.get as jest.Mock).mockResolvedValue({
      external_id: "rec_1",
      title: "Bolognese",
      ingredients: null,
    });
    (saveRecipe as jest.Mock).mockResolvedValue(42);

    const planned = await planSuggestions([suggestion({ external_id: "rec_1" })]);

    expect(planned).toBe(1);
    expect(apiClient.get).toHaveBeenCalledWith("/recipes/rec_1");
    expect(saveRecipe).toHaveBeenCalledWith({
      external_id: "rec_1",
      title: "Bolognese",
      ingredients: [],
    });
    expect(addMealPlanEntry).toHaveBeenCalledWith(42);
    expect(addShoppingGapsForRecipe).toHaveBeenCalledWith(42);
  });

  it("reuses an already-saved corpus recipe without refetching it", async () => {
    (getRecipeByExternalId as jest.Mock).mockResolvedValue({ id: 7 });

    await planSuggestions([suggestion({ external_id: "rec_1" })]);

    expect(apiClient.get).not.toHaveBeenCalled();
    expect(addMealPlanEntry).toHaveBeenCalledWith(7);
  });

  it("plans saved-recipe suggestions by recipe_id", async () => {
    await planSuggestions([suggestion({ recipe_id: 5 })]);

    expect(addMealPlanEntry).toHaveBeenCalledWith(5);
  });

  it("skips a suggestion whose recipe cannot be fetched and plans the rest", async () => {
    (getRecipeByExternalId as jest.Mock).mockResolvedValue(null);
    (apiClient.get as jest.Mock).mockRejectedValueOnce(new Error("404")).mockResolvedValueOnce({
      external_id: "rec_2",
      title: "Chilli",
      ingredients: [],
    });
    (saveRecipe as jest.Mock).mockResolvedValue(9);

    const planned = await planSuggestions([
      suggestion({ external_id: "rec_1" }),
      suggestion({ external_id: "rec_2" }),
    ]);

    expect(planned).toBe(1);
    expect(addMealPlanEntry).toHaveBeenCalledTimes(1);
    expect(addMealPlanEntry).toHaveBeenCalledWith(9);
  });
});
