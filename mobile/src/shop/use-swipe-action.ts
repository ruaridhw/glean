import { useMemo } from "react";
import { Gesture } from "react-native-gesture-handler";

const DEFAULT_ACTION_THRESHOLD = 48;

interface SwipeTranslation {
  translationX: number;
  translationY: number;
}

export function shouldRunSwipeAction(
  { translationX, translationY }: SwipeTranslation,
  threshold = DEFAULT_ACTION_THRESHOLD,
): boolean {
  return translationX <= -threshold && Math.abs(translationX) > Math.abs(translationY);
}

export function useSwipeAction(onSwipeLeft: () => void) {
  const gesture = useMemo(
    () =>
      Gesture.Pan()
        .activeOffsetX([-16, 16])
        .failOffsetY([-24, 24])
        .runOnJS(true)
        .onEnd((event: SwipeTranslation) => {
          if (shouldRunSwipeAction(event)) {
            onSwipeLeft();
          }
        }),
    [onSwipeLeft],
  );

  return gesture;
}
