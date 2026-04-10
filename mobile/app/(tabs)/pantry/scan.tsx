// mobile/app/(tabs)/pantry/scan.tsx

import { CameraView, useCameraPermissions } from "expo-camera";
import { router, useLocalSearchParams } from "expo-router";
import { useRef } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { useScanReceipt } from "@/api/hooks";
import { ErrorState } from "@/components/ui/ErrorState";

export default function ScanScreen() {
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const scanMutation = useScanReceipt();

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
    if (!cameraRef.current || scanMutation.isPending) return;
    const photo = await cameraRef.current.takePictureAsync({ base64: true, quality: 0.8 });
    if (!photo?.base64) return;
    const blob = await (await fetch(`data:image/jpeg;base64,${photo.base64}`)).blob();
    const form = new FormData();
    form.append("file", blob, "receipt.jpg");
    scanMutation.mutate(form, {
      onSuccess: (result) => {
        router.push({
          pathname: "/(tabs)/pantry/review",
          params: { items: JSON.stringify(result.items), ...(returnTo ? { returnTo } : {}) },
        });
      },
    });
  }

  return (
    <View style={styles.container}>
      <CameraView ref={cameraRef} style={styles.camera} facing="back" />
      {scanMutation.isError ? (
        <View style={styles.errorOverlay}>
          <ErrorState
            testID="scan.error"
            message="Could not process receipt. Try again or add items manually."
            onRetry={() => scanMutation.reset()}
          />
        </View>
      ) : (
        <View style={styles.controls}>
          {scanMutation.isPending ? (
            <ActivityIndicator size="large" color="#fff" />
          ) : (
            <Pressable style={styles.shutterButton} onPress={capture}>
              <View style={styles.shutterInner} />
            </Pressable>
          )}
        </View>
      )}
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
  errorOverlay: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "rgba(255,255,255,0.95)",
    padding: 16,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
  },
});
