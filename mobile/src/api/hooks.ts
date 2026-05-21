// mobile/src/api/hooks.ts
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type {
  DescribeResponse,
  RecipeSearchResponse,
  ScanResponse,
  ShoppingParseRequest,
  ShoppingParseResponse,
  SuggestionResponse,
} from "@/api/types";

export function useRecipeSearch(query: string) {
  return useQuery({
    queryKey: ["recipeSearch", query],
    queryFn: () =>
      apiClient.get<RecipeSearchResponse>(`/recipes/search?q=${encodeURIComponent(query)}`),
    enabled: query.trim().length > 0,
  });
}

export function useScanReceipt() {
  return useMutation({
    mutationFn: (formData: FormData) =>
      apiClient.postForm<ScanResponse>("/receipts/scan", formData),
  });
}

export function useDescribeReceipt() {
  return useMutation({
    mutationFn: (text: string) => apiClient.post<DescribeResponse>("/receipts/describe", { text }),
  });
}

export function useParseShoppingDescription() {
  return useMutation({
    mutationFn: (body: ShoppingParseRequest) =>
      apiClient.post<ShoppingParseResponse>("/shopping/parse-description", body),
  });
}

export function useSuggestMeals() {
  return useMutation({
    mutationFn: (body: {
      pantry: unknown;
      recipe_history: unknown;
      food_group_coverage: Record<string, never>;
      purchase_tolerance: number;
      meals_per_week: number;
      dietary_flags: string[];
      max_active_time_mins: number | null;
    }) => apiClient.post<SuggestionResponse>("/suggestions", body),
  });
}
