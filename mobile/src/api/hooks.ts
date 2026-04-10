// mobile/src/api/hooks.ts
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";

interface SearchResult {
  external_id: string;
  title: string;
  cuisine: string | null;
  difficulty: string | null;
  total_time_mins: number | null;
  dietary_flags: string[];
}

interface ParsedIngredient {
  name: string;
  quantity: number;
  unit: string;
  unit_price: number | null;
  confidence: number;
}

export function useRecipeSearch(query: string) {
  return useQuery({
    queryKey: ["recipeSearch", query],
    queryFn: () =>
      apiClient.get<{ results: SearchResult[] }>(
        `/recipes/search?q=${encodeURIComponent(query)}`,
      ),
    enabled: query.trim().length > 0,
  });
}

export function useScanReceipt() {
  return useMutation({
    mutationFn: (formData: FormData) =>
      apiClient.postForm<{ items: ParsedIngredient[] }>("/receipts/scan", formData),
  });
}

export function useDescribeReceipt() {
  return useMutation({
    mutationFn: (text: string) =>
      apiClient.post<{ items: ParsedIngredient[] }>("/receipts/describe", { text }),
  });
}

export function useImportRecipe() {
  return useMutation({
    mutationFn: (url: string) =>
      apiClient.post<any>("/recipes/import-url", { url }),
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
    }) => apiClient.post<{ suggestions: Array<{ recipe_id: number }> }>("/suggestions", body),
  });
}
