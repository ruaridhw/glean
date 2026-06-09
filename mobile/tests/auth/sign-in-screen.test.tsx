import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { AUTH_REDIRECT_URI, handleAuthCode } from "@/auth/google";
import { authStorage } from "@/auth/storage";
import SignInScreen from "../../app/sign-in";

const mockPromptAsync = jest.fn();
const mockUseAuthRequest = jest.fn();
const mockRouterReplace = jest.fn();

jest.mock("expo-auth-session", () => ({
  makeRedirectUri: jest.fn(() => "glean://auth/callback"),
  useAuthRequest: (...args: unknown[]) => mockUseAuthRequest(...args),
}));

jest.mock("expo-router", () => ({
  router: { replace: (...args: unknown[]) => mockRouterReplace(...args) },
}));

jest.mock("@/auth/storage", () => ({
  authStorage: { setPendingAuthRequest: jest.fn() },
}));

jest.mock("@/auth/google", () => ({
  AUTH_REDIRECT_URI: "glean://auth/callback",
  AUTHORIZE_URL: "https://auth.example.com/oauth2/authorize",
  handleAuthCode: jest.fn(),
}));

describe("SignInScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseAuthRequest.mockReturnValue([
      { codeVerifier: "verifier-123", state: "state-abc" },
      null,
      mockPromptAsync,
    ]);
    mockPromptAsync.mockResolvedValue(undefined);
    (authStorage.setPendingAuthRequest as jest.Mock).mockResolvedValue(undefined);
  });

  it("starts Cognito sign-in with the configured native callback URI", () => {
    render(<SignInScreen />);

    expect(mockUseAuthRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        redirectUri: AUTH_REDIRECT_URI,
      }),
      expect.any(Object),
    );
  });

  it("persists the PKCE verifier before opening Cognito", async () => {
    const screen = render(<SignInScreen />);

    fireEvent.press(screen.getByText("Sign in with Google"));

    await waitFor(() => {
      expect(authStorage.setPendingAuthRequest).toHaveBeenCalledWith({
        codeVerifier: "verifier-123",
        state: "state-abc",
      });
    });
    expect(mockPromptAsync).toHaveBeenCalledTimes(1);
  });

  it("does not exchange an AuthSession success response because the callback route owns token exchange", () => {
    mockUseAuthRequest.mockReturnValue([
      { codeVerifier: "verifier-123", state: "state-abc" },
      { type: "success", params: { code: "auth-code-123" } },
      mockPromptAsync,
    ]);

    render(<SignInScreen />);

    expect(handleAuthCode).not.toHaveBeenCalled();
    expect(mockRouterReplace).not.toHaveBeenCalled();
    expect(authStorage.setPendingAuthRequest).not.toHaveBeenCalled();
  });
});
