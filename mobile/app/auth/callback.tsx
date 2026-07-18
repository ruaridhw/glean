import { router, useLocalSearchParams } from "expo-router";
import { useEffect } from "react";
import { ActivityIndicator, Alert, StyleSheet, View } from "react-native";
import { handleAuthCode } from "@/auth/google";
import { useAuthSession } from "@/auth/session";
import { authStorage } from "@/auth/storage";
import { AppText } from "@/components/ui/AppText";
import { theme } from "@/theme";

type CallbackParams = {
  code?: string | string[];
  error?: string | string[];
  error_description?: string | string[];
  state?: string | string[];
};

type ParsedCallbackParams = {
  code?: string;
  error?: string;
  errorDescription?: string;
  state?: string;
};

function singleParam(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) throw new Error("Invalid sign-in callback. Please try again.");
  return value;
}

function parseCallbackParams(params: CallbackParams): ParsedCallbackParams {
  const parsed: ParsedCallbackParams = {};
  const code = singleParam(params.code);
  const error = singleParam(params.error);
  const errorDescription = singleParam(params.error_description);
  const state = singleParam(params.state);

  if (code !== undefined) parsed.code = code;
  if (error !== undefined) parsed.error = error;
  if (errorDescription !== undefined) parsed.errorDescription = errorDescription;
  if (state !== undefined) parsed.state = state;

  return parsed;
}

function fail(message: string) {
  Alert.alert("Sign in failed", message);
  router.replace("/sign-in");
}

export default function AuthCallbackScreen() {
  const params = useLocalSearchParams<CallbackParams>();
  const { refresh } = useAuthSession();

  useEffect(() => {
    async function completeSignIn() {
      let callbackParams: ParsedCallbackParams;

      try {
        callbackParams = parseCallbackParams(params);
      } catch (e: unknown) {
        fail(e instanceof Error ? e.message : "Invalid sign-in callback. Please try again.");
        return;
      }

      const { code, errorDescription, error, state } = callbackParams;

      if (error) {
        fail(errorDescription ?? error);
        return;
      }

      if (!code) {
        fail("Missing authorization code.");
        return;
      }

      try {
        const codeVerifier = await authStorage.getPendingAuthCodeVerifier(state);
        if (!codeVerifier) throw new Error("Missing sign-in verifier. Please try again.");

        await handleAuthCode(code, codeVerifier);
        await authStorage.clearPendingAuthRequest();
        await refresh();
        router.replace("/(tabs)/pantry");
      } catch (e: unknown) {
        await authStorage.clearPendingAuthRequest();
        fail(e instanceof Error ? e.message : "Unknown error");
      }
    }

    void completeSignIn();
  }, [params, refresh]);

  return (
    <View style={styles.container}>
      <ActivityIndicator color={theme.colors.primary} />
      <AppText style={styles.text}>Completing sign in...</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    backgroundColor: theme.colors.background,
  },
  text: {
    color: theme.colors.mutedForeground,
    fontSize: 16,
  },
});
