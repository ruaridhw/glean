import React, { useEffect, useRef } from "react";
import { Animated, View } from "react-native";

interface PulsingDotsProps {
  color: string;
  size?: number;
  spacing?: number;
}

export default function PulsingDots({
  color,
  size = 8,
  spacing = 8,
}: PulsingDotsProps) {
  const animations = useRef([
    new Animated.Value(0),
    new Animated.Value(0),
    new Animated.Value(0),
  ]).current;

  useEffect(() => {
    const startAnimation = () => {
      const animationSequence = animations.map((anim, index) =>
        Animated.sequence([
          Animated.delay(index * 200),
          Animated.loop(
            Animated.sequence([
              Animated.timing(anim, {
                toValue: 1,
                duration: 600,
                useNativeDriver: false,
              }),
              Animated.timing(anim, {
                toValue: 0,
                duration: 800,
                useNativeDriver: false,
              }),
            ])
          ),
        ])
      );

      Animated.parallel(animationSequence).start();
    };

    startAnimation();
  }, [animations]);

  return (
    <View
      style={{
        flexDirection: "row",
        gap: spacing,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {animations.map((anim, index) => (
        <Animated.View
          // biome-ignore lint/suspicious/noArrayIndexKey: static fixed-length array, never reorders
          key={index}
          testID="pulsing-dot"
          style={{
            width: size,
            height: size,
            borderRadius: size / 2,
            backgroundColor: color,
            opacity: anim.interpolate({
              inputRange: [0, 1],
              outputRange: [0.3, 1],
            }),
            transform: [
              {
                scale: anim.interpolate({
                  inputRange: [0, 1],
                  outputRange: [1, 1.2],
                }),
              },
            ],
          }}
        />
      ))}
    </View>
  );
}
