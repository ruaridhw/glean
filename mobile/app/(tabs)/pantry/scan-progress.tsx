// mobile/app/(tabs)/pantry/scan-progress.tsx
import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Animated, StyleSheet, Text, View } from "react-native";
import { useScanReceipt } from "@/api/hooks";
import { ErrorState } from "@/components/ui/ErrorState";
import { theme } from "@/theme";

const STEPS = [
  { label: "Uploading image", icon: "cloud-upload-outline" as const, durationMs: 1500 },
  { label: "Reading receipt", icon: "document-text-outline" as const, durationMs: 2500 },
  { label: "Extracting items", icon: "list-outline" as const, durationMs: 1500 },
];

export default function ScanProgressScreen() {
  const { photoBase64, returnTo } = useLocalSearchParams<{
    photoBase64: string;
    returnTo?: string;
  }>();
  const [activeStep, setActiveStep] = useState(0);
  const [apiDone, setApiDone] = useState(false);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const scanMutation = useScanReceipt();

  // Pulsing icon animation
  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.15, duration: 800, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 800, useNativeDriver: true }),
      ]),
    );
    pulse.start();
    return () => pulse.stop();
  }, [pulseAnim]);

  // Fire API call on mount
  useEffect(() => {
    async function submit() {
      const blob = await (await fetch(`data:image/jpeg;base64,${photoBase64}`)).blob();
      const form = new FormData();
      form.append("file", blob, "receipt.jpg");
      scanMutation.mutate(form, {
        onSuccess: () => setApiDone(true),
      });
    }
    submit();
  }, [photoBase64, scanMutation.mutate]);

  // Timed step progression
  useEffect(() => {
    let elapsed = 0;
    const interval = setInterval(() => {
      elapsed += 200;
      let cumulativeMs = 0;
      for (const [i, step] of STEPS.entries()) {
        cumulativeMs += step.durationMs;
        if (elapsed < cumulativeMs) {
          setActiveStep(i);
          return;
        }
      }
      setActiveStep(STEPS.length - 1);
    }, 200);
    return () => clearInterval(interval);
  }, []);

  // Navigate when API done
  useEffect(() => {
    if (!apiDone || !scanMutation.data) return;
    const fastForward = setTimeout(() => {
      setActiveStep(STEPS.length - 1);
      setTimeout(() => {
        router.replace({
          pathname: "/(tabs)/pantry/review",
          params: {
            items: JSON.stringify(scanMutation.data.items),
            ...(returnTo ? { returnTo } : {}),
          },
        });
      }, 500);
    }, 300);
    return () => clearTimeout(fastForward);
  }, [apiDone, scanMutation.data, returnTo]);

  if (scanMutation.isError) {
    return (
      <View style={s.container}>
        <ErrorState
          testID="scanProgress.error"
          message="Could not process receipt. Try again or add items manually."
          onRetry={() => router.back()}
        />
      </View>
    );
  }

  return (
    <View style={s.container}>
      <Animated.View style={[s.iconContainer, { transform: [{ scale: pulseAnim }] }]}>
        <Ionicons name="receipt-outline" size={64} color={theme.colors.primary} />
      </Animated.View>

      <View style={s.steps}>
        {STEPS.map((step, i) => {
          const isActive = i === activeStep;
          const isComplete = i < activeStep || (i === STEPS.length - 1 && apiDone);
          return (
            <View key={step.label} style={s.stepRow}>
              <Ionicons
                name={isComplete ? "checkmark-circle" : step.icon}
                size={24}
                color={
                  isComplete
                    ? theme.colors.success
                    : isActive
                      ? theme.colors.primary
                      : theme.colors.textDisabled
                }
              />
              <Text
                style={[
                  s.stepLabel,
                  isActive && s.stepLabelActive,
                  isComplete && s.stepLabelComplete,
                ]}
              >
                {step.label}
                {isActive && !isComplete && activeStep === STEPS.length - 1 && !apiDone ? "…" : ""}
              </Text>
            </View>
          );
        })}
      </View>

      {activeStep === STEPS.length - 1 && !apiDone && (
        <Text style={s.almostDone}>Almost done...</Text>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
    justifyContent: "center",
    alignItems: "center",
    padding: theme.spacing.xxl,
  },
  iconContainer: { marginBottom: theme.spacing.xxl },
  steps: {
    gap: theme.spacing.lg,
    width: "100%",
    backgroundColor: theme.colors.card,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.xl,
    ...theme.shadow.card,
  },
  stepRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.lg,
  },
  stepLabel: {
    fontSize: theme.typography.body.fontSize,
    color: theme.colors.textDisabled,
  },
  stepLabelActive: {
    color: theme.colors.text,
    fontWeight: theme.typography.headline.fontWeight as "600",
  },
  stepLabelComplete: { color: theme.colors.success },
  almostDone: {
    marginTop: theme.spacing.xl,
    fontSize: theme.typography.caption.fontSize,
    color: theme.colors.textSecondary,
  },
});
