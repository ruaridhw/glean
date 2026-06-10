import { Ionicons } from "@expo/vector-icons";
import { type ReactNode, useMemo, useRef, useState } from "react";
import {
  Animated,
  Easing,
  PanResponder,
  StyleSheet,
  useWindowDimensions,
  View,
} from "react-native";
import { shouldRunSwipeAction } from "@/components/swipe-action";
import { theme } from "@/theme";

interface SwipeDeleteRowProps {
  actionTestID: string;
  children: (deleteActive: boolean) => ReactNode;
  iconTestID: string;
  onDelete: () => void;
  rowTestID: string;
}

export function SwipeDeleteRow({
  actionTestID,
  children,
  iconTestID,
  onDelete,
  rowTestID,
}: SwipeDeleteRowProps) {
  const { width: screenWidth } = useWindowDimensions();
  const swipeX = useRef(new Animated.Value(0)).current;
  const [deleteActive, setDeleteActive] = useState(false);
  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, gestureState) =>
          Math.abs(gestureState.dx) > 16 && Math.abs(gestureState.dx) > Math.abs(gestureState.dy),
        onPanResponderGrant: () => {
          swipeX.stopAnimation();
        },
        onPanResponderMove: (_, gestureState) => {
          const nextX = Math.max(Math.min(gestureState.dx, 0), -160);
          swipeX.setValue(nextX);
          setDeleteActive(nextX <= -24 || gestureState.vx <= -0.75);
        },
        onPanResponderRelease: (_, gestureState) => {
          if (
            shouldRunSwipeAction({
              translationX: gestureState.dx,
              translationY: gestureState.dy,
              velocityX: gestureState.vx,
            })
          ) {
            setDeleteActive(true);
            const exitTarget = -(screenWidth + 32);
            const duration = Math.max(140, 240 - Math.min(Math.abs(gestureState.vx) * 40, 100));
            Animated.timing(swipeX, {
              toValue: exitTarget,
              duration,
              easing: Easing.out(Easing.quad),
              useNativeDriver: true,
            }).start(onDelete);
            return;
          }

          Animated.spring(swipeX, {
            toValue: 0,
            velocity: gestureState.vx,
            useNativeDriver: true,
          }).start(() => setDeleteActive(false));
        },
        onPanResponderTerminate: () => {
          Animated.spring(swipeX, {
            toValue: 0,
            useNativeDriver: true,
          }).start(() => setDeleteActive(false));
        },
        onPanResponderTerminationRequest: () => true,
      }),
    [onDelete, screenWidth, swipeX],
  );

  return (
    <View style={styles.container}>
      <View testID={actionTestID} style={[styles.action, deleteActive && styles.actionActive]}>
        <Ionicons
          testID={iconTestID}
          name="trash-outline"
          size={20}
          color={deleteActive ? theme.colors.danger : theme.colors.textSecondary}
        />
      </View>
      <Animated.View
        testID={rowTestID}
        style={[{ transform: [{ translateX: swipeX }] }]}
        {...panResponder.panHandlers}
      >
        {children(deleteActive)}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: theme.radius.lg,
    overflow: "hidden",
  },
  action: {
    alignItems: "flex-end",
    backgroundColor: "transparent",
    borderRadius: theme.radius.lg,
    bottom: 0,
    justifyContent: "center",
    left: 0,
    paddingRight: theme.spacing.lg,
    position: "absolute",
    right: 0,
    top: 0,
  },
  actionActive: {
    backgroundColor: "#FEE2E2",
  },
});
