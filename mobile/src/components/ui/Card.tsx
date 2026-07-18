import type { ReactNode } from "react";
import { StyleSheet, View, type ViewProps } from "react-native";
import { theme } from "@/theme";

interface CardProps extends ViewProps {
  children: ReactNode;
}

export function Card({ children, style, ...props }: CardProps) {
  return (
    <View style={[styles.card, style]} {...props}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.card,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.lg,
    ...theme.shadow.card,
  },
});
