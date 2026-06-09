// mobile/app/sign-in.tsx
import { useAuthRequest } from "expo-auth-session";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { AUTH_REDIRECT_URI, AUTHORIZE_URL } from "@/auth/google";
import { authStorage } from "@/auth/storage";

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

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Glean</Text>
      <Text style={styles.subtitle}>Waste less. Cook better.</Text>
      <Pressable
        style={styles.button}
        onPress={() => void startSignIn()}
        disabled={!request || loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Sign in with Google</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: "#fff" },
  title: {
    fontSize: 32,
    fontWeight: "800",
    color: "#2a9d8f",
    textAlign: "center",
    marginBottom: 4,
  },
  subtitle: { fontSize: 16, color: "#888", textAlign: "center", marginBottom: 32 },
  button: { backgroundColor: "#2a9d8f", borderRadius: 8, padding: 14, alignItems: "center" },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
});
