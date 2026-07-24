import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
// @ts-expect-error -- test-only escape hatch, see jest.mock("expo-router") below
import { __resetRouterMock, __setSearchParams, __triggerRefocus, router } from "expo-router";
import { useState } from "react";
import { useGenerateMealPlan } from "@/api/hooks";
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
  // Real expo-router calls useFocusEffect's callback on every focus event
  // (mount, and again each time the screen regains focus after navigating
  // away), and useLocalSearchParams reactively reflects router.setParams.
  // Mapping useFocusEffect to a plain useEffect and useLocalSearchParams to
  // a static value can't reproduce the refocus-duplicate bug, nor prove a
  // fix that clears the param via router.setParams. This fake wires the two
  // together: setParams updates shared state and notifies subscribers, and
  // __triggerRefocus imperatively re-fires the latest captured focus
  // callback to simulate "navigate away, then back" without a real
  // NavigationContainer.
  const state: { focusCallback: (() => void) | undefined; params: Record<string, unknown> } = {
    focusCallback: undefined,
    params: {},
  };
  const listeners = new Set<() => void>();
  const setParams = (patch: Record<string, unknown>) => {
    const next = { ...state.params, ...patch };
    for (const [key, value] of Object.entries(next)) {
      if (value === undefined) delete next[key];
    }
    state.params = next;
    listeners.forEach((listener) => {
      listener();
    });
  };
  return {
    router: { push: jest.fn(), setParams: jest.fn(setParams) },
    useFocusEffect: (callback: () => void) => {
      state.focusCallback = callback;
      React.useEffect(callback, [callback]);
    },
    useLocalSearchParams: () => {
      const [, forceRender] = React.useReducer((c: number) => c + 1, 0);
      React.useEffect(() => {
        listeners.add(forceRender);
        return () => listeners.delete(forceRender);
      }, [forceRender]);
      return state.params;
    },
    __triggerRefocus: () => state.focusCallback?.(),
    __setSearchParams: (params: Record<string, unknown>) => {
      state.params = params;
    },
    __resetRouterMock: () => {
      state.focusCallback = undefined;
      state.params = {};
      listeners.clear();
    },
  };
});

jest.mock("@/api/hooks", () => ({ useGenerateMealPlan: jest.fn() }));
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
jest.mock("@/meal-plan/compress", () => ({ compressPantry: jest.fn().mockReturnValue([]) }));
jest.mock("@/utils/toast", () => ({ showError: jest.fn(), showSuccess: jest.fn() }));
jest.mock("@/platform/haptics", () => ({ hapticImpact: jest.fn().mockResolvedValue(undefined) }));

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

