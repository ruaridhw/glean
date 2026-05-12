import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import { signOut } from "@/auth/google";
import { getUserConfig, saveUserConfig } from "@/db/config";
import SettingsScreen from "../../app/(tabs)/settings";

jest.mock("@expo/vector-icons", () => {
  const React = require("react");
  const { Text } = require("react-native");
  return { Ionicons: ({ name }: { name: string }) => React.createElement(Text, null, name) };
});

jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: ({ children }: { children: React.ReactNode }) => children,
  useSafeAreaInsets: () => ({ top: 0, right: 0, bottom: 0, left: 0 }),
}));

jest.mock("expo-router", () => ({ router: { replace: jest.fn() } }));
jest.mock("@react-native-community/slider", () => "Slider");
jest.mock("expo-file-system", () => ({
  File: jest.fn().mockImplementation(() => ({ exists: false, uri: "file://db" })),
  Paths: { document: "document" },
}));
jest.mock("@/api/client", () => ({ apiClient: { postForm: jest.fn() } }));
jest.mock("@/auth/google", () => ({ signOut: jest.fn().mockResolvedValue(undefined) }));
jest.mock("@/db/config", () => ({
  getUserConfig: jest.fn(),
  saveUserConfig: jest.fn().mockResolvedValue(undefined),
}));
jest.mock("@/platform/haptics", () => ({ hapticImpact: jest.fn().mockResolvedValue(undefined) }));

describe("SettingsScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getUserConfig as jest.Mock).mockResolvedValue({
      id: "user",
      purchase_tolerance: 0.5,
      preferred_servings: 2,
      meals_per_week: 5,
      dietary_flags: ["Vegetarian"],
      max_active_time_mins: null,
    });
  });

  it("renders stats, chips, and account actions after loading config", async () => {
    const screen = render(<SettingsScreen />);

    await waitFor(() => expect(screen.getByText("Settings")).toBeTruthy());
    expect(screen.getByText("Preferences")).toBeTruthy();
    expect(screen.getByText("Dinners per week")).toBeTruthy();
    expect(screen.getByText("Default servings")).toBeTruthy();
    expect(screen.getByText("Dietary preferences")).toBeTruthy();
    expect(screen.getByText("Vegetarian")).toBeTruthy();
    expect(screen.getByText("Sign out")).toBeTruthy();
  });

  it("saves selected config values across the original supported ranges", async () => {
    const screen = render(<SettingsScreen />);

    await waitFor(() => expect(screen.getByText("Save Settings")).toBeTruthy());
    fireEvent.press(screen.getByLabelText("1 dinners per week"));
    fireEvent.press(screen.getByLabelText("5 default servings"));
    fireEvent.press(screen.getByText("Vegan"));
    fireEvent.press(screen.getByText("Save Settings"));

    await waitFor(() =>
      expect(saveUserConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "user",
          meals_per_week: 1,
          preferred_servings: 5,
          dietary_flags: ["Vegetarian", "Vegan"],
        }),
      ),
    );
  });

  it("keeps sign out route replacement", async () => {
    const screen = render(<SettingsScreen />);

    await waitFor(() => expect(screen.getByText("Sign out")).toBeTruthy());
    fireEvent.press(screen.getByText("Sign out"));
    await waitFor(() => expect(signOut).toHaveBeenCalled());
    expect(router.replace).toHaveBeenCalledWith("/sign-in");
  });
});
