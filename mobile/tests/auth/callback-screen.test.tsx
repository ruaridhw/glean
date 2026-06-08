import { render, waitFor } from "@testing-library/react-native";
import { Alert } from "react-native";
import { handleAuthCode } from "@/auth/google";
import { useAuthSession } from "@/auth/session";
import { authStorage } from "@/auth/storage";
import AuthCallbackScreen from "../../app/auth/callback";

const mockReplace = jest.fn();
let mockParams: Record<string, string | string[] | undefined> = {};

jest.mock("expo-router", () => ({
  router: { replace: (...args: unknown[]) => mockReplace(...args) },
  useLocalSearchParams: () => mockParams,
}));

jest.mock("@/auth/google", () => ({
  handleAuthCode: jest.fn(),
}));

jest.mock("@/auth/storage", () => ({
  authStorage: {
    clearPendingAuthRequest: jest.fn(),
    getPendingAuthCodeVerifier: jest.fn(),
  },
}));

jest.mock("@/auth/session", () => ({
  useAuthSession: jest.fn(),
}));

describe("AuthCallbackScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockParams = {};
    jest.spyOn(Alert, "alert").mockImplementation(() => undefined);
    (authStorage.getPendingAuthCodeVerifier as jest.Mock).mockResolvedValue("verifier-123");
    (handleAuthCode as jest.Mock).mockResolvedValue(undefined);
    (useAuthSession as jest.Mock).mockReturnValue({
      refresh: jest.fn().mockResolvedValue(undefined),
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("exchanges the returned Cognito code and routes to Pantry", async () => {
    mockParams = { code: "auth-code-123", state: "state-abc" };

    render(<AuthCallbackScreen />);

    await waitFor(() => {
      expect(handleAuthCode).toHaveBeenCalledWith("auth-code-123", "verifier-123");
    });
    expect(useAuthSession().refresh).toHaveBeenCalledTimes(1);
    expect(authStorage.getPendingAuthCodeVerifier).toHaveBeenCalledWith("state-abc");
    expect(authStorage.clearPendingAuthRequest).toHaveBeenCalledTimes(1);
    expect(mockReplace).toHaveBeenCalledWith("/(tabs)/pantry");
    expect(Alert.alert).not.toHaveBeenCalled();
  });

  it("shows a sign-in failure and returns to sign-in when Cognito returns an error", async () => {
    mockParams = { error: "access_denied", error_description: "User cancelled" };

    render(<AuthCallbackScreen />);

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith("Sign in failed", "User cancelled");
    });
    expect(handleAuthCode).not.toHaveBeenCalled();
    expect(mockReplace).toHaveBeenCalledWith("/sign-in");
  });

  it("shows a sign-in failure and returns to sign-in when the code is missing", async () => {
    mockParams = { state: "state-abc" };

    render(<AuthCallbackScreen />);

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith("Sign in failed", "Missing authorization code.");
    });
    expect(handleAuthCode).not.toHaveBeenCalled();
    expect(mockReplace).toHaveBeenCalledWith("/sign-in");
  });

  it.each([
    ["code", { code: ["auth-code-123", "auth-code-456"], state: "state-abc" }],
    ["state", { code: "auth-code-123", state: ["state-abc", "state-def"] }],
    ["error", { error: ["access_denied", "server_error"] }],
    [
      "error_description",
      { error: "access_denied", error_description: ["User cancelled", "Unexpected error"] },
    ],
  ] satisfies Array<
    [string, Record<string, string | string[] | undefined>]
  >)("rejects repeated %s callback params", async (_name, params) => {
    mockParams = params;

    render(<AuthCallbackScreen />);

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        "Sign in failed",
        "Invalid sign-in callback. Please try again.",
      );
    });
    expect(handleAuthCode).not.toHaveBeenCalled();
    expect(authStorage.clearPendingAuthRequest).not.toHaveBeenCalled();
    expect(mockReplace).toHaveBeenCalledWith("/sign-in");
  });

  it("shows a sign-in failure when token exchange fails", async () => {
    mockParams = { code: "auth-code-123", state: "state-abc" };
    (handleAuthCode as jest.Mock).mockRejectedValue(new Error("Token exchange failed"));

    render(<AuthCallbackScreen />);

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith("Sign in failed", "Token exchange failed");
    });
    expect(authStorage.clearPendingAuthRequest).toHaveBeenCalledTimes(1);
    expect(mockReplace).toHaveBeenCalledWith("/sign-in");
  });
});