describe("PlanScreen", () => {
  const mutate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (__resetRouterMock as () => void)();
    mutate.mockImplementation((_payload, callbacks) => {
      callbacks.onSuccess({ suggestions: [{ recipe_id: 10 }] });
    });
    (useGenerateMealPlan as jest.Mock).mockReturnValue({
      mutate,
      reset: jest.fn(),
      isPending: false,
    });
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
      },
    ]);
  });

  it("renders progress and dinner slots", async () => {
    const screen = render(<PlanScreen />);

    await waitFor(() => expect(screen.getByText("Tomato Pasta")).toBeTruthy());
    expect(screen.getByText("This Week")).toBeTruthy();
    expect(screen.getByText("1/3")).toBeTruthy();
    expect(screen.getByText("2 dinners left to plan this week")).toBeTruthy();
    expect(screen.getAllByText("Add a dinner")).toHaveLength(2);
  }, 15_000);

  it("marks an entry cooked and deletes entries", async () => {
    const screen = render(<PlanScreen />);

    await waitFor(() => expect(screen.getByText("Tomato Pasta")).toBeTruthy());
    fireEvent.press(screen.getByText("Cooked?"));
    await waitFor(() => expect(markMealAsCooked).toHaveBeenCalledWith(1));

    fireEvent.press(screen.getByLabelText("Remove Tomato Pasta"));
    await waitFor(() => expect(deleteMealPlanEntry).toHaveBeenCalledWith(1));
  });

  it("deletes a planned meal from a qualifying left swipe", async () => {
    const screen = render(<PlanScreen />);

    await waitFor(() => expect(screen.getByText("Tomato Pasta")).toBeTruthy());
    const row = screen.getByTestId("plan-slot-row-1");

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

    await waitFor(() => expect(deleteMealPlanEntry).toHaveBeenCalledWith(1));
  });

  it("generates a week using existing suggestion and shopping gap flow", async () => {
    const screen = render(<PlanScreen />);

    await waitFor(() => expect(screen.getByText("Generate")).toBeTruthy());
    fireEvent.press(screen.getByText("Generate"));

    await waitFor(() => expect(mutate).toHaveBeenCalled());
    expect(addMealPlanEntry).toHaveBeenCalledWith(10);
    expect(addShoppingGapsForRecipe).toHaveBeenCalledWith(10);
  });

  it("disables Generate while a request is pending, so a double-tap can't fire it twice", async () => {
    // mutateSpy records every call generateWeek() makes into mutate(),
    // regardless of whether/when any of them resolve — this isolates the
    // "does a second tap re-enter generateWeek" question from mutation
    // resolution timing, which a naive single-shared-callback stub would
    // silently mask (a second call's callbacks would just replace the
    // first's, hiding a double-fire instead of surfacing it).
    const mutateSpy = jest.fn();
    (useGenerateMealPlan as jest.Mock).mockImplementation(() => {
      const [isPending, setIsPending] = useState(false);
      return {
        isPending,
        reset: jest.fn(),
        mutate: (...callArgs: unknown[]) => {
          mutateSpy(...callArgs);
          setIsPending(true);
        },
      };
    });

    const screen = render(<PlanScreen />);
    await waitFor(() => expect(screen.getByText("Generate")).toBeTruthy());

    fireEvent.press(screen.getByText("Generate"));
    await waitFor(() => expect(screen.getByText("Generating")).toBeTruthy());

    // Generate button is disabled while pending, so this second tap must be
    // a no-op rather than firing generateWeek again. generateWeek() is
    // async even when it *does* re-enter (it awaits getPantryItems /
    // getSavedRecipes / getUserConfig before calling mutate), so a bare
    // synchronous assertion right after fireEvent.press would pass even
    // without the guard, simply because the second call hadn't reached
    // mutate() yet. Flush pending microtasks first to rule that out.
    fireEvent.press(screen.getByText("Generating"));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(mutateSpy).toHaveBeenCalledTimes(1);
  });

  it("navigates empty slots to recipe search", async () => {
    const screen = render(<PlanScreen />);

    await waitFor(() => expect(screen.getAllByText("Add a dinner")[0]).toBeTruthy());
    fireEvent.press(screen.getAllByText("Add a dinner")[0]!);
    expect(router.push).toHaveBeenCalledWith("/(tabs)/meals/search");
  });

  it("does not re-add the same recipe when the plan tab regains focus again", async () => {
    // Reproduces the reported bug: "Add to plan" hands off via the
    // add_recipe_id route param (see recipe-detail-screen.test.tsx's
    // "add-to-plan handoff"). If that param is never cleared, every
    // subsequent focus of the plan tab re-runs handleAddRecipe for the same
    // id and inserts another meal_plan_entries row.
    (__setSearchParams as (params: Record<string, unknown>) => void)({ add_recipe_id: "7" });

    render(<PlanScreen />);

    await waitFor(() => expect(addMealPlanEntry).toHaveBeenCalledTimes(1));
    expect(addMealPlanEntry).toHaveBeenCalledWith(7);

    // Simulate navigating off the plan tab and back onto it. The
    // add_recipe_id search param is only gone on refocus if the screen
    // cleared it (via router.setParams) after consuming it the first time.
    await act(async () => {
      (__triggerRefocus as () => void)();
    });

    expect(addMealPlanEntry).toHaveBeenCalledTimes(1);
  });
});
