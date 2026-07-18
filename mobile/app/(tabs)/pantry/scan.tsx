// mobile/app/(tabs)/pantry/scan.tsx

import { Ionicons } from "@expo/vector-icons";
import { CameraView, useCameraPermissions } from "expo-camera";
import { router, useLocalSearchParams } from "expo-router";
import { useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@/theme";

export default function ScanScreen() {
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const [permission, requestPermission] = useCameraPermissions();
  const [capturing, setCapturing] = useState(false);
  const cameraRef = useRef<CameraView>(null);

  if (!permission) return <View style={styles.container} />;
  if (!permission.granted) {
    return (
      <View style={[styles.container, styles.permission]}>
        <Text style={styles.message}>Camera permission is needed to scan receipts.</Text>
        <Pressable style={styles.button} onPress={requestPermission}>
          <Text style={styles.buttonText}>Grant Permission</Text>
        </Pressable>
      </View>
    );
  }

  async function capture() {
    if (!cameraRef.current || capturing) return;
    setCapturing(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({ base64: true, quality: 0.8 });
      if (!photo?.base64) return;
      router.push({
        pathname: "/(tabs)/pantry/scan-progress",
        params: { photoBase64: photo.base64, ...(returnTo ? { returnTo } : {}) },
      });
    } finally {
      setCapturing(false);
    }
  }

  return (
    <View style={styles.container}>
      <CameraView testID="scan.camera" ref={cameraRef} style={styles.camera} facing="back" />

      <View pointerEvents="box-none" style={styles.overlay}>
        <View style={styles.frame} pointerEvents="none" />

        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Close camera"
          style={styles.backButton}
          onPress={() => router.back()}
        >
          <Ionicons name="chevron-back" size={20} color={theme.colors.primaryForeground} />
        </Pressable>

        <View style={styles.controls} pointerEvents="box-none">
          <Text style={styles.hint}>Line the receipt up inside the frame</Text>
          <Pressable style={styles.shutterButton} onPress={capture} disabled={capturing}>
            <View style={styles.shutterInner} />
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#111511" },
  permission: { justifyContent: "center", alignItems: "center", padding: theme.spacing.xl },
  message: {
    color: theme.colors.primaryForeground,
    textAlign: "center",
    marginBottom: theme.spacing.lg,
    fontSize: 16,
    fontFamily: theme.fontFamily.semibold,
    fontWeight: "600",
  },
  button: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    paddingHorizontal: theme.spacing.xl,
    paddingVertical: 14,
    alignItems: "center",
    ...theme.shadow.fab,
  },
  buttonText: {
    color: theme.colors.primaryForeground,
    fontFamily: theme.fontFamily.extrabold,
    fontWeight: "800",
    fontSize: 15,
  },
  camera: { ...StyleSheet.absoluteFillObject },
  overlay: { ...StyleSheet.absoluteFillObject },
  frame: {
    position: "absolute",
    left: 36,
    right: 36,
    top: 80,
    bottom: 120,
    borderWidth: 2.5,
    borderColor: "rgba(255,255,255,0.75)",
    borderRadius: theme.radius.xl,
  },
  backButton: {
    position: "absolute",
    top: 24,
    left: 20,
    width: 44,
    height: 44,
    borderRadius: theme.radius.pill,
    backgroundColor: "rgba(0,0,0,0.45)",
    alignItems: "center",
    justifyContent: "center",
  },
  controls: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 36,
    alignItems: "center",
    gap: 18,
  },
  hint: {
    backgroundColor: "rgba(0,0,0,0.45)",
    color: theme.colors.primaryForeground,
    borderRadius: theme.radius.pill,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.sm,
    fontSize: 13,
    fontFamily: theme.fontFamily.bold,
    fontWeight: "700",
    overflow: "hidden",
  },
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
