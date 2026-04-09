// mobile/app/(tabs)/pantry/scan.tsx

import { CameraView, useCameraPermissions } from "expo-camera";
import { router, useLocalSearchParams } from "expo-router";
import { useRef, useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { apiClient } from "@/api/client";

export default function ScanScreen() {
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const [permission, requestPermission] = useCameraPermissions();
  const [scanning, setScanning] = useState(false);
  const cameraRef = useRef<CameraView>(null);

  if (!permission) return <View style={{ flex: 1 }} />;
  if (!permission.granted) {
    return (
      <View style={styles.container}>
        <Text style={styles.message}>Camera permission is needed to scan receipts.</Text>
        <Pressable style={styles.button} onPress={requestPermission}>
          <Text style={styles.buttonText}>Grant Permission</Text>
        </Pressable>
      </View>
    );
  }

  async function capture() {
    if (!cameraRef.current || scanning) return;
    setScanning(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({ base64: true, quality: 0.8 });
      if (!photo?.base64) throw new Error("No image captured");

      const blob = await (await fetch(`data:image/jpeg;base64,${photo.base64}`)).blob();
      const form = new FormData();
      form.append("file", blob, "receipt.jpg");

      const result = await apiClient.postForm<{ items: unknown[] }>("/receipts/scan", form);
      router.push({
        pathname: "/(tabs)/pantry/review",
        params: { items: JSON.stringify(result.items), ...(returnTo ? { returnTo } : {}) },
      });
    } catch {
      Alert.alert("Scan failed", "Could not process receipt. Try again or add items manually.");
    } finally {
      setScanning(false);
    }
  }

  return (
    <View style={styles.container}>
      <CameraView ref={cameraRef} style={styles.camera} facing="back" />
      <View style={styles.controls}>
        {scanning ? (
          <ActivityIndicator size="large" color="#fff" />
        ) : (
          <Pressable style={styles.shutterButton} onPress={capture}>
            <View style={styles.shutterInner} />
          </Pressable>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  message: { color: "#fff", textAlign: "center", margin: 24, fontSize: 16 },
  button: {
    margin: 24,
    backgroundColor: "#2a9d8f",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontWeight: "600" },
  camera: { flex: 1 },
  controls: { position: "absolute", bottom: 40, width: "100%", alignItems: "center" },
  shutterButton: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "rgba(255,255,255,0.3)",
    justifyContent: "center",
    alignItems: "center",
  },
  shutterInner: { width: 58, height: 58, borderRadius: 29, backgroundColor: "#fff" },
});
