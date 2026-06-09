import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { Pressable, Text } from "react-native";
import { signOut as clearGoogleAuth } from "@/auth/google";
import { AuthProvider, useAuthSession } from "@/auth/session";
import { authStorage } from "@/auth/storage";

jest.mock("@/auth/storage", () => ({
  authStorage: {
    getUserSub: jest.fn(),
    hasTokens: jest.fn(),
  },
}));

jest.mock("@/auth/google", () => ({
  signOut: jest.fn(),
}));

function Probe() {
  const session = useAuthSession();

  return (
    <>
      <Text>{`status:${session.status}`}</Text>
      <Text>{`auth:${session.isAuthenticated ? "authenticated" : "unauthenticated"}`}</Text>
      <Text>{`user:${session.userSub ?? "no-user"}`}</Text>
      <Pressable onPress={() => void session.refresh()}>
        <Text>Refresh</Text>
      </Pressable>
      <Pressable onPress={() => void session.signOut()}>
        <Text>Sign out</Text>
      </Pressable>
    </>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (authStorage.hasTokens as jest.Mock).mockResolvedValue(false);
    (authStorage.getUserSub as jest.Mock).mockResolvedValue(null);
    (clearGoogleAuth as jest.Mock).mockResolvedValue(undefined);
  });

  it("exposes an authenticated session with the resolved user id", async () => {
    (authStorage.hasTokens as jest.Mock).mockResolvedValue(true);
    (authStorage.getUserSub as jest.Mock).mockResolvedValue("user-sub-123");

    const screen = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    expect(screen.getByText("status:loading")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("auth:authenticated")).toBeTruthy());
    expect(screen.getByText("user:user-sub-123")).toBeTruthy();
  });

  it("refreshes the session on demand", async () => {
    (authStorage.hasTokens as jest.Mock).mockResolvedValueOnce(false).mockResolvedValueOnce(true);
    (authStorage.getUserSub as jest.Mock).mockResolvedValue("user-sub-456");

    const screen = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText("auth:unauthenticated")).toBeTruthy());
    fireEvent.press(screen.getByText("Refresh"));

    await waitFor(() => expect(screen.getByText("auth:authenticated")).toBeTruthy());
    expect(screen.getByText("user:user-sub-456")).toBeTruthy();
  });

  it("clears tokens and marks the session unauthenticated on sign out", async () => {
    (authStorage.hasTokens as jest.Mock).mockResolvedValue(true);
    (authStorage.getUserSub as jest.Mock).mockResolvedValue("user-sub-789");

    const screen = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText("auth:authenticated")).toBeTruthy());
    fireEvent.press(screen.getByText("Sign out"));

    await waitFor(() => expect(clearGoogleAuth).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText("auth:unauthenticated")).toBeTruthy());
    expect(screen.getByText("user:no-user")).toBeTruthy();
  });
});
