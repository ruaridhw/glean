import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { signOut as clearGoogleAuth } from "./google";
import { authStorage } from "./storage";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthState = {
  status: AuthStatus;
  userSub: string | null;
};

type AuthSessionContextValue = AuthState & {
  isAuthenticated: boolean;
  isLoading: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);

async function readAuthState(): Promise<AuthState> {
  const authenticated = await authStorage.hasTokens();
  if (!authenticated) return { status: "unauthenticated", userSub: null };

  return {
    status: "authenticated",
    userSub: await authStorage.getUserSub(),
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading", userSub: null });

  const refresh = useCallback(async () => {
    setState(await readAuthState());
  }, []);

  const signOut = useCallback(async () => {
    await clearGoogleAuth();
    setState({ status: "unauthenticated", userSub: null });
  }, []);

  useEffect(() => {
    let mounted = true;

    readAuthState()
      .then((nextState) => {
        if (mounted) setState(nextState);
      })
      .catch((error: unknown) => {
        console.error("[auth] session load failed:", error);
        if (mounted) setState({ status: "unauthenticated", userSub: null });
      });

    return () => {
      mounted = false;
    };
  }, []);

  const value = useMemo<AuthSessionContextValue>(
    () => ({
      ...state,
      isAuthenticated: state.status === "authenticated",
      isLoading: state.status === "loading",
      refresh,
      signOut,
    }),
    [state, refresh, signOut],
  );

  return <AuthSessionContext.Provider value={value}>{children}</AuthSessionContext.Provider>;
}

export function useAuthSession(): AuthSessionContextValue {
  const value = useContext(AuthSessionContext);
  if (!value) throw new Error("useAuthSession must be used within AuthProvider");
  return value;
}
