// mobile/app/sign-in.tsx
import { useAuthRequest } from "expo-auth-session";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, View } from "react-native";
import { AUTH_REDIRECT_URI, AUTHORIZE_URL } from "@/auth/google";
import { authStorage } from "@/auth/storage";
import { GleanMark } from "@/components/GleanMark";
import { AppText } from "@/components/ui/AppText";
import { theme } from "@/theme";

const CLIENT_ID = process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID ?? "";

const discovery = {
  authorizationEndpoint: AUTHORIZE_URL,
};

export default function SignInScreen() {
  const [loading, setLoading] = useState(false);

  const [request, , promptAsync] = useAuthRequest(
    {
      clientId: CLIENT_ID,
      redirectUri: AUTH_REDIRECT_URI,
      scopes: ["openid", "email", "profile"],
      extraParams: { identity_provider: "Google" },
      usePKCE: true,
    },
    discovery,
  );

  async function startSignIn() {
    if (!request || loading) return;
    try {
      if (!request.codeVerifier) throw new Error("Missing sign-in verifier. Please try again.");
      await authStorage.setPendingAuthRequest({
        codeVerifier: request.codeVerifier,
        state: request.state,
      });
      setLoading(true);
      await promptAsync();
    } catch (e: unknown) {
      Alert.alert("Sign in failed", e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  const disabled = !request || loading;

  return (
    <View style={styles.container}>
      <View style={styles.iconTile}>
        <GleanMark size={40} />
      </View>

      <AppText style={styles.title}>Waste less.{"\n"}Cook better.</AppText>

      <Pressable
        style={[styles.button, disabled && styles.buttonDisabled]}
        onPress={() => void startSignIn()}
        disabled={disabled}
      >
        {loading ? (
          <ActivityIndicator color={theme.colors.primaryForeground} />
        ) : (
          <AppText style={styles.buttonText}>Sign in with Google</AppText>
        )}
      </Pressable>

      <AppText style={styles.legal}>
        By continuing you agree to our Terms of Service and Privacy Policy.
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "flex-start",
    padding: theme.spacing.xl,
    backgroundColor: theme.colors.background,
  },
  iconTile: {
    width: 72,
    height: 72,
    borderRadius: theme.radius.xl,
    backgroundColor: theme.colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: theme.spacing.xl,
  },
  title: {
    fontFamily: theme.fontFamily.extrabold,
    fontSize: 32,
    lineHeight: 38,
    letterSpacing: -0.6,
    color: theme.colors.text,
    marginBottom: theme.spacing.xxl,
  },
  button: {
    alignSelf: "stretch",
    backgroundColor: theme.colors.ink,
    borderRadius: theme.radius.md,
    paddingVertical: theme.spacing.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    fontFamily: theme.fontFamily.semibold,
    fontSize: 16,
    color: theme.colors.primaryForeground,
  },
  legal: {
    fontFamily: theme.fontFamily.regular,
    fontSize: 13,
    lineHeight: 18,
    color: theme.colors.textDisabled,
    marginTop: theme.spacing.lg,
  },
});
