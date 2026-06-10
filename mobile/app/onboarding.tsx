import { router } from "expo-router";
import { useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  KeyboardAvoidingView,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useDescribeReceipt } from "@/api/hooks";
import { ErrorState } from "@/components/ui/ErrorState";
import { toRequiredSubmittedText } from "@/normalization/text-input";
import { ONBOARDING_SLIDES } from "@/onboarding/slides";
import { completeOnboarding } from "@/onboarding/storage";
import { theme } from "@/theme";

type OnboardingStep = "tour" | "describe";

async function finishOnboarding() {
  try {
    await completeOnboarding();
  } catch (error) {
    console.warn("[onboarding] completion flag write failed:", error);
  }
  router.replace("/(tabs)/pantry");
}

export default function OnboardingScreen() {
  const [pageIndex, setPageIndex] = useState(0);
  const [step, setStep] = useState<OnboardingStep>("tour");
  const [description, setDescription] = useState("");
  const { width } = useWindowDimensions();
  const listRef = useRef<FlatList<(typeof ONBOARDING_SLIDES)[number]>>(null);
  const describeMutation = useDescribeReceipt();

  const pageWidth = Math.max(width - theme.spacing.lg * 2, 1);
  const canSubmit = Boolean(toRequiredSubmittedText(description));
  const isLastPage = pageIndex === ONBOARDING_SLIDES.length - 1;

  function handleScroll(event: NativeSyntheticEvent<NativeScrollEvent>) {
    const width = event.nativeEvent.layoutMeasurement.width;
    if (width <= 0) return;
    setPageIndex(Math.round(event.nativeEvent.contentOffset.x / width));
  }

  function advanceTour() {
    if (isLastPage) {
      setStep("describe");
      return;
    }

    const nextIndex = pageIndex + 1;
    setPageIndex(nextIndex);
    listRef.current?.scrollToIndex({ animated: true, index: nextIndex });
  }

  function parseDescription() {
    const text = toRequiredSubmittedText(description);
    if (!text || describeMutation.isPending) return;

    describeMutation.mutate(text, {
      onSuccess: (result) => {
        router.push({
          pathname: "/(tabs)/pantry/review",
          params: { items: JSON.stringify(result.items), onboarding: "true" },
        });
      },
    });
  }

  if (step === "describe") {
    return (
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={styles.keyboardView}
      >
        <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
          <View style={styles.headerRow}>
            <Text style={styles.kicker}>Pantry setup</Text>
            <Pressable accessibilityRole="button" onPress={() => void finishOnboarding()}>
              <Text style={styles.skipText}>Skip for now</Text>
            </Pressable>
          </View>

          <View style={styles.describeContent}>
            <Text style={styles.title}>What do you have at home?</Text>
            <Text style={styles.body}>
              Type a rough list of what is already in your kitchen. You can edit everything before
              it is saved.
            </Text>
            <TextInput
              autoFocus
              multiline
              onChangeText={setDescription}
              placeholder="eggs, milk, some chicken in the freezer"
              style={styles.input}
              textAlignVertical="top"
              value={description}
            />
            {describeMutation.isError ? (
              <ErrorState
                message="Could not understand that. Try listing a few items, such as eggs, milk, rice."
                onRetry={() => describeMutation.reset()}
                testID="onboarding.describe.error"
              />
            ) : null}
          </View>

          <Pressable
            accessibilityRole="button"
            disabled={describeMutation.isPending || !canSubmit}
            onPress={parseDescription}
            style={[
              styles.primaryButton,
              (!canSubmit || describeMutation.isPending) && styles.disabled,
            ]}
          >
            {describeMutation.isPending ? (
              <ActivityIndicator color={theme.colors.primaryForeground} />
            ) : (
              <Text style={styles.primaryButtonText}>Review items</Text>
            )}
          </Pressable>
        </SafeAreaView>
      </KeyboardAvoidingView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      <View style={styles.headerRow}>
        <Text style={styles.kicker}>Glean</Text>
        <Pressable accessibilityRole="button" onPress={() => void finishOnboarding()}>
          <Text style={styles.skipText}>Skip</Text>
        </Pressable>
      </View>

      <FlatList
        ref={listRef}
        data={ONBOARDING_SLIDES}
        getItemLayout={(_, index) => ({
          index,
          length: pageWidth,
          offset: pageWidth * index,
        })}
        horizontal
        keyExtractor={(item) => item.key}
        onMomentumScrollEnd={handleScroll}
        pagingEnabled
        renderItem={({ item }) => (
          <View style={[styles.slide, { width: pageWidth }]}>
            <Image source={item.image} style={styles.illustration} />
            <Text style={styles.title}>{item.title}</Text>
            <Text style={styles.body}>{item.body}</Text>
          </View>
        )}
        scrollEnabled
        showsHorizontalScrollIndicator={false}
      />

      <View style={styles.dots}>
        {ONBOARDING_SLIDES.map((slide, index) => (
          <View
            accessibilityState={{ selected: index === pageIndex }}
            key={slide.key}
            style={[styles.dot, index === pageIndex && styles.activeDot]}
            testID={`onboarding.dot.${index}`}
          />
        ))}
      </View>

      <Pressable accessibilityRole="button" onPress={advanceTour} style={styles.primaryButton}>
        <Text style={styles.primaryButtonText}>{isLastPage ? "Get started" : "Next"}</Text>
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  activeDot: {
    backgroundColor: theme.colors.primary,
    width: 22,
  },
  body: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.subhead.fontSize,
    lineHeight: 22,
    textAlign: "center",
  },
  container: {
    backgroundColor: theme.colors.background,
    flex: 1,
    padding: theme.spacing.lg,
  },
  describeContent: {
    flex: 1,
    gap: theme.spacing.md,
    justifyContent: "center",
  },
  disabled: {
    opacity: 0.5,
  },
  dot: {
    backgroundColor: theme.colors.border,
    borderRadius: theme.radius.pill,
    height: 7,
    width: 7,
  },
  dots: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.xs,
    justifyContent: "center",
    marginBottom: theme.spacing.lg,
  },
  headerRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  illustration: {
    aspectRatio: 1,
    borderRadius: theme.radius.lg,
    height: 260,
    maxHeight: "58%",
    resizeMode: "contain",
    width: "100%",
  },
  input: {
    backgroundColor: theme.colors.card,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    color: theme.colors.text,
    fontSize: theme.typography.body.fontSize,
    minHeight: 132,
    padding: theme.spacing.md,
  },
  keyboardView: {
    backgroundColor: theme.colors.background,
    flex: 1,
  },
  kicker: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.sectionLabel.fontSize,
    fontWeight: theme.typography.sectionLabel.fontWeight,
    letterSpacing: theme.typography.sectionLabel.letterSpacing,
    textTransform: theme.typography.sectionLabel.textTransform,
  },
  primaryButton: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    justifyContent: "center",
    minHeight: 48,
    paddingHorizontal: theme.spacing.lg,
  },
  primaryButtonText: {
    color: theme.colors.primaryForeground,
    fontSize: theme.typography.body.fontSize,
    fontWeight: "700",
  },
  skipText: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "700",
  },
  slide: {
    alignItems: "center",
    flex: 1,
    gap: theme.spacing.lg,
    justifyContent: "center",
    paddingHorizontal: theme.spacing.sm,
  },
  title: {
    color: theme.colors.text,
    fontSize: 28,
    fontWeight: "800",
    lineHeight: 34,
    textAlign: "center",
  },
});
