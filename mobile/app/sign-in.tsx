// mobile/app/sign-in.tsx
import { makeRedirectUri, useAuthRequest } from "expo-auth-session";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { AUTHORIZE_URL, handleAuthCode } from "@/auth/google";

const CLIENT_ID = process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID ?? "";
const REDIRECT_URI = makeRedirectUri({ scheme: "glean", path: "auth/callback" });

const discovery = {
  authorizationEndpoint: AUTHORIZE_URL,
};

export default function SignInScreen() {
  const [loading, setLoading] = useState(false);

  const [request, response, promptAsync] = useAuthRequest(
    {
      clientId: CLIENT_ID,
      redirectUri: REDIRECT_URI,
      scopes: ["openid", "email", "profile"],
      extraParams: { identity_provider: "Google" },
      usePKCE: true,
    },
    discovery,
  );

  useEffect(() => {
    if (response?.type !== "success") return;
    const code = response.params.code;
    const codeVerifier = request?.codeVerifier;
    if (!code || !codeVerifier) return;

    setLoading(true);
    handleAuthCode(code, codeVerifier)
      .then(() => router.replace("/(tabs)/pantry"))
      .catch((e: unknown) => {
        Alert.alert("Sign in failed", e instanceof Error ? e.message : "Unknown error");
      })
      .finally(() => setLoading(false));
  }, [response, request]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Glean</Text>
      <Text style={styles.subtitle}>Waste less. Cook better.</Text>
      <Pressable style={styles.button} onPress={() => promptAsync()} disabled={!request || loading}>
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
